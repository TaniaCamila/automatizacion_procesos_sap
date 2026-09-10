"""
EF-05 — Construccion de PivotTables nativas de Excel (Tesoreria).

Fuente unica: MATRIZ_OPERACIONAL_TESORERIA.xlsx (hoja TESORERIA).
Genera PivotTables reales (no tablas estaticas).

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_pivots_tesoreria.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.pivots_tesoreria.module import (  # noqa: E402
    DEFAULT_FUENTE,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-05 — Construir TABLAS_DINAMICAS_TESORERIA.xlsx (PivotTables nativas)"
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
        help="Ruta de salida TABLAS_DINAMICAS_TESORERIA.xlsx",
    )
    args = parser.parse_args()

    out, n = run(fuente=args.fuente, output_path=args.output)
    print(f"Cantidad de PivotTables creadas: {n}")
    print(f"Ruta: {out}")


if __name__ == "__main__":
    main()
