"""
Módulo EF-04 — Matriz operacional Tesorería.

Fuente principal: matriz consolidada TD_USD_COM (derivada de FBL1N/MODELO).
Una fila = un proceso SAP. Sin agregaciones ni duplicados.

NO modifica pipeline, PM anteriores ni artefactos EF/PM previos.
NO usa Archivo Solicitud como fuente principal.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIZ_SAP = ROOT / "data" / "output" / "MATRIZ_VALIDADORA_TD_USD_COM.xlsx"
DEFAULT_MODELO = ROOT / "data" / "output" / "MODELO_TD_USD_COM.xlsx"
DEFAULT_FBL1N = ROOT / "data" / "input" / "FBL1N_FLUJO_RECONSTRUIDO.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "MATRIZ_OPERACIONAL_TESORERIA.xlsx"

TESORERIA_COLUMNS: tuple[str, ...] = (
    "SOCIEDAD",
    "ACREEDOR",
    "PROVISION_CONTABLE",
    "DOCUMENTO_CONTABLE",
    "NOMBRE_BENEFICIARIO",
    "REFERENCIA_DERIVADA",
    "REFERENCIA_BASE",
    "VARIANTE",
    "MONEDA",
    "MONTO_USD",
    "FECHA_PA25USD",
    "MES_PAGO",
    "AÑO_PAGO",
    "DOCUMENTO_PA25USD",
    "ESTADO_PROCESO",
    "OBSERVACION",
)


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


def _pick(df: pd.DataFrame, *candidates: str) -> str | None:
    by_norm = {
        "".join(str(c).lower().split()): c for c in df.columns
    }
    for cand in candidates:
        key = "".join(cand.lower().split())
        if key in by_norm:
            return by_norm[key]
    for cand in candidates:
        key = "".join(cand.lower().split())
        for nk, original in by_norm.items():
            if key and key in nk:
                return original
    return None


def _variante(row: pd.Series) -> str:
    kn = _as_str(row.get("Variante_KN", "")).upper() == "SI"
    kr = _as_str(row.get("Variante_KR", "")).upper() == "SI"
    if kn and kr:
        return "KN+KR"
    if kn:
        return "KN"
    if kr:
        return "KR"
    return ""


def _mes_anio(fecha: str) -> tuple[str, str]:
    if not fecha:
        return "", ""
    ts = pd.to_datetime(fecha, errors="coerce")
    if pd.isna(ts):
        return "", ""
    return ts.strftime("%m"), ts.strftime("%Y")


def _observacion(row: pd.Series) -> str:
    partes: list[str] = []
    if _as_str(row.get("Proceso_Completo", "")).upper() != "SI":
        partes.append("PROCESO_INCOMPLETO")
    if _as_str(row.get("Tiene_PA25USD", "")).upper() != "SI":
        partes.append("SIN_PA25USD")
    if _as_str(row.get("Tiene_Referencia_Derivada", "")).upper() != "SI":
        partes.append("SIN_REFERENCIA_DERIVADA")
    if _as_str(row.get("Tiene_Cambio_Moneda", "")).upper() != "SI":
        partes.append("SIN_CAMBIO_MONEDA")
    return " | ".join(partes)


def load_matriz_consolidada(path: Path) -> pd.DataFrame:
    """Carga la matriz consolidada (una fila por proceso SAP)."""
    df = pd.read_excel(path, sheet_name="MATRIZ", dtype=str)
    if df.empty:
        raise ValueError(f"MATRIZ vacia: {path}")
    required = {
        "Sociedad",
        "Acreedor",
        "Referencia_Base",
        "Referencia_Derivada",
        "Documento_Contable_Cambio_Moneda",
    }
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Columnas ausentes en matriz consolidada: {sorted(missing)}")
    # Deduplicar por ID_PROCESO si existe
    if "ID_PROCESO" in df.columns:
        df = df.drop_duplicates(subset=["ID_PROCESO"], keep="first")
    else:
        df = df.drop_duplicates(
            subset=["Acreedor", "Referencia_Base", "Sociedad"], keep="first"
        )
    return df.reset_index(drop=True)


def load_nombres_beneficiario(fbl1n_path: Path) -> dict[tuple[str, str], str]:
    """Mapa (Sociedad, Documento) -> Name desde FBL1N."""
    if not fbl1n_path.exists():
        return {}
    fbl = pd.read_excel(fbl1n_path, sheet_name=0, dtype=str)
    c_soc = _pick(fbl, "Sociedad")
    c_doc = _pick(fbl, "Nº documento", "N documento", "Documento")
    c_name = _pick(fbl, "Name", "Nombre", "NOMBRE BENEFICIARIO")
    if not c_soc or not c_doc or not c_name:
        return {}
    out: dict[tuple[str, str], str] = {}
    for _, row in fbl.iterrows():
        soc = _as_str(row[c_soc]).upper()
        doc = _as_str(row[c_doc])
        name = _as_str(row[c_name])
        if soc and doc and name and (soc, doc) not in out:
            out[(soc, doc)] = name
    return out


def build_matriz_tesoreria(
    matriz_sap_path: Path = DEFAULT_MATRIZ_SAP,
    fbl1n_path: Path = DEFAULT_FBL1N,
) -> pd.DataFrame:
    sap = load_matriz_consolidada(matriz_sap_path)
    nombres = load_nombres_beneficiario(fbl1n_path)

    rows: list[dict[str, object]] = []
    for _, row in sap.iterrows():
        soc = _as_str(row.get("Sociedad", ""))
        acr = _as_str(row.get("Acreedor", ""))
        doc_contable = _as_str(row.get("Documento_Contable_Cambio_Moneda", ""))
        doc_ini = _as_str(row.get("Documento_Inicial_KR31CLP", ""))
        doc_pa = _as_str(row.get("Documento_PA25USD", ""))
        ref_der = _as_str(row.get("Referencia_Derivada", ""))
        ref_base = _as_str(row.get("Referencia_Base", ""))
        moneda = _as_str(row.get("Moneda_Final", "")) or _as_str(
            row.get("Moneda_Cambio", "")
        )
        monto = _as_str(row.get("Monto_USD", ""))
        fecha_pa = _as_str(row.get("Fecha_Pago", ""))
        mes, anio = _mes_anio(fecha_pa)
        estado = _as_str(row.get("Estado_del_proceso", ""))
        variante = _variante(row)

        # Nombre: preferir doc inicial, luego contable, luego PA
        nombre = ""
        for doc in (doc_ini, doc_contable, doc_pa):
            if doc and (soc.upper(), doc) in nombres:
                nombre = nombres[(soc.upper(), doc)]
                break

        rows.append(
            {
                "SOCIEDAD": soc,
                "ACREEDOR": acr,
                "PROVISION_CONTABLE": doc_contable,
                "DOCUMENTO_CONTABLE": doc_contable,
                "NOMBRE_BENEFICIARIO": nombre,
                "REFERENCIA_DERIVADA": ref_der,
                "REFERENCIA_BASE": ref_base,
                "VARIANTE": variante,
                "MONEDA": moneda,
                "MONTO_USD": monto,
                "FECHA_PA25USD": fecha_pa,
                "MES_PAGO": mes,
                "AÑO_PAGO": anio,
                "DOCUMENTO_PA25USD": doc_pa,
                "ESTADO_PROCESO": estado,
                "OBSERVACION": _observacion(row),
            }
        )

    out = pd.DataFrame(rows, columns=list(TESORERIA_COLUMNS))
    # Sin duplicar procesos: ya deduplicado en load; reforzar por llave operativa
    out = out.drop_duplicates(
        subset=["SOCIEDAD", "ACREEDOR", "REFERENCIA_BASE"], keep="first"
    ).reset_index(drop=True)
    return out


def export_matriz(
    df: pd.DataFrame,
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="TESORERIA", index=False)
        ws = writer.sheets["TESORERIA"]
        text_cols = {
            "ACREEDOR",
            "PROVISION_CONTABLE",
            "DOCUMENTO_CONTABLE",
            "REFERENCIA_DERIVADA",
            "REFERENCIA_BASE",
            "MONTO_USD",
            "DOCUMENTO_PA25USD",
            "MES_PAGO",
            "AÑO_PAGO",
        }
        headers = {cell.value: cell.column for cell in ws[1]}
        for name in text_cols:
            if name not in headers:
                continue
            col_idx = headers[name]
            for row_idx in range(2, ws.max_row + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                if cell.value is None:
                    cell.value = ""
                else:
                    cell.value = str(cell.value)
                cell.number_format = "@"
    return output_path


def run(
    matriz_sap_path: Path = DEFAULT_MATRIZ_SAP,
    fbl1n_path: Path = DEFAULT_FBL1N,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Path, pd.DataFrame, dict[str, int]]:
    df = build_matriz_tesoreria(matriz_sap_path, fbl1n_path)
    out = export_matriz(df, output_path)

    variantes = df["VARIANTE"].map(_as_str)
    con_pa = df["DOCUMENTO_PA25USD"].map(_as_str).ne("")
    stats = {
        "procesos": len(df),
        "kn": int((variantes == "KN").sum()),
        "kr": int((variantes == "KR").sum()),
        "kn_kr": int((variantes == "KN+KR").sum()),
        "con_pa25usd": int(con_pa.sum()),
        "sin_pa25usd": int((~con_pa).sum()),
    }
    return out, df, stats
