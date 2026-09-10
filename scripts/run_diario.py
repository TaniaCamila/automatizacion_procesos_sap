#!/usr/bin/env python
"""Ejecución diaria segura (Operador): VBS SAP → validar FBL1N futuro → pipeline.

Uso (desde la raíz del proyecto):
  .venv\\Scripts\\python.exe scripts\\run_diario.py
  .venv\\Scripts\\python.exe scripts\\run_diario.py --simulate-vbs

No abre Power BI ni Outlook. No modifica el VBS original.
Solo termina: cscript propio + EXCEL.EXE/saplogon.exe *nuevos* tras el VBS.
Nunca mata Excel/SAP/Outlook que ya existían antes del wrapper.

Correo: solo el weekday configurado (MAIL_SEND_WEEKDAY, 0=lunes … 4=viernes)
puede respetar MAIL_AUTO_SEND=true. El resto fuerza false antes del pipeline.
--simulate-vbs nunca envía correo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Importante: NO importar src.config.config aquí.
# MAIL_AUTO_SEND debe decidirse y escribirse en os.environ antes de cargar config.

LOCK_FILENAME = "run_diario.lock"
PIPELINE_SCRIPT = ROOT / "scripts" / "run_actualizacion_automatica.py"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
BACKUP_DIRNAME = "fbl1n_future_backups"
DOTENV_PATH = ROOT / ".env"

STABLE_CHECKS = 3
STABLE_INTERVAL_SEC = 2.0
DEFAULT_VBS_TIMEOUT_SEC = 45 * 60
DEFAULT_POST_VALIDATE_KILL_GRACE_SEC = 2.0
DEFAULT_FILE_RELEASE_TIMEOUT_SEC = 120.0
DEFAULT_FILE_RELEASE_POLL_SEC = 0.5
SAP_EXPORT_IMAGES = ("EXCEL.EXE", "saplogon.exe")

EXIT_OK = 0
EXIT_LOCK = 2
EXIT_VBS = 3
EXIT_INVALID = 4
EXIT_PIPELINE = 5
EXIT_CONFIG = 6
EXIT_UNEXPECTED = 1
EXIT_INTERRUPTED = 130
PIPELINE_LOCK_FILENAME = "pipeline.lock"
CUTOFF_MODE_STATIC = "static"
CUTOFF_MODE_MAX_SOURCE = "max_source_date"

# Rellenados por load_project_config() tras el override de correo.
ROOT_DIR: Path = ROOT
FBL1N_FUTURE_ENABLED: bool = False
FBL1N_FUTURE_PATH: Path = ROOT
FBL1N_COMPENSATION_CUTOFF: Any = None
EXPECTED_COLUMNS: tuple[str, ...] = ()
FECHA_COMP_COL: str = "Fecha compensación"


class DiarioAborted(Exception):
    """Fallo controlado del wrapper diario."""

    def __init__(self, message: str, *, exit_code: int = EXIT_UNEXPECTED) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class BackupInfo:
    source: Path
    backup: Path
    sha256: str
    size: int
    mtime_ns: int
    existed: bool


@dataclass
class ChildProc:
    pid: int
    popen: Any | None = None


@dataclass(frozen=True)
class MailDayPolicy:
    local_date: str
    weekday: int
    configured_mail_weekday: int
    mail_configured: bool
    mail_effective: bool
    motivo: str


@dataclass(frozen=True)
class SourceCutoffInfo:
    mode: str
    local_date: str
    source_latest_compensation_date: str
    effective_compensation_cutoff: str
    rows_with_date_after_local_date: int
    valid_business_rows: int
    mail_subject_preview: str


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    """Leer .env sin pasar por config (evita congelar MAIL_AUTO_SEND)."""

    values: dict[str, str] = {}
    if not path.is_file():
        return values
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def _lookup_env(name: str, dotenv: dict[str, str]) -> str:
    if name in os.environ:
        return os.environ.get(name, "").strip().strip('"').strip("'")
    return str(dotenv.get(name, "")).strip().strip('"').strip("'")


def _parse_bool_strict(raw: str) -> bool:
    return raw.strip().lower() in {"true", "1", "yes", "on"}


def resolve_mail_day_policy(
    *,
    now: datetime,
    simulate_vbs: bool,
    dotenv_path: Path | None = None,
) -> MailDayPolicy:
    """Decidir MAIL_AUTO_SEND efectivo según weekday local (Mon=0 … Sun=6)."""

    dotenv = _parse_dotenv_file(dotenv_path or DOTENV_PATH)
    raw_weekday = _lookup_env("MAIL_SEND_WEEKDAY", dotenv)
    if not raw_weekday:
        raise DiarioAborted(
            "MAIL_SEND_WEEKDAY ausente; se exige 0..6 (0=lunes … 4=viernes).",
            exit_code=EXIT_CONFIG,
        )
    try:
        configured_weekday = int(raw_weekday)
    except ValueError as exc:
        raise DiarioAborted(
            f"MAIL_SEND_WEEKDAY inválido ({raw_weekday!r}); se exige entero 0..6.",
            exit_code=EXIT_CONFIG,
        ) from exc
    if configured_weekday < 0 or configured_weekday > 6:
        raise DiarioAborted(
            f"MAIL_SEND_WEEKDAY fuera de rango ({configured_weekday}); se exige 0..6.",
            exit_code=EXIT_CONFIG,
        )

    mail_configured = _parse_bool_strict(_lookup_env("MAIL_AUTO_SEND", dotenv))
    weekday = int(now.weekday())
    local_date = now.date().isoformat()

    if simulate_vbs:
        return MailDayPolicy(
            local_date=local_date,
            weekday=weekday,
            configured_mail_weekday=configured_weekday,
            mail_configured=mail_configured,
            mail_effective=False,
            motivo="simulate-vbs fuerza MAIL_AUTO_SEND=false",
        )
    if weekday != configured_weekday:
        return MailDayPolicy(
            local_date=local_date,
            weekday=weekday,
            configured_mail_weekday=configured_weekday,
            mail_configured=mail_configured,
            mail_effective=False,
            motivo=(
                f"weekday={weekday} ≠ MAIL_SEND_WEEKDAY={configured_weekday}; "
                "override MAIL_AUTO_SEND=false"
            ),
        )
    return MailDayPolicy(
        local_date=local_date,
        weekday=weekday,
        configured_mail_weekday=configured_weekday,
        mail_configured=mail_configured,
        mail_effective=bool(mail_configured),
        motivo=(
            "día de envío; se respeta MAIL_AUTO_SEND del .env"
            if mail_configured
            else "día de envío; MAIL_AUTO_SEND=false en .env"
        ),
    )


def apply_mail_day_policy(policy: MailDayPolicy, logger: logging.Logger) -> None:
    """Escribir override en os.environ antes de importar/usar config del orquestador."""

    os.environ["MAIL_AUTO_SEND"] = "true" if policy.mail_effective else "false"
    if "src.config.config" in sys.modules:
        cfg = sys.modules["src.config.config"]
        cfg.MAIL_AUTO_SEND = bool(policy.mail_effective)
    logger.info(
        "local_date=%s weekday=%s configured_mail_weekday=%s "
        "mail_configured=%s mail_effective=%s motivo=%s",
        policy.local_date,
        policy.weekday,
        policy.configured_mail_weekday,
        policy.mail_configured,
        policy.mail_effective,
        policy.motivo,
    )


def load_project_config() -> None:
    """Importar config del proyecto solo después del override de correo."""

    global ROOT_DIR, FBL1N_FUTURE_ENABLED, FBL1N_FUTURE_PATH
    global FBL1N_COMPENSATION_CUTOFF, EXPECTED_COLUMNS, FECHA_COMP_COL

    from src.config.config import (
        FBL1N_COMPENSATION_CUTOFF as _cutoff,
        FBL1N_FUTURE_ENABLED as _fut_en,
        FBL1N_FUTURE_PATH as _fut_path,
        ROOT_DIR as _root,
        resolve_log_dir as _resolve_log_dir,
        resolve_state_dir as _resolve_state_dir,
    )
    from src.modules.fbl1n_fuentes.module import (
        EXPECTED_COLUMNS as _cols,
        FECHA_COMP_COL as _fecha,
    )
    import src.config.config as cfg

    # Re-sincronizar por si config ya estaba importado en el proceso.
    cfg.MAIL_AUTO_SEND = _parse_bool_strict(os.environ.get("MAIL_AUTO_SEND", ""))

    ROOT_DIR = _root
    FBL1N_FUTURE_ENABLED = bool(_fut_en)
    FBL1N_FUTURE_PATH = Path(_fut_path)
    FBL1N_COMPENSATION_CUTOFF = _cutoff
    EXPECTED_COLUMNS = tuple(_cols)
    FECHA_COMP_COL = str(_fecha)

    # Exponer resolvers usados por lock/logging (mismas funciones del proyecto).
    global resolve_log_dir, resolve_state_dir
    resolve_log_dir = _resolve_log_dir  # type: ignore[misc]
    resolve_state_dir = _resolve_state_dir  # type: ignore[misc]


def resolve_log_dir() -> Path:
    return ROOT / "logs"


def resolve_state_dir() -> Path:
    return ROOT / "state"


def maybe_retry_pending_mail(logger: logging.Logger) -> str:
    """
    Viernes (mail_effective): si hay Pending del alias publicado, reintentar envío
    sin reconstruir MATRIZ. Sin Pending → no envía (anti-duplicado / Unchanged limpio).
    """

    import src.config.config as cfg
    from src.modules.actualizacion_automatica.mail import (
        MAIL_PENDING,
        load_mail_state,
        run_mail_stage,
    )
    from src.modules.actualizacion_automatica.module import load_state
    from src.modules.publicacion_final.module import (
        PUBLISH_SUCCEEDED,
        load_publish_state,
    )

    if not bool(cfg.MAIL_AUTO_SEND):
        logger.info("mail_effective=false; no retry de correo Pending")
        return "skipped_mail_effective_false"

    pipeline = load_state()
    publish = load_publish_state()
    mail = load_mail_state()
    if not pipeline:
        logger.info("Sin last_fbl1n_state; no retry de correo")
        return "skipped_no_pipeline_state"
    if not publish or str(publish.get("publish_status") or "") != PUBLISH_SUCCEEDED:
        logger.info("Publicación no Succeeded; no retry de correo")
        return "skipped_publish_not_succeeded"
    if not mail or str(mail.get("mail_status") or "") != MAIL_PENDING:
        logger.info("Unchanged/sin Pending: no se envía correo")
        return "skipped_no_pending"

    sha = str(
        pipeline.get("source_fbl1n_sha256")
        or pipeline.get("combined_source_sha256")
        or ""
    ).strip()
    mail_sha = str(mail.get("source_fbl1n_sha256") or "").strip()
    pub_sha = str(publish.get("source_fbl1n_sha256") or "").strip()
    if not sha or sha != mail_sha or (pub_sha and pub_sha != sha):
        logger.info(
            "Alias inconsistente pipeline/mail/publish; no retry "
            "(pipeline=%s mail=%s publish=%s)",
            sha[:12] if sha else "-",
            mail_sha[:12] if mail_sha else "-",
            pub_sha[:12] if pub_sha else "-",
        )
        return "skipped_alias_mismatch"

    months = list(pipeline.get("months") or [])
    latest = str(pipeline.get("latest_compensation_date") or "").strip() or None
    logger.info(
        "Retry correo Pending sin reconstruir MATRIZ alias=%s…",
        sha[:16],
    )
    # decision=Changed desbloquea mail_may_be_composed en modo futuro; el contenido
    # pendiente proviene de un Changed previo para el mismo alias publicado.
    staged = run_mail_stage(
        sha,
        logger,
        months=months,
        latest_compensation_date=latest,
        future_enabled=True,
        decision="Changed",
        publish_ok=True,
    )
    logger.info(
        "Retry correo status=%s executed=%s message=%s",
        staged.status,
        staged.executed,
        staged.message,
    )
    return f"retried:{staged.status}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def _terminate_pid_only(pid: int, logger: logging.Logger) -> bool:
    """Terminar exclusivamente el PID indicado (no árboles ajenos)."""

    if pid <= 0 or not _pid_running(pid):
        logger.info("PID %s ya no está vivo; no se termina", pid)
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, int(pid))  # PROCESS_TERMINATE
        if not handle:
            logger.warning("No se pudo abrir PID %s para TerminateProcess", pid)
            return False
        try:
            ok = bool(ctypes.windll.kernel32.TerminateProcess(handle, 1))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        logger.info("TerminateProcess PID=%s ok=%s", pid, ok)
        return ok
    except Exception as exc:
        logger.warning("Fallo terminando PID %s: %s", pid, exc)
        return False


def list_pids_for_images(
    images: tuple[str, ...] = SAP_EXPORT_IMAGES,
) -> set[int]:
    """Snapshot de PIDs para EXCEL.EXE / saplogon.exe (u otras imágenes)."""

    wanted = {name.lower() for name in images}
    found: set[int] = set()
    if sys.platform != "win32":
        return found
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=creationflags,
            check=False,
        )
    except Exception:
        return found
    for row in csv.reader(StringIO(proc.stdout or "")):
        if len(row) < 2:
            continue
        image = str(row[0]).strip().strip('"')
        if image.lower() not in wanted:
            continue
        try:
            found.add(int(str(row[1]).strip().strip('"')))
        except ValueError:
            continue
    return found


def is_transient_lock_error(exc: BaseException) -> bool:
    """PermissionError / sharing violation: reintentar, no abortar de inmediato."""

    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror in (32, 33):  # sharing / lock violation
            return True
        errno = getattr(exc, "errno", None)
        if errno in (13, 11):  # EACCES / EAGAIN
            return True
        msg = str(exc).lower()
        if "permission" in msg or "denied" in msg or "being used" in msg:
            return True
    return False


def wait_until_file_readable(
    path: Path,
    *,
    timeout_sec: float,
    logger: logging.Logger,
    sleep_fn: Callable[[float], None] | None = None,
    poll_sec: float = DEFAULT_FILE_RELEASE_POLL_SEC,
) -> None:
    """Esperar a que el xlsx deje de estar bloqueado en exclusivo."""

    sleeper = sleep_fn or time.sleep
    deadline = time.monotonic() + timeout_sec
    last_exc: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            with path.open("rb") as handle:
                handle.read(1)
            logger.info("Archivo legible: %s", path)
            return
        except OSError as exc:
            last_exc = exc
            if is_transient_lock_error(exc):
                logger.info(
                    "Archivo aún bloqueado (%s); reintentando…",
                    type(exc).__name__,
                )
                sleeper(poll_sec)
                continue
            raise
    raise DiarioAborted(
        f"Timeout esperando liberación de {path}: {last_exc}",
        exit_code=EXIT_VBS,
    )


def terminate_new_pids(
    baseline: set[int],
    *,
    list_pids_fn: Callable[[], set[int]],
    terminate_fn: Callable[[int, logging.Logger], bool],
    logger: logging.Logger,
    label: str = "office",
) -> set[int]:
    """Terminar solo PIDs actuales que no estaban en el baseline."""

    current = set(list_pids_fn())
    newcomers = sorted(pid for pid in (current - set(baseline)) if pid > 0)
    if not newcomers:
        logger.info("Sin PIDs %s nuevos que terminar (baseline=%s)", label, sorted(baseline))
        return set()
    logger.info(
        "Terminando PIDs %s nuevos=%s (baseline=%s)",
        label,
        newcomers,
        sorted(baseline),
    )
    terminated: set[int] = set()
    for pid in newcomers:
        if terminate_fn(pid, logger):
            terminated.add(pid)
        else:
            # Intentar igual marcar para trazabilidad; el proceso pudo morir solo.
            terminated.add(pid)
    return terminated


def release_sap_export_holders(
    *,
    future: Path,
    baseline_office_pids: set[int],
    cscript: ChildProc | None,
    terminate_fn: Callable[[int, logging.Logger], bool],
    list_pids_fn: Callable[[], set[int]],
    logger: logging.Logger,
    sleep_fn: Callable[[float], None] | None = None,
    grace_sec: float = DEFAULT_POST_VALIDATE_KILL_GRACE_SEC,
    release_timeout_sec: float = DEFAULT_FILE_RELEASE_TIMEOUT_SEC,
) -> set[int]:
    """
    Tras estabilidad por size/mtime: cerrar cscript propio y Excel/saplogon *nuevos*,
    luego esperar legibilidad del futuro.
    """

    sleeper = sleep_fn or time.sleep
    killed: set[int] = set()
    if cscript is not None and cscript.pid > 0:
        sleeper(grace_sec)
        terminate_fn(cscript.pid, logger)
        killed.add(cscript.pid)
        if cscript.popen is not None:
            try:
                cscript.popen.wait(timeout=5)
            except Exception:
                pass
    killed |= terminate_new_pids(
        baseline_office_pids,
        list_pids_fn=list_pids_fn,
        terminate_fn=terminate_fn,
        logger=logger,
        label="EXCEL/saplogon",
    )
    if future.is_file():
        wait_until_file_readable(
            future,
            timeout_sec=release_timeout_sec,
            logger=logger,
            sleep_fn=sleeper,
        )
    return killed


def setup_logging(stamp: str) -> tuple[logging.Logger, Path]:
    log_dir = resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_diario_{stamp}.log"
    logger = logging.getLogger("run_diario")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger, log_path


def lock_path() -> Path:
    return resolve_state_dir() / LOCK_FILENAME


class DiarioLock:
    """Lock exclusivo distinto de pipeline.lock. Huérfanos: abortar sin borrar."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or lock_path()
        self._held = False
        self.pid = os.getpid()

    def acquire(self, logger: logging.Logger) -> None:
        resolve_state_dir().mkdir(parents=True, exist_ok=True)
        if self.path.is_file():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                other = int(payload.get("pid") or 0)
            except (OSError, ValueError, json.JSONDecodeError, TypeError):
                raise DiarioAborted(
                    f"Lock ilegible en {self.path}. Recuperación: verificar que no "
                    f"haya otra corrida; si el PID no existe, eliminar manualmente "
                    f"solo este archivo ({LOCK_FILENAME}) y reintentar.",
                    exit_code=EXIT_LOCK,
                )
            if _pid_running(other) and other != self.pid:
                raise DiarioAborted(
                    f"Lock activo: proceso vivo pid={other} ({self.path})",
                    exit_code=EXIT_LOCK,
                )
            # Huérfano: NO borrar en silencio.
            logger.error(
                "Lock huérfano detectado path=%s pid=%s (proceso no vivo). "
                "NO se elimina automáticamente. Recuperación: confirmar que no hay "
                "corrida en curso y eliminar manualmente %s",
                self.path,
                other,
                self.path,
            )
            raise DiarioAborted(
                f"Lock huérfano en {self.path} (pid={other}). "
                f"Eliminar manualmente tras verificación y reintentar.",
                exit_code=EXIT_LOCK,
            )
        payload = {
            "pid": self.pid,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "script": "run_diario.py",
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self._held = True
        logger.info("Lock adquirido %s pid=%s", self.path, self.pid)

    def release(self, logger: logging.Logger) -> None:
        if not self._held:
            return
        try:
            if self.path.is_file():
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                    owner = int(payload.get("pid") or 0)
                except (OSError, ValueError, json.JSONDecodeError, TypeError):
                    owner = -1
                if owner == self.pid:
                    self.path.unlink()
                    logger.info("Lock liberado %s", self.path)
                else:
                    logger.warning(
                        "Lock no liberado: pertenece a pid=%s (actual=%s)",
                        owner,
                        self.pid,
                    )
        except OSError as exc:
            logger.warning("No se pudo liberar lock: %s", exc)
        self._held = False


def _env_str(name: str) -> str:
    return os.getenv(name, "").strip().strip('"').strip("'")


def resolve_vbs_path() -> Path:
    raw = _env_str("SAP_FBL1N_VBS_PATH")
    if not raw:
        raise DiarioAborted(
            "SAP_FBL1N_VBS_PATH ausente en .env",
            exit_code=EXIT_CONFIG,
        )
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    else:
        path = path.resolve()
    return path


def precheck_config(*, simulate_vbs: bool, logger: logging.Logger) -> Path:
    """Validar configuración. Retorna ruta VBS (puede ser ficticia en simulate)."""

    if not VENV_PYTHON.is_file():
        raise DiarioAborted(f"No existe .venv: {VENV_PYTHON}", exit_code=EXIT_CONFIG)
    if not PIPELINE_SCRIPT.is_file():
        raise DiarioAborted(
            f"No existe pipeline: {PIPELINE_SCRIPT}",
            exit_code=EXIT_CONFIG,
        )
    if not FBL1N_FUTURE_ENABLED:
        raise DiarioAborted(
            "FBL1N_FUTURE_ENABLED debe ser true",
            exit_code=EXIT_CONFIG,
        )
    if FBL1N_COMPENSATION_CUTOFF is None:
        raise DiarioAborted(
            "FBL1N_COMPENSATION_CUTOFF ausente o inválida",
            exit_code=EXIT_CONFIG,
        )
    future = Path(FBL1N_FUTURE_PATH)
    if not future.exists() and not future.parent.is_dir():
        raise DiarioAborted(
            f"FBL1N_FUTURE_PATH inexistente y carpeta padre ausente: {future}",
            exit_code=EXIT_CONFIG,
        )
    logger.info(
        "Config OK future=%s cutoff=%s future_enabled=%s",
        future,
        FBL1N_COMPENSATION_CUTOFF.isoformat(),
        FBL1N_FUTURE_ENABLED,
    )
    if simulate_vbs:
        logger.warning("Modo --simulate-vbs: no se ejecutará cscript real")
        return Path("(simulate)")
    vbs = resolve_vbs_path()
    if not vbs.is_file():
        raise DiarioAborted(f"SAP_FBL1N_VBS_PATH no existe: {vbs}", exit_code=EXIT_CONFIG)
    logger.info("VBS=%s", vbs)
    return vbs


def backup_future_file(future: Path, logger: logging.Logger) -> BackupInfo | None:
    """Copiar FBL1N futuro válido anterior a backup local; nunca borrar el respaldo."""

    if not future.is_file() or future.stat().st_size <= 0:
        logger.info("Sin archivo futuro previo válido para backup: %s", future)
        return None
    backup_root = ROOT / "temp" / BACKUP_DIRNAME
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    dest = backup_root / f"FBL1N_future_backup_{stamp}.xlsx"
    shutil.copy2(future, dest)
    sha = _sha256_file(dest)
    st = dest.stat()
    info = BackupInfo(
        source=future.resolve(),
        backup=dest.resolve(),
        sha256=sha,
        size=int(st.st_size),
        mtime_ns=int(st.st_mtime_ns),
        existed=True,
    )
    logger.info(
        "Backup futuro sha=%s size=%s mtime_ns=%s path=%s",
        sha,
        info.size,
        info.mtime_ns,
        dest,
    )
    return info


def restore_future_atomic(backup: BackupInfo, logger: logging.Logger) -> str:
    """Restaurar atómicamente el FBL1N futuro desde backup y verificar SHA."""

    target = backup.source
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + f".restore.{os.getpid()}.tmp")
    shutil.copy2(backup.backup, tmp)
    os.replace(tmp, target)
    restored_sha = _sha256_file(target)
    if restored_sha != backup.sha256:
        raise DiarioAborted(
            f"SHA restaurado ({restored_sha}) ≠ backup ({backup.sha256})",
            exit_code=EXIT_UNEXPECTED,
        )
    logger.info(
        "Restaurado FBL1N futuro desde %s → %s sha=%s (OK)",
        backup.backup,
        target,
        restored_sha,
    )
    return restored_sha


