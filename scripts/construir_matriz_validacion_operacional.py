"""
EF-01 — Construccion de MATRIZ_VALIDACION_OPERACIONAL.

Modulo nuevo. NO modifica pipeline, src existente, PM anteriores,
MODELO_TD_USD_COM, MATRIZ_VALIDADORA, AUDITORIA, Dashboard ni Power BI.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_matriz_validacion_operacional.py
  .venv\\Scripts\\python.exe scripts\\construir_matriz_validacion_operacional.py --solicitud "ruta.xlsx"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.validacion_operacional.module import (  # noqa: E402
    DEFAULT_MATRIZ_SAP,
    DEFAULT_OUTPUT,
    run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EF-01 — Construir MATRIZ_VALIDACION_OPERACIONAL (hoja MVO)"
    )
    parser.add_argument(
        "--solicitud",
        type=Path,
        default=None,
        help="Ruta al Archivo Solicitud Pago Extranjero (Tesoreria)",
    )
    parser.add_argument(
        "--matriz-sap",
        type=Path,
        default=DEFAULT_MATRIZ_SAP,
        help="Ruta a MATRIZ_VALIDADORA_TD_USD_COM.xlsx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ruta de salida MATRIZ_VALIDACION_OPERACIONAL.xlsx",
    )
    parser.add_argument(
        "--responsable",
        type=str,
        default="SISTEMA",
        help="Valor columna RESPONSABLE",
    )
    args = parser.parse_args()

    out, mvo = run(
        solicitud_path=args.solicitud,
        matriz_sap_path=args.matriz_sap,
        output_path=args.output,
        responsable=args.responsable,
    )

    estados = mvo["ESTADO_VALIDACION"].value_counts().to_dict()
    acciones = mvo["ACCION_RECOMENDADA"].value_counts().to_dict()
    print(f"Solicitudes: {len(mvo)}")
    print(f"Salida: {out}")
    print(f"Estados: {estados}")
    print(f"Acciones: {acciones}")
    print(f"Encontrados: {(mvo['PROCESO_ENCONTRADO']=='SI').sum()}")
    print(f"Completos: {(mvo['PROCESO_COMPLETO']=='SI').sum()}")


if __name__ == "__main__":
    main()
