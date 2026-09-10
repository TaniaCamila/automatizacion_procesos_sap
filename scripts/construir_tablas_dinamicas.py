"""
EF-03 — Construccion de TABLAS_DINAMICAS_OPERACIONALES.

Modulo nuevo. NO modifica pipeline, src existentes, PM anteriores,
MVO, RESUMEN_OPERACIONAL, Dashboard ni Power BI.

Fuente unica: MATRIZ_VALIDACION_OPERACIONAL.xlsx (hoja MVO).

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_tablas_dinamicas.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.tablas_dinamicas.module import (  # noqa: E402
    DEFAULT_MVO,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-03 — Construir TABLAS_DINAMICAS_OPERACIONALES.xlsx"
    )
    parser.add_argument(
        "--mvo",
        type=Path,
        default=DEFAULT_MVO,
        help="Ruta a MATRIZ_VALIDACION_OPERACIONAL.xlsx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ruta de salida TABLAS_DINAMICAS_OPERACIONALES.xlsx",
    )
    args = parser.parse_args()

    out, sheets = run(mvo_path=args.mvo, output_path=args.output)
    print(f"Salida: {out}")
    for name, df in sheets.items():
        print(f"--- {name} ---")
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
