"""
EF-02 — Construccion de RESUMEN_OPERACIONAL.

Modulo nuevo. NO modifica pipeline, src existentes, PM anteriores,
MATRIZ_VALIDACION_OPERACIONAL, Dashboard ni Power BI.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_resumen_operacional.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.resumen_operacional.module import (  # noqa: E402
    DEFAULT_MVO,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-02 — Construir RESUMEN_OPERACIONAL.xlsx"
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
        help="Ruta de salida RESUMEN_OPERACIONAL.xlsx",
    )
    args = parser.parse_args()

    out, sheets = run(mvo_path=args.mvo, output_path=args.output)
    print(f"Salida: {out}")
    for name, df in sheets.items():
        print(f"  {name}: {len(df)} filas")
    general = sheets["RESUMEN_GENERAL"]
    print(general.to_string(index=False))


if __name__ == "__main__":
    main()
