"""
Comando único de actualización FBL1N.

Uso (desde la raíz del repo):
  .venv\\Scripts\\python.exe scripts\\run_actualizacion_automatica.py
  .venv\\Scripts\\python.exe scripts\\run_actualizacion_automatica.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.actualizacion_automatica.module import (  # noqa: E402
    PipelineAborted,
    run_actualizacion,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquestar pipeline FBL1N (matriz + dinámicas) de forma controlada."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocesar aunque el FBL1N coincida con el último estado exitoso.",
    )
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Solo detectar cambio/estabilidad/lock; no ejecutar matriz ni dinámicas.",
    )
    args = parser.parse_args()
    try:
        result = run_actualizacion(force=args.force, detect_only=args.detect_only)
    except PipelineAborted:
        return 1
    if result.status != "OK":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
