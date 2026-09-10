"""
EF-08 — Preparación del paquete Power BI Tesorería (sin .pbix).

Entrada : MODELO_POWERBI.xlsx (solo lectura; no se modifica)
Salida  : data/output/PBIX_TESORERIA_PACKAGE/

NO modifica pipeline, EF anteriores ni el modelo de datos.
NO genera .pbix. NO abre Power BI Desktop.
NO usa Archivo Solicitud Pago Extranjero.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_pbix_tesoreria.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.pbix_tesoreria.module import (  # noqa: E402
    DASHBOARD_NAME,
    run,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EF-08 — Preparar estructura del paquete Power BI (sin .pbix)"
    )
    parser.add_argument(
        "--modelo",
        type=Path,
        default=ROOT / "data" / "output" / "MODELO_POWERBI.xlsx",
        help="Ruta MODELO_POWERBI.xlsx (solo lectura)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "output" / "PBIX_TESORERIA_PACKAGE",
        help="Directorio de salida del paquete",
    )
    args = parser.parse_args()

    out = run(modelo=args.modelo, package_dir=args.out)
    print(f"Dashboard : {DASHBOARD_NAME}")
    print(f"Paquete   : {out}")
    print("Estado    : EF-08 PREPARACION COMPLETA (sin .pbix)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