def preserve_failed_future(future: Path, logger: logging.Logger) -> Path | None:
    """Conservar evidencia del futuro fallido/interrumpido sin borrar el backup."""

    if not future.is_file() or future.stat().st_size <= 0:
        return None
    dest_dir = ROOT / "temp" / "fbl1n_future_failed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"FBL1N_future_failed_{_now_stamp()}.xlsx"
    shutil.copy2(future, dest)
    logger.info("Evidencia futuro fallido conservada en %s sha=%s", dest, _sha256_file(dest))
    return dest.resolve()


def release_pipeline_lock_if_child(
    child_pids: set[int],
    logger: logging.Logger,
) -> None:
    """Liberar pipeline.lock solo si el PID dueño es un hijo registrado por este wrapper."""

    path = resolve_state_dir() / PIPELINE_LOCK_FILENAME
    if not path.is_file() or not child_pids:
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        owner = int(payload.get("pid") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        logger.warning("pipeline.lock ilegible; no se elimina automáticamente: %s", path)
        return
    if owner in child_pids:
        try:
            path.unlink()
            logger.info("pipeline.lock liberado (pid hijo=%s)", owner)
        except OSError as exc:
            logger.warning("No se pudo liberar pipeline.lock: %s", exc)
    else:
        logger.info(
            "pipeline.lock pertenece a pid=%s (no es hijo registrado); no se toca",
            owner,
        )


def terminate_registered_children(
    children: list[ChildProc],
    *,
    terminate_fn: Callable[[int, logging.Logger], bool],
    logger: logging.Logger,
) -> set[int]:
    """Terminar únicamente PIDs hijos creados por este wrapper."""

    seen: set[int] = set()
    for child in children:
        if child.pid <= 0 or child.pid in seen:
            continue
        seen.add(child.pid)
        terminate_fn(child.pid, logger)
        if child.popen is not None:
            try:
                child.popen.wait(timeout=5)
            except Exception:
                pass
    return seen


def assert_ooxml_zip(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise DiarioAborted(f"Archivo vacío o ausente: {path}", exit_code=EXIT_INVALID)
    with path.open("rb") as handle:
        magic = handle.read(4)
    if magic[:2] != b"PK":
        raise DiarioAborted(f"No es OOXML/ZIP: {path}", exit_code=EXIT_INVALID)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
        if bad is not None:
            raise DiarioAborted(f"ZIP corrupto ({bad}): {path}", exit_code=EXIT_INVALID)
    except zipfile.BadZipFile as exc:
        raise DiarioAborted(f"ZIP inválido: {path}", exit_code=EXIT_INVALID) from exc


def validate_fbl1n_business(path: Path, logger: logging.Logger) -> dict[str, Any]:
    """21 columnas canónicas, ≥1 fila, fechas de compensación legibles."""

    import pandas as pd

    assert_ooxml_zip(path)
    frame = pd.read_excel(path, engine="calamine")
    columns = [str(c) for c in frame.columns.tolist()]
    if columns != list(EXPECTED_COLUMNS):
        raise DiarioAborted(
            f"Columnas no canónicas ({len(columns)}). "
            f"missing={sorted(set(EXPECTED_COLUMNS) - set(columns))[:5]} "
            f"extra={sorted(set(columns) - set(EXPECTED_COLUMNS))[:5]}",
            exit_code=EXIT_INVALID,
        )
    if frame.empty:
        raise DiarioAborted("FBL1N futuro sin filas", exit_code=EXIT_INVALID)
    if FECHA_COMP_COL not in frame.columns:
        raise DiarioAborted("Sin columna Fecha compensación", exit_code=EXIT_INVALID)
    dates = pd.to_datetime(frame[FECHA_COMP_COL], errors="coerce")
    valid = int(dates.notna().sum())
    if valid < 1:
        raise DiarioAborted(
            "Ninguna Fecha compensación legible",
            exit_code=EXIT_INVALID,
        )
    meta = {
        "rows": int(len(frame)),
        "valid_dates": valid,
        "sha256": _sha256_file(path),
        "size": int(path.stat().st_size),
    }
    logger.info(
        "FBL1N futuro validado rows=%s valid_dates=%s sha=%s",
        meta["rows"],
        meta["valid_dates"],
        meta["sha256"],
    )
    return meta


def resolve_cutoff_mode(*, dotenv_path: Path | None = None) -> str:
    """Leer FBL1N_COMPENSATION_CUTOFF_MODE (static | max_source_date)."""

    dotenv = _parse_dotenv_file(dotenv_path or DOTENV_PATH)
    raw = _lookup_env("FBL1N_COMPENSATION_CUTOFF_MODE", dotenv).strip().lower()
    if not raw:
        return CUTOFF_MODE_STATIC
    if raw in {CUTOFF_MODE_STATIC, CUTOFF_MODE_MAX_SOURCE}:
        return raw
    raise DiarioAborted(
        f"FBL1N_COMPENSATION_CUTOFF_MODE inválido ({raw!r}); "
        f"se exige '{CUTOFF_MODE_STATIC}' o '{CUTOFF_MODE_MAX_SOURCE}'.",
        exit_code=EXIT_CONFIG,
    )


def compute_source_cutoff_info(
    path: Path,
    *,
    local_date: date,
    logger: logging.Logger,
    mode: str = CUTOFF_MODE_MAX_SOURCE,
) -> SourceCutoffInfo:
    """
    Máxima Fecha compensación entre filas de negocio válidas
    (Sociedad + Fecha presentes). Pies/totales SAP no cuentan.
    """

    import pandas as pd
    from src.modules.actualizacion_automatica.mail import build_mail_subject
    from src.modules.fbl1n_fuentes.module import (
        _parse_compensation_date_value,
        _required_fields_present,
        semantic_fbl1n_fingerprint,
    )

    frame = pd.read_excel(path, engine="calamine")
    columns = [str(c) for c in frame.columns.tolist()]
    if columns != list(EXPECTED_COLUMNS):
        raise DiarioAborted(
            "Columnas no canónicas al calcular cutoff desde fuente",
            exit_code=EXIT_INVALID,
        )
    sem = semantic_fbl1n_fingerprint(frame)
    latest = sem.latest_compensation_date
    if not latest or sem.valid_rows < 1:
        raise DiarioAborted(
            "Ninguna Fecha de compensación válida en filas de negocio "
            "(se excluyen pies/totales sin campos obligatorios).",
            exit_code=EXIT_INVALID,
        )

    valid = frame.loc[_required_fields_present(frame)]
    after_local = 0
    for value in valid[FECHA_COMP_COL]:
        parsed = _parse_compensation_date_value(value)
        if parsed is not None and parsed > local_date:
            after_local += 1

    subject = build_mail_subject(
        "periodo",
        latest_compensation_date=latest,
        future_enabled=True,
    )
    info = SourceCutoffInfo(
        mode=mode,
        local_date=local_date.isoformat(),
        source_latest_compensation_date=latest,
        effective_compensation_cutoff=latest,
        rows_with_date_after_local_date=int(after_local),
        valid_business_rows=int(sem.valid_rows),
        mail_subject_preview=subject,
    )
    logger.info(
        "cutoff_mode=%s local_date=%s source_latest_compensation_date=%s "
        "effective_compensation_cutoff=%s rows_with_date_after_local_date=%s "
        "valid_business_rows=%s",
        info.mode,
        info.local_date,
        info.source_latest_compensation_date,
        info.effective_compensation_cutoff,
        info.rows_with_date_after_local_date,
        info.valid_business_rows,
    )
    if after_local:
        logger.info(
            "Se incluyen %s fila(s) con Fecha compensación > local_date=%s "
            "(no se limitan por el reloj del PC)",
            after_local,
            info.local_date,
        )
    return info


def apply_effective_compensation_cutoff(
    info: SourceCutoffInfo,
    logger: logging.Logger,
    *,
    persist: bool,
) -> str | None:
    """
    Fijar FBL1N_COMPENSATION_CUTOFF en os.environ + config del proceso.
    Si persist=False (simulación), no modifica el entorno.
    Devuelve el valor previo de os.environ (o None).
    """

    prev = os.environ.get("FBL1N_COMPENSATION_CUTOFF")
    if not persist:
        logger.info(
            "SIMULATE cutoff (sin escribir env): effective_compensation_cutoff=%s "
            "mail_subject_preview=%s",
            info.effective_compensation_cutoff,
            info.mail_subject_preview,
        )
        return prev

    global FBL1N_COMPENSATION_CUTOFF
    iso = info.effective_compensation_cutoff
    os.environ["FBL1N_COMPENSATION_CUTOFF"] = iso
    FBL1N_COMPENSATION_CUTOFF = date.fromisoformat(iso)
    try:
        import src.config.config as cfg

        cfg.FBL1N_COMPENSATION_CUTOFF = FBL1N_COMPENSATION_CUTOFF
    except Exception as exc:
        logger.warning("No se pudo sincronizar cfg.FBL1N_COMPENSATION_CUTOFF: %s", exc)
    logger.info(
        "FBL1N_COMPENSATION_CUTOFF efectivo aplicado=%s (prev=%s) "
        "mail_subject_preview=%s",
        iso,
        prev or "-",
        info.mail_subject_preview,
    )
    return prev


def resolve_and_apply_cutoff_from_source(
    path: Path,
    *,
    local_date: date,
    logger: logging.Logger,
    dotenv_path: Path | None = None,
    persist: bool = True,
) -> SourceCutoffInfo | None:
    """Si mode=max_source_date, calcular máximo y aplicar; si static, no-op."""

    mode = resolve_cutoff_mode(dotenv_path=dotenv_path)
    if mode != CUTOFF_MODE_MAX_SOURCE:
        fallback = (
            FBL1N_COMPENSATION_CUTOFF.isoformat()
            if FBL1N_COMPENSATION_CUTOFF is not None
            else os.environ.get("FBL1N_COMPENSATION_CUTOFF", "-")
        )
        logger.info(
            "cutoff_mode=%s local_date=%s effective_compensation_cutoff=%s "
            "(fallback .env; sin derivar desde fuente)",
            mode,
            local_date.isoformat(),
            fallback,
        )
        return None
    info = compute_source_cutoff_info(
        path, local_date=local_date, logger=logger, mode=mode
    )
    apply_effective_compensation_cutoff(info, logger, persist=persist)
    return info


def wait_stable_new_file(
    path: Path,
    *,
    started_monotonic: float,
    timeout_sec: float,
    logger: logging.Logger,
    checks: int = STABLE_CHECKS,
    interval_sec: float = STABLE_INTERVAL_SEC,
    min_mtime_ns: int | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Esperar archivo nuevo post-inicio y estable N veces (solo size/mtime; sin open)."""

    sleeper = sleep_fn or time.sleep
    deadline = time.monotonic() + timeout_sec
    last: tuple[int, int] | None = None
    stable = 0
    while time.monotonic() < deadline:
        if not path.is_file():
            last = None
            stable = 0
            sleeper(interval_sec)
            continue
        try:
            st = path.stat()
        except OSError as exc:
            if is_transient_lock_error(exc):
                logger.info("stat transitorio (%s); reintentando…", type(exc).__name__)
            last = None
            stable = 0
            sleeper(interval_sec)
            continue
        if st.st_size <= 0:
            last = None
            stable = 0
            sleeper(interval_sec)
            continue
        if min_mtime_ns is not None and int(st.st_mtime_ns) < min_mtime_ns:
            # Aún el archivo anterior (VBS no reemplazó).
            last = None
            stable = 0
            sleeper(interval_sec)
            continue
        key = (int(st.st_size), int(st.st_mtime_ns))
        if key == last:
            stable += 1
        else:
            last = key
            stable = 1
        if stable >= checks:
            logger.info(
                "Archivo estable size=%s mtime_ns=%s checks=%s (sin validar aún)",
                key[0],
                key[1],
                checks,
            )
            return {"size": key[0], "mtime_ns": key[1]}
        sleeper(interval_sec)
    raise DiarioAborted(
        f"Timeout esperando FBL1N futuro estable ({timeout_sec:.0f}s): {path}",
        exit_code=EXIT_VBS,
    )


def validate_fbl1n_business_retrying(
    path: Path,
    logger: logging.Logger,
    *,
    timeout_sec: float = DEFAULT_FILE_RELEASE_TIMEOUT_SEC,
    sleep_fn: Callable[[float], None] | None = None,
    poll_sec: float = DEFAULT_FILE_RELEASE_POLL_SEC,
) -> dict[str, Any]:
    """Validar negocio solo cuando el archivo es legible; PermissionError es transitorio."""

    sleeper = sleep_fn or time.sleep
    deadline = time.monotonic() + timeout_sec
    last_exc: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            with path.open("rb") as handle:
                handle.read(1)
            return validate_fbl1n_business(path, logger)
        except DiarioAborted:
            raise
        except OSError as exc:
            last_exc = exc
            if is_transient_lock_error(exc):
                logger.info(
                    "Validación diferida por bloqueo (%s); reintentando…",
                    type(exc).__name__,
                )
                sleeper(poll_sec)
                continue
            raise
    raise DiarioAborted(
        f"Timeout validando FBL1N futuro legible: {path} ({last_exc})",
        exit_code=EXIT_VBS,
    )


def start_cscript(vbs: Path, logger: logging.Logger) -> ChildProc:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    logger.info('Ejecutando: cscript.exe //nologo "%s"', vbs)
    popen = subprocess.Popen(
        ["cscript.exe", "//nologo", str(vbs)],
        cwd=str(vbs.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    logger.info("cscript PID hijo=%s", popen.pid)
    return ChildProc(pid=int(popen.pid), popen=popen)


def run_nonproductive_simulation(
    *,
    logger: logging.Logger,
    simulate_fixture: Path | None = None,
    local_date: date | None = None,
) -> int:
    """
    --simulate-vbs: solo lectura/validación. Cero escrituras al FBL1N productivo,
    cero cscript, cero pipeline, cero publicación, cero correo.
    """

    env_before = os.environ.get("FBL1N_COMPENSATION_CUTOFF")
    future = Path(FBL1N_FUTURE_PATH)
    target: Path
    if simulate_fixture is not None:
        fixture = Path(simulate_fixture)
        if not fixture.is_file():
            raise DiarioAborted(
                f"--simulate-fixture inexistente: {fixture}",
                exit_code=EXIT_CONFIG,
            )
        logger.info(
            "SIMULATE: validando fixture en solo lectura (no se copia a %s): %s",
            future,
            fixture,
        )
        meta = validate_fbl1n_business(fixture, logger)
        target = fixture
        target_label = "fixture"
    else:
        if not future.is_file():
            raise DiarioAborted(
                f"SIMULATE: FBL1N_FUTURE_PATH debe existir para validar: {future}",
                exit_code=EXIT_CONFIG,
            )
        before = {
            "sha256": _sha256_file(future),
            "size": int(future.stat().st_size),
            "mtime_ns": int(future.stat().st_mtime_ns),
        }
        logger.info(
            "SIMULATE: validando futuro productivo en solo lectura sha=%s",
            before["sha256"],
        )
        meta = validate_fbl1n_business(future, logger)
        after = {
            "sha256": _sha256_file(future),
            "size": int(future.stat().st_size),
            "mtime_ns": int(future.stat().st_mtime_ns),
        }
        if after != before:
            raise DiarioAborted(
                "SIMULATE: el futuro cambió durante la validación (no permitido).",
                exit_code=EXIT_UNEXPECTED,
            )
        target = future
        target_label = "future"

    cutoff_info = resolve_and_apply_cutoff_from_source(
        target,
        local_date=local_date or date.today(),
        logger=logger,
        dotenv_path=DOTENV_PATH,
        persist=False,
    )
    # Garantizar que la simulación no deje el env tocado.
    if os.environ.get("FBL1N_COMPENSATION_CUTOFF") != env_before:
        if env_before is None:
            os.environ.pop("FBL1N_COMPENSATION_CUTOFF", None)
        else:
            os.environ["FBL1N_COMPENSATION_CUTOFF"] = env_before
        raise DiarioAborted(
            "SIMULATE: FBL1N_COMPENSATION_CUTOFF en os.environ cambió (no permitido).",
            exit_code=EXIT_UNEXPECTED,
        )

    eff = (
        cutoff_info.effective_compensation_cutoff
        if cutoff_info is not None
        else (
            FBL1N_COMPENSATION_CUTOFF.isoformat()
            if FBL1N_COMPENSATION_CUTOFF is not None
            else "-"
        )
    )
    logger.info(
        "SIMULATION_OK target=%s rows=%s valid_dates=%s sha=%s "
        "effective_compensation_cutoff=%s "
        "(sin VBS, sin pipeline, sin escritura productiva, sin correo)",
        target_label,
        meta["rows"],
        meta["valid_dates"],
        meta["sha256"],
        eff,
    )
    print(f"SIMULATION_OK effective_compensation_cutoff={eff}", flush=True)
    return EXIT_OK


def run_pipeline(logger: logging.Logger) -> tuple[int, ChildProc]:
    """Ejecutar pipeline sin --force; devolver exit code y ChildProc rastreable."""

    cmd = [str(VENV_PYTHON), str(PIPELINE_SCRIPT)]
    logger.info("Pipeline: %s", " ".join(cmd))
    popen = subprocess.Popen(cmd, cwd=str(ROOT))
    child = ChildProc(pid=int(popen.pid), popen=popen)
    logger.info("Pipeline PID hijo=%s", child.pid)
    code = int(popen.wait())
    logger.info("Pipeline exit=%s", code)
    return code, child


def _restore_after_failure(
    *,
    backup: BackupInfo | None,
    future: Path | None,
    future_replaced: bool,
    logger: logging.Logger,
    baseline_office_pids: set[int] | None = None,
    list_pids_fn: Callable[[], set[int]] | None = None,
    terminate_fn: Callable[[int, logging.Logger], bool] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    release_timeout_sec: float = DEFAULT_FILE_RELEASE_TIMEOUT_SEC,
) -> None:
    if not future_replaced or backup is None or future is None:
        return
    term = terminate_fn or _terminate_pid_only
    list_pids = list_pids_fn or list_pids_for_images
    sleeper = sleep_fn or time.sleep
    try:
        terminate_new_pids(
            set(baseline_office_pids or ()),
            list_pids_fn=list_pids,
            terminate_fn=term,
            logger=logger,
            label="EXCEL/saplogon (rollback)",
        )
    except Exception as exc:
        logger.warning("Limpieza office en rollback: %s", exc)
    if future.is_file():
        try:
            wait_until_file_readable(
                future,
                timeout_sec=release_timeout_sec,
                logger=logger,
                sleep_fn=sleeper,
            )
        except Exception as exc:
            logger.warning("Archivo aún no liberado antes del rollback: %s", exc)
    try:
        preserve_failed_future(future, logger)
    except Exception as exc:
        logger.warning("No se pudo conservar evidencia del futuro: %s", exc)
    try:
        restore_future_atomic(backup, logger)
    except Exception as restore_exc:
        logger.error("Rollback del futuro falló: %s", restore_exc)


def run_daily(
    *,
    simulate_vbs: bool = False,
    simulate_fixture: Path | None = None,
    vbs_timeout_sec: float = DEFAULT_VBS_TIMEOUT_SEC,
    logger: logging.Logger | None = None,
    now: datetime | None = None,
    start_cscript_fn: Callable[[Path, logging.Logger], ChildProc] | None = None,
    run_pipeline_fn: Callable[[logging.Logger], tuple[int, ChildProc]] | None = None,
    terminate_fn: Callable[[int, logging.Logger], bool] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    mail_retry_fn: Callable[[logging.Logger], str] | None = None,
    list_pids_fn: Callable[[], set[int]] | None = None,
) -> int:
    stamp = _now_stamp()
    if logger is None:
        logger, log_path = setup_logging(stamp)
    else:
        log_path = Path("(injected)")
    logger.info("=== run_diario start log=%s ===", log_path)
    logger.info("ROOT=%s", ROOT)

    lock: DiarioLock | None = None
    children: list[ChildProc] = []
    backup: BackupInfo | None = None
    future: Path | None = None
    future_replaced = False
    exit_code = EXIT_UNEXPECTED
    term = terminate_fn or _terminate_pid_only
    list_pids = list_pids_fn or list_pids_for_images
    sleeper = sleep_fn or time.sleep
    baseline_office_pids: set[int] = set()

    try:
        # Override de correo ANTES de importar config / lanzar pipeline hijo.
        policy = resolve_mail_day_policy(
            now=now or datetime.now(),
            simulate_vbs=simulate_vbs,
            dotenv_path=DOTENV_PATH,
        )
        apply_mail_day_policy(policy, logger)
        load_project_config()

        lock = DiarioLock()
        lock.acquire(logger)
        vbs = precheck_config(simulate_vbs=simulate_vbs, logger=logger)
        future = Path(FBL1N_FUTURE_PATH)

        # --- Simulación estrictamente no productiva ---
        if simulate_vbs:
            exit_code = run_nonproductive_simulation(
                logger=logger,
                simulate_fixture=simulate_fixture,
                local_date=(now or datetime.now()).date(),
            )
            logger.info("=== run_diario SIMULATION_OK ===")
            return exit_code

        # --- Modo real ---
        baseline_office_pids = set(list_pids())
        logger.info(
            "Baseline EXCEL/saplogon pids=%s",
            sorted(baseline_office_pids),
        )
        backup = backup_future_file(future, logger)
        min_mtime_ns = None
        if future.is_file():
            try:
                min_mtime_ns = int(future.stat().st_mtime_ns) + 1
            except OSError:
                min_mtime_ns = None

        started_monotonic = time.monotonic()
        starter = start_cscript_fn or start_cscript
        child = starter(vbs, logger)
        children.append(child)
        # El VBS puede borrar/reemplazar el futuro desde este momento.
        future_replaced = True

        try:
            stable = wait_stable_new_file(
                future,
                started_monotonic=started_monotonic,
                timeout_sec=vbs_timeout_sec,
                logger=logger,
                min_mtime_ns=min_mtime_ns,
                checks=STABLE_CHECKS,
                interval_sec=STABLE_INTERVAL_SEC,
                sleep_fn=sleeper,
            )
            logger.info("Estabilidad OK meta=%s", stable)
            release_sap_export_holders(
                future=future,
                baseline_office_pids=baseline_office_pids,
                cscript=child,
                terminate_fn=term,
                list_pids_fn=list_pids,
                logger=logger,
                sleep_fn=sleeper,
            )
            meta = validate_fbl1n_business_retrying(
                future,
                logger,
                sleep_fn=sleeper,
            )
            logger.info("Validación OK meta=%s", meta)
            # Cutoff efectivo ANTES del pipeline / retry correo.
            resolve_and_apply_cutoff_from_source(
                future,
                local_date=(now or datetime.now()).date(),
                logger=logger,
                dotenv_path=DOTENV_PATH,
                persist=True,
            )
        except DiarioAborted:
            if child.pid > 0:
                term(child.pid, logger)
            _restore_after_failure(
                backup=backup,
                future=future,
                future_replaced=future_replaced,
                logger=logger,
                baseline_office_pids=baseline_office_pids,
                list_pids_fn=list_pids,
                terminate_fn=term,
                sleep_fn=sleeper,
            )
            future_replaced = False
            if backup is None:
                logger.error(
                    "No había archivo anterior; no se inventa restauración. Abortando."
                )
            raise

        pipeline = run_pipeline_fn or run_pipeline
        code, pipe_child = pipeline(logger)
        children.append(pipe_child)
        if code != 0:
            raise DiarioAborted(
                f"Pipeline exit={code}",
                exit_code=EXIT_PIPELINE,
            )

        # Éxito real: conservar el nuevo futuro (no restaurar).
        future_replaced = False
        retry = mail_retry_fn or maybe_retry_pending_mail
        retry_status = retry(logger)
        logger.info("mail_retry=%s", retry_status)
        logger.info("=== run_diario OK ===")
        exit_code = EXIT_OK
        return exit_code
    except DiarioAborted as exc:
        logger.error("ABORT exit=%s: %s", exc.exit_code, exc)
        exit_code = int(exc.exit_code)
        return exit_code
    except (KeyboardInterrupt, SystemExit) as exc:
        logger.error("Interrupción (%s): restaurando si corresponde", type(exc).__name__)
        exit_code = EXIT_INTERRUPTED
        raise
    except Exception as exc:
        logger.exception("Error no controlado: %s", exc)
        exit_code = EXIT_UNEXPECTED
        return exit_code
    finally:
        child_pids = terminate_registered_children(
            children, terminate_fn=term, logger=logger
        )
        try:
            terminate_new_pids(
                baseline_office_pids,
                list_pids_fn=list_pids,
                terminate_fn=term,
                logger=logger,
                label="EXCEL/saplogon (finally)",
            )
        except Exception as exc:
            logger.warning("Limpieza office finally: %s", exc)
        try:
            release_pipeline_lock_if_child(child_pids, logger)
        except Exception as exc:
            logger.warning("Limpieza pipeline.lock: %s", exc)
        if future_replaced:
            _restore_after_failure(
                backup=backup,
                future=future,
                future_replaced=True,
                logger=logger,
                baseline_office_pids=baseline_office_pids,
                list_pids_fn=list_pids,
                terminate_fn=term,
                sleep_fn=sleeper,
            )
        if lock is not None:
            lock.release(logger)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wrapper diario Operador: VBS → validar futuro → pipeline"
    )
    parser.add_argument(
        "--simulate-vbs",
        action="store_true",
        help=(
            "Simulación no productiva: valida config/futuro (o --simulate-fixture) "
            "en solo lectura. No escribe FBL1N, no VBS, no pipeline, no correo."
        ),
    )
    parser.add_argument(
        "--simulate-fixture",
        type=Path,
        default=None,
        help=(
            "Con --simulate-vbs, validar este xlsx en solo lectura "
            "(nunca se copia al FBL1N productivo)."
        ),
    )
    parser.add_argument(
        "--vbs-timeout-sec",
        type=float,
        default=DEFAULT_VBS_TIMEOUT_SEC,
        help="Timeout esperando FBL1N futuro nuevo (default 2700s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_daily(
            simulate_vbs=bool(args.simulate_vbs),
            simulate_fixture=args.simulate_fixture,
            vbs_timeout_sec=float(args.vbs_timeout_sec),
        )
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return EXIT_INTERRUPTED
        if isinstance(code, int):
            return code if code != 0 else EXIT_INTERRUPTED
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    raise SystemExit(main())
