"""
Módulo EF-06 — Preparación del modelo Power BI.

Genera MODELO_POWERBI.xlsx (FACT + DIMs) desde MATRIZ_OPERACIONAL_TESORERIA.
NO crea .pbix. NO genera medidas DAX.
NO modifica pipeline, PM anteriores ni artefactos previos.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FUENTE = ROOT / "data" / "output" / "MATRIZ_OPERACIONAL_TESORERIA.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "MODELO_POWERBI.xlsx"

FACT_COLUMNS: tuple[str, ...] = (
    "SOCIEDAD",
    "ACREEDOR",
    "PROVISION_CONTABLE",
    "NOMBRE_BENEFICIARIO",
    "REFERENCIA_DERIVADA",
    "VARIANTE",
    "MONEDA",
    "MONTO_USD",
    "FECHA_PA25USD",
    "MES_PAGO",
    "AÑO_PAGO",
)

_MES_NOMBRE = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def _as_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        number = float(text.replace(",", ""))
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return text


def _to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_tesoreria(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="TESORERIA", dtype=str)
    if df.empty:
        raise ValueError(f"Hoja TESORERIA vacia: {path}")
    missing = [c for c in FACT_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Columnas ausentes en TESORERIA: {missing}")
    return df


def build_fact_pagos(src: pd.DataFrame) -> pd.DataFrame:
    fact = src.loc[:, list(FACT_COLUMNS)].copy()
    for col in FACT_COLUMNS:
        if col == "MONTO_USD":
            fact[col] = fact[col].map(_to_float)
        else:
            fact[col] = fact[col].map(_as_str)
    return fact.reset_index(drop=True)


def build_dim_sociedad(src: pd.DataFrame) -> pd.DataFrame:
    vals = sorted({_as_str(v) for v in src["SOCIEDAD"].tolist() if _as_str(v)})
    return pd.DataFrame({"SOCIEDAD": vals})


def build_dim_proveedor(src: pd.DataFrame) -> pd.DataFrame:
    work = src.copy()
    work["_acr"] = work["ACREEDOR"].map(_as_str)
    work["_nom"] = work["NOMBRE_BENEFICIARIO"].map(_as_str)
    # Lista unica de acreedores; conservar un nombre representativo si existe
    rows: list[dict[str, str]] = []
    for acr, g in work.groupby("_acr", sort=True):
        if not acr:
            continue
        nombres = [n for n in g["_nom"].tolist() if n]
        nombre = sorted(set(nombres))[0] if nombres else ""
        rows.append({"ACREEDOR": acr, "NOMBRE_BENEFICIARIO": nombre})
    return pd.DataFrame(rows)


def build_dim_fecha(src: pd.DataFrame) -> pd.DataFrame:
    fechas = sorted(
        {
            _as_str(v)
            for v in src["FECHA_PA25USD"].tolist()
            if _as_str(v)
        }
    )
    rows: list[dict[str, object]] = []
    for fecha in fechas:
        ts = pd.to_datetime(fecha, errors="coerce")
        if pd.isna(ts):
            continue
        mes = int(ts.month)
        anio = int(ts.year)
        trimestre = int((mes - 1) // 3 + 1)
        rows.append(
            {
                "FECHA": ts.strftime("%Y-%m-%d"),
                "MES": f"{mes:02d}",
                "AÑO": str(anio),
                "MES_NOMBRE": _MES_NOMBRE.get(mes, ""),
                "TRIMESTRE": f"Q{trimestre}",
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["FECHA", "MES", "AÑO", "MES_NOMBRE", "TRIMESTRE"])
    return out.drop_duplicates(subset=["FECHA"]).sort_values("FECHA").reset_index(
        drop=True
    )


def build_dim_moneda(src: pd.DataFrame) -> pd.DataFrame:
    vals = sorted({_as_str(v) for v in src["MONEDA"].tolist() if _as_str(v)})
    return pd.DataFrame({"MONEDA": vals})


def build_modelo(src: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "FACT_PAGOS": build_fact_pagos(src),
        "DIM_SOCIEDAD": build_dim_sociedad(src),
        "DIM_PROVEEDOR": build_dim_proveedor(src),
        "DIM_FECHA": build_dim_fecha(src),
        "DIM_MONEDA": build_dim_moneda(src),
    }


def export_modelo(
    sheets: dict[str, pd.DataFrame],
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            # Texto en claves para evitar notacion cientifica
            text_like = {
                "ACREEDOR",
                "PROVISION_CONTABLE",
                "REFERENCIA_DERIVADA",
                "MES_PAGO",
                "AÑO_PAGO",
                "MES",
                "AÑO",
                "FECHA",
            }
            headers = {cell.value: cell.column for cell in ws[1]}
            for col_name in text_like:
                if col_name not in headers:
                    continue
                col_idx = headers[col_name]
                for row_idx in range(2, ws.max_row + 1):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    if cell.value is None:
                        cell.value = ""
                    else:
                        cell.value = str(cell.value)
                    cell.number_format = "@"
    return output_path


def run(
    fuente: Path = DEFAULT_FUENTE,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Path, dict[str, pd.DataFrame]]:
    src = load_tesoreria(Path(fuente))
    sheets = build_modelo(src)
    out = export_modelo(sheets, Path(output_path))
    return out, sheets
