"""
EF-06 — Preparacion del Modelo Power BI.

Fuente: MATRIZ_OPERACIONAL_TESORERIA.xlsx
Salida: MODELO_POWERBI.xlsx (FACT_PAGOS + DIMs)

NO crea .pbix. NO genera medidas DAX.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_modelo_powerbi.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.modelo_powerbi.module import (  # noqa: E402
    DEFAULT_FUENTE,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-06 — Construir MODELO_POWERBI.xlsx"
    )
    parser.add_argument(
        "--fuente",
        type=Path,
        default=DEFAULT_FUENTE,
        help="Ruta a MATRIZ_OPERACIONAL_TESORERIA.xlsx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ruta de salida MODELO_POWERBI.xlsx",
    )
    args = parser.parse_args()

    out, sheets = run(fuente=args.fuente, output_path=args.output)
    print(f"Salida: {out}")
    for name, df in sheets.items():
        print(f"  {name}: {len(df)} filas")


if __name__ == "__main__":
    main()
