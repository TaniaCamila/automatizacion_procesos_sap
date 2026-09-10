"""
EF-11.0 / EF-13.7 / EF-14.2 / EF-14.9 — Construccion del entregable de dinamicas finales.

Fuente unica (solo lectura): MATRIZ_FBL1N_*.xlsx mas reciente.
Pago ME (solo lectura): data/input/EJM_ARCHIVO_PAGO_MONEDA_EXTRANJERA.xlsx

Hojas:
  COMB_CLP, NO_COMB_CLP, COMB_USD, NO_COMB_USD, CLP_USD,
  COMB_GNL CHILE, CONFIRMING_USD, PENDIENTES_USD, NO_ECM

NO modifica pipeline, MATRIZ, catalogos ni reglas.

Uso:
  .venv\\Scripts\\python.exe scripts\\construir_dinamicas_finales.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.dinamicas_finales.module import (  # noqa: E402
    CONFIRMING_SHEET,
    FINAL_SHEET_ORDER,
    NO_ECM_SHEET,
    PAGO_ME_PATH,
    PENDIENTES_SHEET,
    SHEET_MAP,
    get_last_ef137_audit,
    get_last_ef142_audit,
    get_last_ef144_audit,
    get_last_ef149_audit,
    run,
)
from src.modules.margen.module import InformeMargenModule  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EF-14.9 — Generar DINAMICAS_FINALES_*.xlsx"
    )
    parser.add_argument(
        "--matriz",
        type=Path,
        default=None,
        help="Ruta a MATRIZ_FBL1N_*.xlsx (default: mas reciente en data/output)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta de salida DINAMICAS_FINALES_*.xlsx",
    )
    args = parser.parse_args()

    out, sheets, counts, source = run(
        matriz_path=args.matriz,
        output_path=args.output,
    )

    print(f"Fuente MATRIZ: {source}")
    print(f"Fuente pago ME: {PAGO_ME_PATH}")
    print(f"Archivo generado: {out}")
    print("Hojas creadas:")
    for name in FINAL_SHEET_ORDER:
        origin = SHEET_MAP.get(name, name)
        if name == "CLP_USD":
            origin = "COMB_USD + NO_COMB_USD (EF-13.7 USD)"
        elif name in {"COMB_USD", "NO_COMB_USD"}:
            origin = f"{origin} + EF-13.7 USD pago ME"
        elif name == CONFIRMING_SHEET:
            origin = "SIN_MATCH confirming (EF-14.9)"
        elif name == PENDIENTES_SHEET:
            origin = "sin match / match multiple USD"
        elif name == NO_ECM_SHEET:
            origin = "fuera de nomenclatura (EF-14.2)"
        print(f"  - {name}: {counts[name]} registros  (origen: {origin})")

    audit = get_last_ef137_audit()
    if audit is not None:
        print("EF-13.7 — validacion USD:")
        print(f"  evaluados={audit['procesados']}")
        print(f"  match_unico={audit['match_unico']}")
        print(f"  sin_match={audit['sin_match']}")
        print(f"  match_multiple={audit['multi']}")
        print(f"  pendientes={audit['pendientes']}")

    ef142 = get_last_ef142_audit()
    if ef142 is not None:
        print("EF-14.2 — NO_ECM:")
        print(f"  registros_trasladados={ef142['registros_trasladados']}")
        print(f"  monto_trasladado={ef142['monto_trasladado']}")
        print(f"  sin_concepto={ef142['sin_concepto']}")
        print(f"  fuera_nomenclatura={ef142['fuera_nomenclatura']}")
        print(f"  universo={ef142['universo_registros']}")
        print(f"  dinamicas={ef142['dinamicas_registros']}")
        print(f"  no_ecm={ef142['no_ecm_registros']}")
        print(f"  conciliacion_registros_ok={ef142['conciliacion_registros_ok']}")
        print(f"  conciliacion_importe_ok={ef142['conciliacion_importe_ok']}")
        print(f"  duplicados={ef142['duplicados']}")
        print(f"  total_COMB_CLP={ef142['total_COMB_CLP']}")
        print(f"  total_NO_COMB_CLP={ef142['total_NO_COMB_CLP']}")
        print(f"  total_COMB_USD={ef142['total_COMB_USD']}")
        print(f"  total_NO_COMB_USD={ef142['total_NO_COMB_USD']}")
        print(f"  total_CLP_USD={ef142['total_CLP_USD']}")
        print(f"  total_COMB_GNL={ef142['total_COMB_GNL']}")
        if "total_CONFIRMING_USD" in ef142:
            print(f"  total_CONFIRMING_USD={ef142['total_CONFIRMING_USD']}")
        print(f"  total_NO_ECM={ef142['total_NO_ECM']}")

    ef144 = get_last_ef144_audit()
    if ef144 is not None:
        print("EF-14.4 — DATOS documentales:")
        print(f"  filas_por_datos={ef144['filas_por_datos']}")
        print(f"  importe_por_datos={ef144['importe_por_datos']}")
        print(f"  duplicados_por_datos={ef144['duplicados_por_datos']}")
        print(f"  columnas={ef144['columnas_documentales']}")

    ef149 = get_last_ef149_audit()
    if ef149 is not None:
        print("EF-14.9 — CONFIRMING_USD:")
        print(f"  registros={ef149['registros']}")
        print(f"  proveedores={ef149['proveedores']}")
        print(f"  acreedores={ef149['acreedores']}")
        print(f"  todos_sin_match={ef149['todos_sin_match']}")
        print(f"  solo_acreedores_confirming={ef149['solo_acreedores_confirming']}")
        print(f"  importe_clp={ef149['importe_clp']}")
        print(f"  total_pivot={ef149['total_pivot']}")
        print(
            f"  pendientes_confirming_sin_match="
            f"{ef149['pendientes_confirming_sin_match']}"
        )
        print(
            f"  pendientes_confirming_importe="
            f"{ef149['pendientes_confirming_importe']}"
        )
        print(f"  conciliacion_registros_ok={ef149['conciliacion_registros_ok']}")
        print(f"  conciliacion_importe_ok={ef149['conciliacion_importe_ok']}")

    print(
        "Logica base: InformeMargenModule.generate_td_clp_dynamics "
        f"(TD_CLP_COM_2026={InformeMargenModule._TD_SHEET_COM}, "
        f"TD_CLP_NO_COM={InformeMargenModule._TD_SHEET_NO_COM}, "
        f"CLP_USD_COM={InformeMargenModule._TD_SHEET_CLP_USD_COM}, "
        f"CLP_USD_NO_COM={InformeMargenModule._TD_SHEET_CLP_USD_NO_COM})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
