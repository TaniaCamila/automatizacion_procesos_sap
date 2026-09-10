"""
Módulo EF-02 — Resumen operacional.

Concentra indicadores desde MATRIZ_VALIDACION_OPERACIONAL (hoja MVO).
NO modifica datos de la MVO. NO recalcula reglas SAP.
NO modifica pipeline ni módulos anteriores.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MVO = ROOT / "data" / "output" / "MATRIZ_VALIDACION_OPERACIONAL.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "RESUMEN_OPERACIONAL.xlsx"

ESTADOS_ORDEN: tuple[str, ...] = (
    "VALIDADO",
    "VALIDADO_CON_OBSERVACION",
    "NO_VALIDADO",
    "INCOMPLETO",
)


def _as_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if not text or text.lower() == "nan" else text


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 2)


def load_mvo(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="MVO", dtype=str)
    if df.empty:
        raise ValueError(f"MVO vacia: {path}")
    required = {"ESTADO_VALIDACION", "ACCION_RECOMENDADA"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Columnas ausentes en MVO: {sorted(missing)}")
    return df


def build_resumen_general(mvo: pd.DataFrame) -> pd.DataFrame:
    total = len(mvo)
    estados = mvo["ESTADO_VALIDACION"].map(_as_str).str.upper()

    n_val = int((estados == "VALIDADO").sum())
    n_obs = int((estados == "VALIDADO_CON_OBSERVACION").sum())
    n_no = int((estados == "NO_VALIDADO").sum())
    n_inc = int((estados == "INCOMPLETO").sum())

    fecha = ""
    if "FECHA_EJECUCION" in mvo.columns and not mvo["FECHA_EJECUCION"].empty:
        fecha = _as_str(mvo["FECHA_EJECUCION"].iloc[0])

    archivo = ""
    if "ARCHIVO_ORIGEN" in mvo.columns and not mvo["ARCHIVO_ORIGEN"].empty:
        # Si hay mas de un origen, listar unicos
        origenes = sorted(
            { _as_str(v) for v in mvo["ARCHIVO_ORIGEN"].tolist() if _as_str(v) }
        )
        archivo = " | ".join(origenes)

    return pd.DataFrame(
        [
            {"INDICADOR": "TOTAL_SOLICITUDES", "VALOR": total},
            {"INDICADOR": "VALIDADAS", "VALOR": n_val},
            {"INDICADOR": "VALIDADAS_CON_OBSERVACION", "VALOR": n_obs},
            {"INDICADOR": "NO_VALIDADAS", "VALOR": n_no},
            {"INDICADOR": "INCOMPLETAS", "VALOR": n_inc},
            {"INDICADOR": "PORCENTAJE_VALIDADAS", "VALOR": _pct(n_val, total)},
            {"INDICADOR": "PORCENTAJE_NO_VALIDADAS", "VALOR": _pct(n_no, total)},
            {"INDICADOR": "PORCENTAJE_INCOMPLETAS", "VALOR": _pct(n_inc, total)},
            {"INDICADOR": "FECHA_EJECUCION", "VALOR": fecha},
            {"INDICADOR": "ARCHIVO_PROCESADO", "VALOR": archivo},
        ]
    )


def build_resumen_estados(mvo: pd.DataFrame) -> pd.DataFrame:
    total = len(mvo)
    estados = mvo["ESTADO_VALIDACION"].map(_as_str).str.upper()
    counts = estados.value_counts()

    rows = []
    for estado in ESTADOS_ORDEN:
        cant = int(counts.get(estado, 0))
        rows.append(
            {
                "ESTADO_VALIDACION": estado,
                "CANTIDAD": cant,
                "PORCENTAJE": _pct(cant, total),
            }
        )
    return pd.DataFrame(rows)


def build_resumen_acciones(mvo: pd.DataFrame) -> pd.DataFrame:
    acciones = mvo["ACCION_RECOMENDADA"].map(_as_str)
    # Vacios como (SIN_ACCION) para no perder filas
    acciones = acciones.map(lambda a: a if a else "(SIN_ACCION)")
    vc = acciones.value_counts()
    rows = [
        {"ACCION_RECOMENDADA": accion, "CANTIDAD": int(cant)}
        for accion, cant in vc.items()
    ]
    return pd.DataFrame(rows)


def build_resumen_variantes(mvo: pd.DataFrame) -> pd.DataFrame:
    if "VARIANTE" not in mvo.columns:
        return pd.DataFrame(
            columns=[
                "VARIANTE",
                "CANTIDAD",
                "PROCESOS_COMPLETOS",
                "PROCESOS_INCOMPLETOS",
            ]
        )

    work = mvo.copy()
    work["_var"] = work["VARIANTE"].map(_as_str)
    work["_var"] = work["_var"].map(lambda v: v if v else "(SIN_VARIANTE)")

    completo = pd.Series([False] * len(work))
    if "PROCESO_COMPLETO" in work.columns:
        completo = work["PROCESO_COMPLETO"].map(_as_str).str.upper().eq("SI")
    elif "ESTADO_PROCESO_SAP" in work.columns:
        completo = work["ESTADO_PROCESO_SAP"].map(_as_str).str.upper().eq("COMPLETO")

    rows = []
    for variante, g in work.groupby("_var", sort=True):
        mask = work["_var"] == variante
        n = int(mask.sum())
        n_comp = int((mask & completo).sum())
        n_inc = n - n_comp
        rows.append(
            {
                "VARIANTE": variante,
                "CANTIDAD": n,
                "PROCESOS_COMPLETOS": n_comp,
                "PROCESOS_INCOMPLETOS": n_inc,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("CANTIDAD", ascending=False).reset_index(drop=True)


def build_resumen(mvo: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "RESUMEN_GENERAL": build_resumen_general(mvo),
        "RESUMEN_ESTADOS": build_resumen_estados(mvo),
        "RESUMEN_ACCIONES": build_resumen_acciones(mvo),
        "RESUMEN_VARIANTES": build_resumen_variantes(mvo),
    }


def export_resumen(
    sheets: dict[str, pd.DataFrame],
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return output_path


def run(
    mvo_path: Path = DEFAULT_MVO,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Path, dict[str, pd.DataFrame]]:
    mvo = load_mvo(Path(mvo_path))
    sheets = build_resumen(mvo)
    out = export_resumen(sheets, Path(output_path))
    return out, sheets
