"""
Orquestador del flujo FBL1N ya validado:

    1. python src/main.py
    2. python scripts/construir_dinamicas_finales.py

No modifica reglas de negocio, clasificacion, matching ni artefactos
mas alla de invocar esos dos comandos y validar sus salidas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook

from ...config.config import (
    CLP_USD_ACREEDOR_CONCEPTO_PATH,
    CONCEPTOS_ADMIN_PATH,
    CONCEPTOS_PATH,
    FBL1N_FUTURE_ENABLED,
    FBL1N_FUTURE_PATH,
    INPUT_DIR,
    MONEDA_PATH,
    OUTPUT_DIR,
    RESOURCES_DIR,
    ROOT_DIR,
    SOCIEDADES_PATH,
    STATE_DIR,
    FBL1N_PATH,
    resolve_log_dir,
    resolve_state_dir,
)
from ...modules.dinamicas_finales.module import (
    ACTUAL_FILENAME,
    EXPECTED_DINAMICAS_SHEETS,
    PAGO_ME_PATH,
)
from ...modules.margen.module import InformeMargenModule
from ...modules.publicacion_final.module import (
    PUBLISH_FAILED,
    PUBLISH_SUCCEEDED,
    PublishAborted,
    load_publish_state,
    needs_publish_retry,
    run_publish,
)
from .mail import (
    MAIL_FAILED,
    MAIL_SUCCEEDED,
    load_mail_state,
    needs_mail_retry,
    run_mail_stage,
)


def _pipeline_state_path(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return resolve_state_dir() / "last_fbl1n_state.json"


def _lock_path(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return resolve_state_dir() / "pipeline.lock"


STATE_PATH = STATE_DIR / "last_fbl1n_state.json"
LOCK_PATH = STATE_DIR / "pipeline.lock"

BI_DIR = INPUT_DIR.parent / "04_BI"
PBIX_FILE = "Dashboard_Validacion_FBL1N.pbix"

STABLE_CHECKS = 3
STABLE_INTERVAL_SEC = 10
STABLE_TIMEOUT_SEC = 300
ONEDRIVE_SETTLE_SEC = 15

STAGE1_TIMEOUT_SEC = 3 * 60 * 60
STAGE2_TIMEOUT_SEC = 1 * 60 * 60

POWERBI_MIN_SHEETS: tuple[str, ...] = (
    "COMB_CLP",
    "NO_COMB_CLP",
    "COMB_USD",
    "NO_COMB_USD",
    "CLP_USD",
    "COMB_GNL CHILE",
    "DATOS_COMB_CLP",
    "DATOS_NO_COMB_CLP",
    "DATOS_COMB_USD",
    "DATOS_NO_COMB_USD",
    "DATOS_CLP_USD",
    "DATOS_COMB_GNL CHILE",
)

REQUIRED_RESOURCES: tuple[Path, ...] = (
    SOCIEDADES_PATH,
    MONEDA_PATH,
    CONCEPTOS_PATH,
    CONCEPTOS_ADMIN_PATH,
    CLP_USD_ACREEDOR_CONCEPTO_PATH,
)

MONTH_LABELS = InformeMargenModule._TD_MONTH_LABELS

_CONC_RE = re.compile(
    r"conciliacion_(registros|importe)_ok=(True|False)",
    re.IGNORECASE,
)
_DUP_RE = re.compile(r"duplicados=(True|False)", re.IGNORECASE)


class PipelineAborted(Exception):
    """Fallo controlado del orquestador (no relanza reglas de negocio)."""


@dataclass
class RunResult:
    status: str
    skipped: bool = False
    message: str = ""
    fbl1n_path: Path | None = None
    sha256: str = ""
    size: int = 0
    mtime: str = ""
    fbl1n_rows: int | None = None
    matrix_rows: int | None = None
    months: list[str] = field(default_factory=list)
    month_labels: list[str] = field(default_factory=list)
    matriz_path: Path | None = None
    dinamicas_path: Path | None = None
    actual_path: Path | None = None
    duration_sec: float = 0.0
    log_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    publish_status: str = ""
    publish_only: bool = False
    mail_status: str = ""
    mail_only: bool = False
    decision: str = ""
    source_mode: str = ""
    combined_source_sha256: str = ""
    future_semantic_sha256: str = ""
    latest_compensation_date: str = ""
    future_valid_rows: int | None = None
    future_invalid_rows: int | None = None


def _setup_run_logger(stamp: str) -> tuple[logging.Logger, Path]:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except OSError:
            pass
    log_dir = resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"actualizacion_automatica_{stamp}.log"
    logger = logging.getLogger("actualizacion_automatica")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger, log_path


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


class PipelineLock:
    """Lock de archivo con PID; elimina candados huérfanos."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = _lock_path(path)
        self._held = False

    def acquire(self) -> None:
        resolve_state_dir().mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            stale = True
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(payload.get("pid", 0))
                if _pid_running(pid) and pid != os.getpid():
                    stale = False
                    raise PipelineAborted(
                        f"Ya hay una ejecución en curso (pid={pid}, lock={self.path})"
                    )
            except PipelineAborted:
                raise
            except Exception:
                stale = True
            if stale:
                try:
                    self.path.unlink()
                except OSError:
                    pass

        payload = {
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass
        self._held = False

    def __enter__(self) -> PipelineLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _is_locked(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r+b"):
            return False
    except OSError:
        return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(path),
    }


def load_state(path: Path | None = None) -> dict[str, Any] | None:
    target = _pipeline_state_path(path)
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(payload: dict[str, Any], path: Path | None = None) -> None:
    target = _pipeline_state_path(path)
    resolve_state_dir().mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def is_same_fbl1n(current: dict[str, Any], last: dict[str, Any] | None) -> bool:
    """Misma versión si coinciden hash y tamaño (mtime de OneDrive se ignora)."""

    if last is None:
        return False
    return (
        current.get("sha256") == last.get("sha256")
        and int(current.get("size") or 0) == int(last.get("size") or 0)
    )


def wait_until_stable(
    path: Path,
    logger: logging.Logger,
    *,
    checks: int = STABLE_CHECKS,
    interval: float = STABLE_INTERVAL_SEC,
    timeout: float = STABLE_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Esperar a que size/mtime no cambien y el archivo sea legible."""

    logger.info(
        "Esperando estabilidad de %s (checks=%d, intervalo=%.0fs, timeout=%.0fs)",
        path,
        checks,
        interval,
        timeout,
    )
    deadline = time.monotonic() + timeout
    previous: tuple[int, int] | None = None
    consecutive = 0

    while time.monotonic() < deadline:
        if not path.exists():
            raise PipelineAborted(f"El archivo desapareció durante la espera: {path}")
        stat = path.stat()
        snap = (int(stat.st_size), int(stat.st_mtime_ns))
        readable = True
        try:
            with path.open("rb") as handle:
                handle.read(64)
        except OSError as exc:
            readable = False
            logger.info("Archivo aún no legible: %s", exc)

        if previous == snap and readable:
            consecutive += 1
            logger.info(
                "Comprobación estable %d/%d size=%d mtime_ns=%d",
                consecutive,
                checks,
                snap[0],
                snap[1],
            )
        else:
            consecutive = 0
            logger.info(
                "Aún inestable o bloqueado size=%d readable=%s",
                snap[0],
                readable,
            )
        if consecutive >= checks:
            fp = fingerprint(path)
            logger.info("FBL1N estable sha256=%s size=%s", fp["sha256"], fp["size"])
            return fp
        previous = snap
        time.sleep(interval)

    raise PipelineAborted(
        f"FBL1N no se estabilizó en {int(timeout)}s (OneDrive aún escribiendo?): {path}"
    )


def _preflight(logger: logging.Logger) -> Path:
    missing: list[str] = []
    for folder, label in (
        (INPUT_DIR, "01_INPUT"),
        (RESOURCES_DIR, "02_RECURSOS"),
        (OUTPUT_DIR, "03_OUTPUT"),
        (BI_DIR, "04_BI"),
    ):
        if not folder.is_dir():
            missing.append(f"{label}: {folder}")

    if not FBL1N_PATH.is_file():
        missing.append(f"FBL1N: {FBL1N_PATH}")
    if not PAGO_ME_PATH.is_file():
        missing.append(f"Pago ME: {PAGO_ME_PATH}")

    for resource in REQUIRED_RESOURCES:
        if not resource.is_file():
            missing.append(f"Recurso: {resource}")

    pbix = BI_DIR / PBIX_FILE
    if BI_DIR.is_dir() and not pbix.is_file():
        logger.warning("Power BI no encontrado (no bloquea): %s", pbix)

    if missing:
        raise PipelineAborted(
            "Validación previa fallida. No se modificará ningún archivo.\n  - "
            + "\n  - ".join(missing)
        )

    actual = OUTPUT_DIR / ACTUAL_FILENAME
    if actual.exists() and _is_locked(actual):
        raise PipelineAborted(
            f"{ACTUAL_FILENAME} está bloqueado (probablemente abierto en Excel). "
            "Cierre el archivo y reintente. No se inició el pipeline."
        )
    if FBL1N_PATH.exists() and _is_locked(FBL1N_PATH):
        raise PipelineAborted(
            f"FBL1N.xlsx está bloqueado. Espere a que OneDrive/Excel lo libere: {FBL1N_PATH}"
        )

    logger.info("Validación previa OK")
    logger.info("FBL1N=%s", FBL1N_PATH)
    logger.info("Pago ME=%s", PAGO_ME_PATH)
    logger.info("OUTPUT=%s", OUTPUT_DIR)
    logger.info("BI=%s", BI_DIR)
    return actual


def _run_stage(
    args: list[str],
    logger: logging.Logger,
    *,
    timeout: int,
    label: str,
) -> str:
    logger.info("Iniciando %s: %s", label, " ".join(args))
    started = time.perf_counter()
    completed = subprocess.run(
        args,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    logger.info("stdout %s:\n%s", label, stdout if stdout.strip() else "(vacio)")
    if stderr.strip():
        logger.info("stderr %s:\n%s", label, stderr)
    logger.info("%s returncode=%s duración=%.1fs", label, completed.returncode, elapsed)
    if completed.returncode != 0:
        raise PipelineAborted(
            f"{label} falló con código {completed.returncode}. "
            f"stderr: {stderr[-2000:]}"
        )
    return stdout + "\n" + stderr


def _newest_after(
    directory: Path,
    pattern: str,
    after_mtime: float,
    *,
    exclude: frozenset[str] = frozenset(),
) -> Path | None:
    candidates = [
        path
        for path in directory.glob(pattern)
        if path.name not in exclude and path.stat().st_mtime + 0.5 >= after_mtime
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _month_label(period: str) -> str:
    text = str(period).strip()
    mapped = InformeMargenModule._month_label_from_period(text)
    return mapped or text


def _validate_matrix(
    matriz_path: Path,
    fbl1n_path: Path,
    logger: logging.Logger,
) -> tuple[int, int, list[str], list[str]]:
    logger.info("Validando matriz %s", matriz_path)
    if not matriz_path.is_file() or matriz_path.stat().st_size <= 0:
        raise PipelineAborted(f"MATRIZ inexistente o vacía: {matriz_path}")

    matrix = pd.read_excel(
        matriz_path,
        sheet_name="MATRIZ_FBL1N",
        usecols=["mes_compensacion"],
        engine="calamine",
    )
    if matrix.empty:
        raise PipelineAborted(f"MATRIZ sin filas: {matriz_path}")

    fbl = pd.read_excel(fbl1n_path, usecols=["Fecha compensación"])
    fbl_rows = int(len(fbl))
    matrix_rows = int(len(matrix))
    logger.info("Filas FBL1N=%d  MATRIZ=%d", fbl_rows, matrix_rows)
    if fbl_rows != matrix_rows:
        logger.warning(
            "Las filas de FBL1N (%d) y MATRIZ (%d) no coinciden.",
            fbl_rows,
            matrix_rows,
        )

    fbl_months = (
        pd.to_datetime(fbl["Fecha compensación"], errors="coerce")
        .dt.strftime("%Y-%m")
        .dropna()
    )
    mat_months = matrix["mes_compensacion"].fillna("").astype(str).str.strip()
    fbl_set = {item for item in fbl_months.unique().tolist() if item and item != "NaT"}
    mat_set = {item for item in mat_months.unique().tolist() if item}
    missing = sorted(fbl_set - mat_set)
    if missing:
        logger.warning(
            "FBL1N tiene meses que no aparecen en la MATRIZ: %s",
            ", ".join(missing),
        )
    months = sorted(mat_set)
    labels = [_month_label(item) for item in months]
    logger.info("Meses MATRIZ: %s", ", ".join(labels) if labels else "(ninguno)")
    return fbl_rows, matrix_rows, months, labels


def _workbook_sheets(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def _parse_audit_flags(output: str, logger: logging.Logger) -> None:
    conc_hits = _CONC_RE.findall(output)
    dup_hits = _DUP_RE.findall(output)
    logger.info("Indicadores conciliacion encontrados: %s", conc_hits)
    logger.info("Indicadores duplicados encontrados: %s", dup_hits)

    if not conc_hits:
        raise PipelineAborted(
            "No se encontraron conciliacion_registros_ok / conciliacion_importe_ok "
            "en la salida de dinámicas."
        )
    failed = [f"conciliacion_{name}_ok={value}" for name, value in conc_hits if value != "True"]
    if failed:
        raise PipelineAborted(
            "Conciliación fallida: " + ", ".join(failed)
        )
    if not dup_hits:
        raise PipelineAborted(
            "No se encontró el indicador duplicados=True/False en la salida de dinámicas."
        )
    if any(value.lower() == "true" for value in dup_hits):
        raise PipelineAborted(f"Duplicados reportados en dinámicas: {dup_hits}")


def _validate_dinamicas(
    historico: Path,
    actual: Path,
    stage2_started: float,
    stage2_output: str,
    logger: logging.Logger,
) -> None:
    if historico is None or not historico.is_file() or historico.stat().st_size <= 0:
        raise PipelineAborted("No se generó DINAMICAS_FINALES_<timestamp>.xlsx")
    if not actual.is_file() or actual.stat().st_size <= 0:
        raise PipelineAborted(f"No se actualizó {ACTUAL_FILENAME}")
    if actual.stat().st_mtime + 0.5 < stage2_started:
        raise PipelineAborted(
            f"{ACTUAL_FILENAME} no tiene mtime posterior a la etapa 2 "
            f"(mtime={datetime.fromtimestamp(actual.stat().st_mtime)})"
        )

    names = set(_workbook_sheets(actual))
    missing_expected = sorted(EXPECTED_DINAMICAS_SHEETS - names)
    missing_powerbi = [name for name in POWERBI_MIN_SHEETS if name not in names]
    if missing_expected:
        raise PipelineAborted(
            "ACTUAL incompleto; faltan hojas: " + ", ".join(missing_expected)
        )
    if missing_powerbi:
        raise PipelineAborted(
            "ACTUAL no tiene hojas mínimas de Power BI: " + ", ".join(missing_powerbi)
        )
    logger.info("Hojas ACTUAL (%d): %s", len(names), ", ".join(sorted(names)))
    _parse_audit_flags(stage2_output, logger)


def _python_exe() -> str:
    venv_exe = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_exe.is_file():
        return str(venv_exe)
    return sys.executable


def format_summary(result: RunResult) -> str:
    months = ", ".join(result.month_labels) if result.month_labels else "-"
    filas = result.matrix_rows if result.matrix_rows is not None else result.fbl1n_rows
    if result.skipped:
        actual_txt = "sin cambios"
    elif result.status == "OK" and result.message.startswith("cambio detectado"):
        actual_txt = "no actualizado (detect-only)"
    elif result.status == "OK":
        actual_txt = "actualizado"
    else:
        actual_txt = "no actualizado"
    return "\n".join(
        [
            "============================================================",
            "ACTUALIZACIÓN FBL1N",
            "============================================================",
            f"Estado: {result.status}",
            f"FBL1N: {result.fbl1n_path or '-'}",
            f"Filas: {filas if filas is not None else '-'}",
            f"Meses: {months}",
            f"Matriz: {result.matriz_path or '-'}",
            f"Dinámica: {result.dinamicas_path or '-'}",
            f"ACTUAL: {actual_txt}",
            f"Publicación: {result.publish_status or '-'}",
            f"Correo: {result.mail_status or '-'}",
            f"Duración: {result.duration_sec:.1f}s",
            "============================================================",
        ]
    )


def _apply_last_pipeline_paths(result: RunResult, last: dict[str, Any] | None, actual_path: Path) -> None:
    result.matriz_path = Path(last["matriz"]) if last and last.get("matriz") else None
    result.dinamicas_path = (
        Path(last["dinamicas"]) if last and last.get("dinamicas") else None
    )
    result.actual_path = Path(last["actual"]) if last and last.get("actual") else actual_path
    result.fbl1n_rows = last.get("fbl1n_rows") if last else None
    result.matrix_rows = last.get("matrix_rows") if last else None
    result.months = list(last.get("months") or []) if last else []
    result.month_labels = [_month_label(item) for item in result.months]


def _run_publish_step(
    result: RunResult,
    sha256: str,
    logger: logging.Logger,
    *,
    publish_only: bool,
) -> None:
    logger.info(
        "Iniciando publicación final (publish_only=%s sha256=%s)",
        publish_only,
        sha256,
    )
    result.publish_only = publish_only
    try:
        published = run_publish(sha256, logger)
    except PublishAborted as exc:
        result.publish_status = PUBLISH_FAILED
        raise PipelineAborted(
            "Pipeline técnico no se reejecuta. Publicación Failed: " + str(exc)
        ) from exc
    result.publish_status = published.status
    if published.status != PUBLISH_SUCCEEDED:
        raise PipelineAborted(
            "Pipeline técnico no se reejecuta. Publicación Failed: "
            + (published.error or published.status)
        )
    logger.info("Publicación final Succeeded para hash %s", sha256)


def _run_mail_step(
    result: RunResult,
    sha256: str,
    logger: logging.Logger,
    *,
    mail_only: bool,
    latest_compensation_date: str | None = None,
) -> None:
    logger.info(
        "Iniciando etapa correo (mail_only=%s sha256=%s). "
        "Display no autorizado. Send solo si MAIL_AUTO_SEND=true.",
        mail_only,
        sha256,
    )
    iso_date = str(
        latest_compensation_date or result.latest_compensation_date or ""
    ).strip() or None
    staged = run_mail_stage(
        sha256,
        logger,
        months=list(result.months or []),
        latest_compensation_date=iso_date,
        decision=result.decision or None,
        publish_ok=result.publish_status == PUBLISH_SUCCEEDED,
    )
    result.mail_status = staged.status
    result.mail_only = mail_only
    logger.info("Etapa correo: status=%s message=%s", staged.status, staged.message)


def _stable_wait_kwargs() -> dict[str, Any]:
    """Overrides opcionales de estabilidad; vacío → constantes productivas."""

    kwargs: dict[str, Any] = {}
    checks_raw = os.getenv("FBL1N_STABLE_CHECKS", "").strip()
    interval_raw = os.getenv("FBL1N_STABLE_INTERVAL_SEC", "").strip()
    timeout_raw = os.getenv("FBL1N_STABLE_TIMEOUT_SEC", "").strip()
    if checks_raw:
        kwargs["checks"] = int(checks_raw)
    if interval_raw:
        kwargs["interval"] = float(interval_raw)
    if timeout_raw:
        kwargs["timeout"] = float(timeout_raw)
    return kwargs


def _attach_source_decision(result: RunResult, decision: Any) -> None:
    result.decision = str(decision.status or "")
    result.source_mode = str(decision.source_mode or "")
    result.combined_source_sha256 = str(decision.combined_source_sha256 or "")
    result.future_semantic_sha256 = str(decision.future_semantic_sha256 or "")
    result.latest_compensation_date = str(decision.latest_compensation_date or "")
    result.future_valid_rows = int(decision.future_valid_rows or 0)
    result.future_invalid_rows = int(decision.future_invalid_rows or 0)


def _detect_future_source(
    logger: logging.Logger,
    historical_fp: dict[str, Any],
    last: dict[str, Any] | None,
    historical_df: Any,
) -> Any:
    from ...loaders.excel_loader import ExcelLoader
    from ..fbl1n_fuentes.detection import plan_source_detection

    path = Path(FBL1N_FUTURE_PATH)
    name = path.name or "FBL1N_FUTURO.xlsx"
    if not path.exists() or not path.is_file():
        return plan_source_detection(
            future_enabled=True,
            historical_fp=historical_fp,
            last=last,
            historical_df=historical_df,
            future_available=False,
            future_error=f"El archivo FBL1N futuro no está disponible: {name}.",
            logger=logger,
        )
    if _is_locked(path):
        return plan_source_detection(
            future_enabled=True,
            historical_fp=historical_fp,
            last=last,
            historical_df=historical_df,
            future_available=False,
            future_error=f"El archivo FBL1N futuro está bloqueado o no es estable: {name}.",
            logger=logger,
        )
    try:
        future_fp = wait_until_stable(path, logger, **_stable_wait_kwargs())
        future_df = ExcelLoader().load_fbl1n(path)
    except PipelineAborted:
        return plan_source_detection(
            future_enabled=True,
            historical_fp=historical_fp,
            last=last,
            historical_df=historical_df,
            future_available=False,
            future_error=f"El archivo FBL1N futuro no se estabilizó: {name}.",
            logger=logger,
        )
    except Exception:
        return plan_source_detection(
            future_enabled=True,
            historical_fp=historical_fp,
            last=last,
            historical_df=historical_df,
            future_available=False,
            future_error=f"El archivo FBL1N futuro no es legible: {name}.",
            logger=logger,
        )
    return plan_source_detection(
        future_enabled=True,
        historical_fp=historical_fp,
        last=last,
        historical_df=historical_df,
        future_df=future_df,
        future_file_sha256=str(future_fp.get("sha256") or ""),
        logger=logger,
    )


def run_actualizacion(*, force: bool = False, detect_only: bool = False) -> RunResult:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger, log_path = _setup_run_logger(stamp)
    wall_started = time.perf_counter()
    started_at = datetime.now()
    result = RunResult(status="ERROR", log_path=log_path)

    logger.info("=" * 60)
    logger.info("Inicio orquestador actualizacion automatica")
    logger.info("force=%s detect_only=%s pid=%s", force, detect_only, os.getpid())
    logger.info("=" * 60)

    lock = PipelineLock()
    try:
        lock.acquire()
        actual_path = _preflight(logger)
        result.actual_path = actual_path
        result.fbl1n_path = FBL1N_PATH

        fp = wait_until_stable(FBL1N_PATH, logger, **_stable_wait_kwargs())
        result.sha256 = str(fp["sha256"])
        result.size = int(fp["size"])
        result.mtime = str(fp["mtime"])
        logger.info(
            "FBL1N detectado path=%s size=%s mtime=%s sha256=%s",
            fp["path"],
            fp["size"],
            fp["mtime"],
            fp["sha256"],
        )

        last = load_state()
        publish_sha = str(fp["sha256"])
        future_decision = None

        if FBL1N_FUTURE_ENABLED:
            from ..fbl1n_fuentes.detection import (
                DECISION_FAILED,
                DECISION_HISTORICAL_ANOMALY,
                DECISION_NODATA,
            )

            logger.info("Modo FBL1N futuro habilitado; detección semántica combinada")
            from ...loaders.excel_loader import ExcelLoader

            try:
                historical_df = ExcelLoader().load_fbl1n(FBL1N_PATH)
            except Exception as exc:
                raise PipelineAborted(
                    f"El FBL1N histórico no es legible: {exc}"
                ) from exc
            future_decision = _detect_future_source(
                logger, fp, last, historical_df
            )
            _attach_source_decision(result, future_decision)
            if future_decision.status in {
                DECISION_FAILED,
                DECISION_HISTORICAL_ANOMALY,
            }:
                raise PipelineAborted(future_decision.message)
            if future_decision.status == DECISION_NODATA:
                _apply_last_pipeline_paths(result, last, actual_path)
                result.status = "OK"
                result.skipped = True
                result.message = future_decision.message
                result.duration_sec = time.perf_counter() - wall_started
                logger.info(
                    "NoData: sin MATRIZ, sin DINÁMICAS, sin publicación, sin correo"
                )
                logger.info("Resultado final: OK (NoData)")
                print(format_summary(result), flush=True)
                return result
            publish_sha = str(future_decision.source_fbl1n_sha256 or "")
            logger.info(
                "Identidad combinada lista; publicación/correo usarán alias compatible"
            )

        same_source = (
            future_decision is not None
            and future_decision.status == "Unchanged"
        ) if FBL1N_FUTURE_ENABLED else is_same_fbl1n(fp, last)

        if not force and same_source:
            _apply_last_pipeline_paths(result, last, actual_path)
            if detect_only:
                result.status = "OK"
                result.skipped = True
                result.message = "sin cambios (detect-only)"
                result.duration_sec = time.perf_counter() - wall_started
                logger.info(
                    "detect-only: no pipeline, no publicación, no correo, no state"
                )
                print(format_summary(result), flush=True)
                return result
            publish_state = load_publish_state()
            prior_status = (
                str(publish_state.get("publish_status") or "") if publish_state else "(ausente)"
            )
            logger.info(
                "FBL1N combinado sin cambios semánticos. publish_status previo=%s"
                if FBL1N_FUTURE_ENABLED
                else "FBL1N sin cambios (sha256+size). publish_status previo=%s",
                prior_status,
            )
            if not needs_publish_retry(publish_sha):
                result.publish_status = PUBLISH_SUCCEEDED
                mail_state = load_mail_state()
                prior_mail = (
                    str(mail_state.get("mail_status") or "") if mail_state else "(ausente)"
                )
                logger.info("publish_status=Succeeded. mail_status previo=%s", prior_mail)
                if FBL1N_FUTURE_ENABLED:
                    logger.info(
                        "Modo futuro Unchanged: no se construye ni envía correo"
                    )
                    result.status = "OK"
                    result.skipped = True
                    if not needs_mail_retry(publish_sha):
                        result.mail_status = MAIL_SUCCEEDED
                        result.message = "sin cambios"
                    else:
                        result.message = "sin cambios; correo no aplica (Unchanged)"
                    result.duration_sec = time.perf_counter() - wall_started
                    logger.info("Resultado final: OK (sin cambios; correo no aplica)")
                    print(format_summary(result), flush=True)
                    return result
                if not needs_mail_retry(publish_sha):
                    result.status = "OK"
                    result.skipped = True
                    result.message = "sin cambios"
                    result.mail_status = MAIL_SUCCEEDED
                    result.duration_sec = time.perf_counter() - wall_started
                    logger.info(
                        "Skip total: mismo FBL1N, publicación Succeeded y correo "
                        "Succeeded para el mismo hash."
                    )
                    logger.info("Resultado final: OK (sin cambios)")
                    print(format_summary(result), flush=True)
                    return result

                logger.info(
                    "Mismo FBL1N y publicación Succeeded; etapa correo pendiente "
                    "(no src/main.py, no MATRIZ, no DINÁMICAS, no publicación)."
                )
                _run_mail_step(
                    result,
                    publish_sha,
                    logger,
                    mail_only=True,
                )
                result.status = "OK"
                result.skipped = True
                if result.mail_status == MAIL_SUCCEEDED:
                    result.message = "sin cambios; correo enviado"
                    logger.info(
                        "Resultado final: OK (pipeline y publicación omitidos; correo enviado)"
                    )
                elif result.mail_status == MAIL_FAILED:
                    result.message = "sin cambios; correo Failed"
                    logger.info(
                        "Resultado final: OK (pipeline y publicación omitidos; correo Failed)"
                    )
                else:
                    result.message = "sin cambios; correo pendiente/no ejecutado"
                    logger.info(
                        "Resultado final: OK (pipeline y publicación omitidos; correo no enviado)"
                    )
                result.duration_sec = time.perf_counter() - wall_started
                print(format_summary(result), flush=True)
                return result

            logger.info(
                "Mismo FBL1N; se reintenta únicamente publicación final "
                "(no src/main.py, no MATRIZ, no DINÁMICAS)."
            )
            _run_publish_step(
                result,
                publish_sha,
                logger,
                publish_only=True,
            )
            result.status = "OK"
            result.skipped = True
            result.message = "sin cambios; publicación recuperada"
            result.duration_sec = time.perf_counter() - wall_started
            logger.info("Resultado final: OK (pipeline omitido; publicación Succeeded)")
            print(format_summary(result), flush=True)
            return result

        if detect_only:
            result.status = "OK"
            result.skipped = False
            result.message = "cambio detectado (detect-only)"
            result.matriz_path = Path(last["matriz"]) if last and last.get("matriz") else None
            result.dinamicas_path = (
                Path(last["dinamicas"]) if last and last.get("dinamicas") else None
            )
            logger.info(
                "CAMBIO DETECTADO en FBL1N (sha256/size distintos). "
                "--detect-only: no se ejecuta el pipeline."
            )
            result.duration_sec = time.perf_counter() - wall_started
            logger.info("Resultado final: OK (cambio detectado, detect-only)")
            print(format_summary(result), flush=True)
            return result

        python = _python_exe()

        stage1_started = time.time()
        _run_stage(
            [python, str(ROOT_DIR / "src" / "main.py")],
            logger,
            timeout=STAGE1_TIMEOUT_SEC,
            label="Etapa 1 src/main.py",
        )
        matriz = _newest_after(OUTPUT_DIR, "MATRIZ_FBL1N_*.xlsx", stage1_started)
        if matriz is None:
            raise PipelineAborted(
                "Etapa 1 terminó pero no apareció una MATRIZ_FBL1N_<timestamp>.xlsx nueva"
            )
        result.matriz_path = matriz
        logger.info("Matriz generada: %s", matriz)

        fbl_rows, matrix_rows, months, labels = _validate_matrix(
            matriz, FBL1N_PATH, logger
        )
        result.fbl1n_rows = fbl_rows
        result.matrix_rows = matrix_rows
        result.months = months
        result.month_labels = labels

        stage2_started = time.time()
        stage2_output = _run_stage(
            [python, str(ROOT_DIR / "scripts" / "construir_dinamicas_finales.py")],
            logger,
            timeout=STAGE2_TIMEOUT_SEC,
            label="Etapa 2 construir_dinamicas_finales.py",
        )
        dinamicas = _newest_after(
            OUTPUT_DIR,
            "DINAMICAS_FINALES_*.xlsx",
            stage2_started,
            exclude=frozenset({ACTUAL_FILENAME}),
        )
        if dinamicas is None:
            raise PipelineAborted(
                "Etapa 2 terminó pero no apareció DINAMICAS_FINALES_<timestamp>.xlsx"
            )
        result.dinamicas_path = dinamicas
        logger.info("Dinámica histórica generada: %s", dinamicas)

        _validate_dinamicas(
            dinamicas,
            actual_path,
            stage2_started,
            stage2_output,
            logger,
        )
        result.actual_path = actual_path

        logger.info(
            "Publicación local lista. Esperando %.0fs por settle de OneDrive (sin Graph).",
            ONEDRIVE_SETTLE_SEC,
        )
        time.sleep(ONEDRIVE_SETTLE_SEC)
        if not actual_path.is_file() or _is_locked(actual_path):
            raise PipelineAborted(
                f"{ACTUAL_FILENAME} no quedó accesible tras la espera OneDrive"
            )
        logger.info("ACTUAL accesible tras settle local: %s", actual_path)
        logger.info("Datos listos para actualización de Power BI (%s)", BI_DIR / PBIX_FILE)

        if future_decision is not None:
            from ..fbl1n_fuentes.detection import build_combined_state_payload

            state_payload = build_combined_state_payload(
                historical_fp=fp,
                decision=future_decision,
                started_at=started_at.isoformat(timespec="seconds"),
                last_success_at=datetime.now().isoformat(timespec="seconds"),
                fbl1n_rows=fbl_rows,
                matrix_rows=matrix_rows,
                months=months,
                matriz=str(matriz),
                dinamicas=str(dinamicas),
                actual=str(actual_path),
                log=str(log_path),
            )
        else:
            state_payload = {
                **fp,
                "last_success_at": datetime.now().isoformat(timespec="seconds"),
                "started_at": started_at.isoformat(timespec="seconds"),
                "fbl1n_rows": fbl_rows,
                "matrix_rows": matrix_rows,
                "months": months,
                "matriz": str(matriz),
                "dinamicas": str(dinamicas),
                "actual": str(actual_path),
                "log": str(log_path),
            }
        save_state(state_payload)
        logger.info("Estado pipeline guardado en %s", STATE_PATH)

        _run_publish_step(
            result,
            publish_sha,
            logger,
            publish_only=False,
        )

        _run_mail_step(
            result,
            publish_sha,
            logger,
            mail_only=False,
        )

        result.status = "OK"
        result.message = "actualizado"
        result.duration_sec = time.perf_counter() - wall_started

        mail_body = format_summary(result)
        logger.info("Resultado final: OK")
        print(mail_body, flush=True)
        return result

    except subprocess.TimeoutExpired as exc:
        result.errors.append(str(exc))
        logger.exception("Timeout de etapa")
        result.duration_sec = time.perf_counter() - wall_started
        print(format_summary(result), flush=True)
        raise PipelineAborted(f"Timeout: {exc}") from exc
    except PipelineAborted as exc:
        result.errors.append(str(exc))
        result.message = str(exc)
        logger.error("ERROR: %s", exc)
        result.duration_sec = time.perf_counter() - wall_started
        print(format_summary(result), flush=True)
        raise
    except Exception as exc:
        result.errors.append(str(exc))
        result.message = str(exc)
        logger.exception("Error inesperado del orquestador")
        result.duration_sec = time.perf_counter() - wall_started
        print(format_summary(result), flush=True)
        raise PipelineAborted(str(exc)) from exc
    finally:
        lock.release()
        logger.info("Lock liberado. Fin orquestador (status=%s)", result.status)
