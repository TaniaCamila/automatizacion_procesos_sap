"""
Publicación final hacia REPORTE QUERY MENSUAL.

Copia (nunca mueve) DINAMICAS_FINALES_ACTUAL.xlsx y el archivo de pago ME
hacia la carpeta de usuarios. PROVEEDORES.xlsx solo se valida.

Transacción compensada mediante rollback (no atomicidad multiarchivo real).
No modifica 01_INPUT, 03_OUTPUT ni PROVEEDORES.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from ...config.config import OUTPUT_DIR, PUBLICATION_DIR, resolve_state_dir
from ...modules.dinamicas_finales.module import (
    ACTUAL_FILENAME,
    EXPECTED_DINAMICAS_SHEETS,
    PAGO_ME_PATH,
)

def publish_state_path(path: Path | None = None) -> Path:
    """Ruta de last_publish_state.json según RUTA_STATE actual."""

    if path is not None:
        return Path(path)
    return resolve_state_dir() / "last_publish_state.json"


# Compatibilidad: valor al import. Las funciones operativas usan publish_state_path().
PUBLISH_STATE_PATH = publish_state_path()

PUBLISH_PENDING = "Pending"
PUBLISH_SUCCEEDED = "Succeeded"
PUBLISH_FAILED = "Failed"

DINAMICAS_DEST_NAME = "DINAMICAS_FINALES_ACTUAL.xlsx"
PAGO_ME_DEST_NAME = "PAGO_MONEDA_EXTRANJERA.xlsx"
PROVEEDORES_NAME = "PROVEEDORES.xlsx"
PUBLISHED_FILE_NAMES: tuple[str, ...] = (
    DINAMICAS_DEST_NAME,
    PAGO_ME_DEST_NAME,
    PROVEEDORES_NAME,
)

TMP_DINAMICAS_NAME = ".DINAMICAS_FINALES_ACTUAL.tmp.xlsx"
TMP_PAGO_NAME = ".PAGO_MONEDA_EXTRANJERA.tmp.xlsx"
BAK_DINAMICAS_NAME = ".DINAMICAS_FINALES_ACTUAL.bak.xlsx"
BAK_PAGO_NAME = ".PAGO_MONEDA_EXTRANJERA.bak.xlsx"

ONEDRIVE_SETTLE_SEC = 15
COPY_RETRIES = 5
COPY_RETRY_WAIT_SEC = 2


class PublishAborted(Exception):
    """Fallo controlado de la publicación final."""


@dataclass
class PublishResult:
    status: str
    source_fbl1n_sha256: str = ""
    published_files: list[str] = field(default_factory=list)
    error: str = ""
    publish_at: str = ""


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


def load_publish_state(path: Path | None = None) -> dict[str, Any] | None:
    target = publish_state_path(path)
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_publish_state(
    payload: dict[str, Any],
    path: Path | None = None,
) -> None:
    target = publish_state_path(path)
    resolve_state_dir().mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def needs_publish_retry(fbl1n_sha256: str) -> bool:
    """True si no hay publicación Succeeded vinculada a este hash."""

    state = load_publish_state()
    if state is None:
        return True
    stored = str(state.get("source_fbl1n_sha256") or "")
    if stored != str(fbl1n_sha256 or ""):
        return True
    return str(state.get("publish_status") or "") != PUBLISH_SUCCEEDED


def _write_status(
    *,
    sha256: str,
    status: str,
    error: str | None,
    published_files: list[str] | None = None,
    logger: logging.Logger,
) -> dict[str, Any]:
    payload = {
        "source_fbl1n_sha256": sha256,
        "publish_status": status,
        "publish_at": datetime.now().isoformat(timespec="seconds"),
        "published_files": list(published_files or []),
        "publish_error": error,
    }
    save_publish_state(payload)
    logger.info(
        "Estado publicación guardado status=%s hash=%s error=%s",
        status,
        sha256,
        error or "(ninguno)",
    )
    return payload


def _excel_sheet_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def _validate_readable_excel(path: Path, label: str) -> list[str]:
    if not path.is_file():
        raise PublishAborted(f"{label} inexistente: {path}")
    if path.stat().st_size <= 0:
        raise PublishAborted(f"{label} vacío (size=0): {path}")
    try:
        names = _excel_sheet_names(path)
    except Exception as exc:
        raise PublishAborted(f"{label} no es un Excel legible: {path} ({exc})") from exc
    if not names:
        raise PublishAborted(f"{label} no tiene hojas: {path}")
    return names


def _validate_dinamicas(path: Path, label: str) -> list[str]:
    names = _validate_readable_excel(path, label)
    missing = sorted(EXPECTED_DINAMICAS_SHEETS - set(names))
    if missing:
        raise PublishAborted(
            f"{label} incompleto; faltan hojas: " + ", ".join(missing)
        )
    return names


def _validate_proveedores(path: Path) -> list[str]:
    """Solo lectura. No abre en modo escritura; no debe alterar mtime/hash."""

    if not path.is_file():
        raise PublishAborted(f"PROVEEDORES inexistente: {path}")
    if path.stat().st_size <= 0:
        raise PublishAborted(f"PROVEEDORES vacío (size=0): {path}")
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
        if not header:
            raise PublishAborted(f"PROVEEDORES ilegible: {path}")
        names = _excel_sheet_names(path)
    except PublishAborted:
        raise
    except Exception as exc:
        raise PublishAborted(
            f"PROVEEDORES no es un Excel legible/no corrupto: {path} ({exc})"
        ) from exc
    if not names:
        raise PublishAborted(f"PROVEEDORES sin hojas: {path}")
    return names


def _copy_with_retry(source: Path, dest: Path, logger: logging.Logger) -> None:
    last_error: OSError | None = None
    for attempt in range(1, COPY_RETRIES + 1):
        try:
            shutil.copy2(source, dest)
            return
        except PermissionError as exc:
            last_error = exc
            logger.warning(
                "PermissionError copiando %s → %s (intento %d/%d): %s",
                source.name,
                dest.name,
                attempt,
                COPY_RETRIES,
                exc,
            )
            time.sleep(COPY_RETRY_WAIT_SEC)
    raise PublishAborted(
        f"No se pudo copiar {source} → {dest} tras {COPY_RETRIES} intentos: {last_error}"
    )


def _replace_with_retry(source: Path, dest: Path, logger: logging.Logger) -> None:
    last_error: OSError | None = None
    for attempt in range(1, COPY_RETRIES + 1):
        try:
            os.replace(source, dest)
            return
        except PermissionError as exc:
            last_error = exc
            logger.warning(
                "PermissionError replace %s → %s (intento %d/%d): %s",
                source.name,
                dest.name,
                attempt,
                COPY_RETRIES,
                exc,
            )
            time.sleep(COPY_RETRY_WAIT_SEC)
    raise PublishAborted(
        f"No se pudo reemplazar {dest} tras {COPY_RETRIES} intentos: {last_error}"
    )


def _unlink_quiet(path: Path, logger: logging.Logger) -> None:
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        logger.warning("No se pudo eliminar %s: %s", path, exc)


def run_publish(
    source_fbl1n_sha256: str,
    logger: logging.Logger,
    *,
    publication_dir: Path | None = None,
) -> PublishResult:
    """
    Publicar copias finales. Transacción compensada mediante rollback.

    No mueve ni modifica originales de 01_INPUT / 03_OUTPUT / PROVEEDORES.
    """

    sha = str(source_fbl1n_sha256 or "").strip()
    if not sha:
        raise PublishAborted("source_fbl1n_sha256 vacío; no se publica.")

    dest_dir = Path(publication_dir) if publication_dir else PUBLICATION_DIR
    origin_dinamicas = OUTPUT_DIR / ACTUAL_FILENAME
    origin_pago = PAGO_ME_PATH
    dest_dinamicas = dest_dir / DINAMICAS_DEST_NAME
    dest_pago = dest_dir / PAGO_ME_DEST_NAME
    dest_proveedores = dest_dir / PROVEEDORES_NAME
    tmp_dinamicas = dest_dir / TMP_DINAMICAS_NAME
    tmp_pago = dest_dir / TMP_PAGO_NAME
    bak_dinamicas = dest_dir / BAK_DINAMICAS_NAME
    bak_pago = dest_dir / BAK_PAGO_NAME

    result = PublishResult(status=PUBLISH_FAILED, source_fbl1n_sha256=sha)
    replaced_dinamicas = False
    had_dest_dinamicas = dest_dinamicas.is_file()
    restored = False

    logger.info("=" * 60)
    logger.info("Inicio publicación final (transacción compensada mediante rollback)")
    logger.info("source_fbl1n_sha256=%s", sha)
    logger.info("Destino: %s", dest_dir)
    logger.info("Origen DINÁMICAS: %s", origin_dinamicas)
    logger.info("Origen PAGO ME: %s", origin_pago)
    logger.info("PROVEEDORES (solo validar): %s", dest_proveedores)
    logger.info("=" * 60)

    _write_status(sha256=sha, status=PUBLISH_PENDING, error=None, logger=logger)

    try:
        if not dest_dir.is_dir():
            raise PublishAborted(f"Carpeta de publicación inexistente: {dest_dir}")

        logger.info("Validando origen DINÁMICAS")
        if _is_locked(origin_dinamicas):
            raise PublishAborted(f"Origen DINÁMICAS bloqueado: {origin_dinamicas}")
        din_sheets = _validate_dinamicas(origin_dinamicas, "Origen DINÁMICAS")
        logger.info("DINÁMICAS origen OK hojas=%d", len(din_sheets))

        logger.info("Validando origen PAGO MONEDA EXTRANJERA")
        if _is_locked(origin_pago):
            raise PublishAborted(f"Origen PAGO ME bloqueado: {origin_pago}")
        pago_sheets = _validate_readable_excel(origin_pago, "Origen PAGO ME")
        logger.info("PAGO ME origen OK hojas=%s", ", ".join(pago_sheets))

        logger.info("Validando PROVEEDORES (sin modificar)")
        prov_sheets = _validate_proveedores(dest_proveedores)
        logger.info("PROVEEDORES OK hojas=%s size=%s", ", ".join(prov_sheets), dest_proveedores.stat().st_size)

        if dest_dinamicas.exists() and _is_locked(dest_dinamicas):
            raise PublishAborted(
                f"Destino DINÁMICAS bloqueado (probablemente abierto en Excel): {dest_dinamicas}"
            )
        if dest_pago.exists() and _is_locked(dest_pago):
            raise PublishAborted(
                f"Destino PAGO_MONEDA_EXTRANJERA bloqueado: {dest_pago}"
            )

        for leftover in (tmp_dinamicas, tmp_pago, bak_dinamicas, bak_pago):
            _unlink_quiet(leftover, logger)

        logger.info("Creando temporales en %s", dest_dir)
        _copy_with_retry(origin_dinamicas, tmp_dinamicas, logger)
        _copy_with_retry(origin_pago, tmp_pago, logger)
        logger.info("Temporales creados")

        logger.info("Validando temporales")
        _validate_dinamicas(tmp_dinamicas, "Temporal DINÁMICAS")
        _validate_readable_excel(tmp_pago, "Temporal PAGO ME")
        logger.info("Temporales OK")

        if had_dest_dinamicas:
            logger.info("Backup destino DINÁMICAS → %s", bak_dinamicas.name)
            _copy_with_retry(dest_dinamicas, bak_dinamicas, logger)
        if dest_pago.is_file():
            logger.info("Backup destino PAGO ME → %s", bak_pago.name)
            _copy_with_retry(dest_pago, bak_pago, logger)

        logger.info("Reemplazo final DINÁMICAS (os.replace)")
        _replace_with_retry(tmp_dinamicas, dest_dinamicas, logger)
        replaced_dinamicas = True
        logger.info("Reemplazo final PAGO ME (os.replace)")
        try:
            _replace_with_retry(tmp_pago, dest_pago, logger)
        except Exception:
            logger.error(
                "Falló el segundo replace; rollback compensado del primero"
            )
            if had_dest_dinamicas and bak_dinamicas.is_file():
                _replace_with_retry(bak_dinamicas, dest_dinamicas, logger)
                restored = True
                logger.info("Rollback: restaurada DINÁMICAS desde backup")
            elif dest_dinamicas.is_file():
                _unlink_quiet(dest_dinamicas, logger)
                restored = True
                logger.info("Rollback: eliminada DINÁMICAS destino nueva (no había versión previa)")
            raise

        logger.info(
            "Esperando %.0fs por settle de OneDrive (sin Graph)",
            ONEDRIVE_SETTLE_SEC,
        )
        time.sleep(ONEDRIVE_SETTLE_SEC)

        _validate_dinamicas(dest_dinamicas, "Destino DINÁMICAS")
        _validate_readable_excel(dest_pago, "Destino PAGO ME")
        _validate_proveedores(dest_proveedores)

        _unlink_quiet(bak_dinamicas, logger)
        _unlink_quiet(bak_pago, logger)
        _unlink_quiet(tmp_dinamicas, logger)
        _unlink_quiet(tmp_pago, logger)

        published = list(PUBLISHED_FILE_NAMES)
        payload = _write_status(
            sha256=sha,
            status=PUBLISH_SUCCEEDED,
            error=None,
            published_files=published,
            logger=logger,
        )
        result.status = PUBLISH_SUCCEEDED
        result.published_files = published
        result.publish_at = str(payload["publish_at"])
        logger.info("Publicación final Succeeded (transacción compensada mediante rollback)")
        logger.info("Archivos publicados/validados: %s", ", ".join(published))
        return result

    except Exception as exc:
        message = str(exc)
        logger.error("Publicación Failed: %s", message)
        if replaced_dinamicas and not restored:
            try:
                if had_dest_dinamicas and bak_dinamicas.is_file():
                    os.replace(bak_dinamicas, dest_dinamicas)
                    logger.info("Rollback de excepción: restaurada DINÁMICAS desde backup")
                elif dest_dinamicas.is_file() and not had_dest_dinamicas:
                    dest_dinamicas.unlink()
                    logger.info("Rollback de excepción: eliminada DINÁMICAS destino nueva")
            except OSError as rollback_exc:
                logger.error("Rollback incompleto; se conserva backup si existe: %s", rollback_exc)

        _unlink_quiet(tmp_dinamicas, logger)
        _unlink_quiet(tmp_pago, logger)
        if bak_dinamicas.exists() and dest_dinamicas.exists() and had_dest_dinamicas:
            _unlink_quiet(bak_dinamicas, logger)
        if bak_pago.exists() and dest_pago.exists():
            _unlink_quiet(bak_pago, logger)

        _write_status(
            sha256=sha,
            status=PUBLISH_FAILED,
            error=message,
            published_files=[],
            logger=logger,
        )
        result.status = PUBLISH_FAILED
        result.error = message
        result.publish_at = datetime.now().isoformat(timespec="seconds")
        if isinstance(exc, PublishAborted):
            raise
        raise PublishAborted(message) from exc
