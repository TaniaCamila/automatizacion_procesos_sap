"""
EF-04 — Construccion de MATRIZ_OPERACIONAL_TESORERIA.

Modulo nuevo. Fuente principal: matriz consolidada TD_USD_COM (FBL1N/MODELO).
Una fila = un proceso SAP. El Archivo Solicitud NO es fuente principal.

NO modifica pipeline, PM anteriores ni artefactos EF/PM previos.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_matriz_operacional_tesoreria.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.matriz_operacional_tesoreria.module import (  # noqa: E402
    DEFAULT_FBL1N,
    DEFAULT_MATRIZ_SAP,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-04 — Construir MATRIZ_OPERACIONAL_TESORERIA.xlsx"
    )
    parser.add_argument(
        "--matriz-sap",
        type=Path,
        default=DEFAULT_MATRIZ_SAP,
        help="Matriz consolidada TD_USD_COM (MATRIZ_VALIDADORA)",
    )
    parser.add_argument(
        "--fbl1n",
        type=Path,
        default=DEFAULT_FBL1N,
        help="FBL1N para NOMBRE_BENEFICIARIO",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ruta de salida",
    )
    args = parser.parse_args()

    out, _df, stats = run(
        matriz_sap_path=args.matriz_sap,
        fbl1n_path=args.fbl1n,
        output_path=args.output,
    )
    print(f"Cantidad de procesos: {stats['procesos']}")
    print(f"Cantidad KN: {stats['kn']}")
    print(f"Cantidad KR: {stats['kr']}")
    print(f"Cantidad KN+KR: {stats['kn_kr']}")
    print(f"Cantidad con PA25USD: {stats['con_pa25usd']}")
    print(f"Cantidad sin PA25USD: {stats['sin_pa25usd']}")
    print(f"Ruta: {out}")


if __name__ == "__main__":
    main()
