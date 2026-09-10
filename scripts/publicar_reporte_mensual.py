"""
Publicación manual hacia REPORTE QUERY MENSUAL.

No ejecuta el pipeline técnico. No modifica FBL1N.

Uso (desde la raíz del repo):
  .venv\\Scripts\\python.exe scripts\\publicar_reporte_mensual.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.config import FBL1N_PATH, LOG_DIR  # noqa: E402
from src.modules.actualizacion_automatica.module import (  # noqa: E402
    PipelineLock,
    load_state,
    sha256_file,
)
from src.modules.publicacion_final.module import (  # noqa: E402
    PUBLISH_SUCCEEDED,
    PublishAborted,
    run_publish,
)


def _setup_logger() -> logging.Logger:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except OSError:
            pass
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"publicacion_final_{stamp}.log"
    logger = logging.getLogger("publicacion_final")
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
    logger.info("Log: %s", log_path)
    return logger


def _resolve_sha256(logger: logging.Logger) -> str:
    last = load_state()
    if last and last.get("sha256"):
        sha = str(last["sha256"])
        logger.info("source_fbl1n_sha256 desde last_fbl1n_state.json: %s", sha)
        return sha
    if FBL1N_PATH.is_file():
        sha = sha256_file(FBL1N_PATH)
        logger.info("source_fbl1n_sha256 calculado (solo lectura) de FBL1N: %s", sha)
        return sha
    raise PublishAborted(
        "No hay last_fbl1n_state.json ni FBL1N para asociar source_fbl1n_sha256"
    )


def main() -> int:
    logger = _setup_logger()
    lock = PipelineLock()
    try:
        lock.acquire()
        sha = _resolve_sha256(logger)
        result = run_publish(sha, logger)
    except PublishAborted as exc:
        logger.error("PUBLICACIÓN ERROR: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Error inesperado de publicación: %s", exc)
        return 1
    finally:
        lock.release()

    if result.status != PUBLISH_SUCCEEDED:
        logger.error("publish_status=%s error=%s", result.status, result.error)
        return 1
    print(
        "\n".join(
            [
                "============================================================",
                "PUBLICACIÓN FINAL",
                "============================================================",
                f"Estado: {result.status}",
                f"Hash FBL1N: {result.source_fbl1n_sha256}",
                f"Archivos: {', '.join(result.published_files)}",
                "============================================================",
            ]
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
