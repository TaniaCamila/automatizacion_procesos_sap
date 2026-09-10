"""
Módulo EF-01 — Validación operacional TD_USD_COM.

Construye MATRIZ_VALIDACION_OPERACIONAL (una fila = una solicitud Tesorería).
La evidencia SAP proviene únicamente de MATRIZ_VALIDADORA_TD_USD_COM.xlsx.

NO modifica pipeline, src existente, PM anteriores ni matrices PM.
NO infiere reglas SAP nuevas. NO crea referencias nuevas.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIZ_SAP = ROOT / "data" / "output" / "MATRIZ_VALIDADORA_TD_USD_COM.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "MATRIZ_VALIDACION_OPERACIONAL.xlsx"
DEFAULT_SOLICITUD_CANDIDATES = (
    ROOT / "data" / "input" / "EJM_ARCHIVO_PAGO_MONEDA_EXTRANJERA.xlsx",
    Path.home() / "Downloads" / "EJM ARCHIVO PAGO MONEDA EXTRANJERA.xlsx",
    Path.home() / "Downloads" / "EJM_ARCHIVO_PAGO_MONEDA_EXTRANJERA.xlsx",
)

_REF_SUFFIX_RE = re.compile(r"[-_/]\d+$")

ESTADOS_VALIDACION = frozenset(
    {"VALIDADO", "VALIDADO_CON_OBSERVACION", "NO_VALIDADO", "INCOMPLETO"}
)

MVO_COLUMNS: tuple[str, ...] = (
    # A
    "ID_EJECUCION",
    "FECHA_EJECUCION",
    "SOCIEDAD",
    "ACREEDOR",
    "DOCUMENTO_SOLICITUD",
    # B
    "MONEDA_SOLICITADA",
    "IMPORTE_SOLICITADO",
    "FECHA_SOLICITUD",
    "ARCHIVO_ORIGEN",
    # C
    "REFERENCIA_BASE",
    "REFERENCIA_DERIVADA",
    "DOCUMENTO_KR31CLP",
    "DOCUMENTO_CAMBIO_28",
    "DOCUMENTO_CAMBIO_36",
    "DOCUMENTO_PA25USD",
    "VARIANTE",
    "ESTADO_PROCESO_SAP",
    # D
    "PROCESO_ENCONTRADO",
    "PROCESO_COMPLETO",
    "ESTADO_VALIDACION",
    "MOTIVO",
    "OBSERVACION",
    "ACCION_RECOMENDADA",
    # E
    "AÑO",
    "MES",
    "SEMANA",
    "RESPONSABLE",
    "ESTADO_DASHBOARD",
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


def _norm_key(value: object) -> str:
    return _as_str(value).upper()


def _pick(df: pd.DataFrame, *candidates: str) -> str | None:
    by_norm = {
        re.sub(r"\s+", "", str(c).strip().lower()): c for c in df.columns
    }
    for cand in candidates:
        key = re.sub(r"\s+", "", cand.strip().lower())
        if key in by_norm:
            return by_norm[key]
    for cand in candidates:
        key = re.sub(r"\s+", "", cand.strip().lower())
        for nk, original in by_norm.items():
            if key and key in nk:
                return original
    return None


def _referencia_base(value: object) -> str:
    text = _as_str(value)
    if not text:
        return ""
    base = text
    while True:
        updated = _REF_SUFFIX_RE.sub("", base)
        if updated == base:
            break
        base = updated
    return base.strip()


def _si_no(flag: bool) -> str:
    return "SI" if flag else "NO"


def resolve_solicitud_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(path)
        return path
    for cand in DEFAULT_SOLICITUD_CANDIDATES:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "No se encontro Archivo Solicitud Pago Extranjero. "
        "Indique la ruta o coloque el archivo en data/input/."
    )


def load_matriz_sap(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="MATRIZ", dtype=str)
    if df.empty:
        raise ValueError(f"MATRIZ vacia: {path}")
    required = [
        "Referencia_Derivada",
        "Referencia_Base",
        "Acreedor",
        "Sociedad",
        "Proceso_Completo",
        "Tiene_PA25USD",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Columnas ausentes en MATRIZ_VALIDADORA: {missing}")
    work = df.copy()
    work["_ref_der"] = work["Referencia_Derivada"].map(_as_str)
    work["_ref_base"] = work["Referencia_Base"].map(_as_str)
    work["_acr"] = work["Acreedor"].map(_as_str)
    # Indices de busqueda (primera coincidencia)
    by_der: dict[str, pd.Series] = {}
    by_base: dict[str, pd.Series] = {}
    for _, row in work.iterrows():
        der = row["_ref_der"]
        base = row["_ref_base"]
        if der and der not in by_der:
            by_der[der] = row
        if base and base not in by_base:
            by_base[base] = row
    work.attrs["by_der"] = by_der
    work.attrs["by_base"] = by_base
    return work


def load_solicitud(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, dtype=str)
    if df.empty:
        raise ValueError(f"Archivo solicitud vacio: {path}")
    return df


def _variante_from_sap(row: pd.Series) -> str:
    kn = _as_str(row.get("Variante_KN", "")).upper() == "SI"
    kr = _as_str(row.get("Variante_KR", "")).upper() == "SI"
    if kn and kr:
        return "KN|KR"
    if kn:
        return "KN"
    if kr:
        return "KR"
    return ""


def _accion_recomendada(estado: str, motivo: str) -> str:
    if estado == "VALIDADO":
        return "CONTINUAR"
    if estado == "VALIDADO_CON_OBSERVACION":
        return "CONTINUAR"
    if motivo == "SIN PA25USD":
        return "REVISAR PAGO"
    if estado == "INCOMPLETO" or motivo == "PROCESO INCOMPLETO":
        return "REVISAR SAP"
    if estado == "NO_VALIDADO" or motivo == "NO ENCONTRADO":
        return "REVISAR REFERENCIA"
    return "REVISAR"


def _estado_dashboard(estado_validacion: str) -> str:
    return estado_validacion


def build_mvo(
    solicitud_path: Path,
    matriz_sap_path: Path = DEFAULT_MATRIZ_SAP,
    responsable: str = "SISTEMA",
    id_ejecucion: str | None = None,
    fecha_ejecucion: datetime | None = None,
) -> pd.DataFrame:
    """Construye la matriz operacional (una fila por solicitud)."""
    ahora = fecha_ejecucion or datetime.now()
    exec_id = id_ejecucion or ahora.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    fecha_exec = ahora.strftime("%Y-%m-%d %H:%M:%S")
    anio = ahora.strftime("%Y")
    mes = ahora.strftime("%m")
    semana = ahora.strftime("%W")

    sap = load_matriz_sap(matriz_sap_path)
    by_der: dict[str, pd.Series] = sap.attrs["by_der"]
    by_base: dict[str, pd.Series] = sap.attrs["by_base"]

    sol = load_solicitud(solicitud_path)
    archivo_origen = solicitud_path.name

    c_soc = _pick(sol, "SOCIEDAD", "Sociedad")
    c_acr = _pick(sol, "ACREEDOR", "Acreedor")
    c_mon = _pick(sol, "MONEDA", "Moneda", "MONEDA_SOLICITADA")
    c_monto = _pick(sol, "MONTO", "Importe", "IMPORTE_SOLICITADO", "MONTO_SOLICITADO")
    c_ref = _pick(sol, "REFERENCIA", "Referencia")
    c_doc = _pick(
        sol,
        "PROVISIÓN CONTABLE",
        "PROVISION CONTABLE",
        "DOCUMENTO_SOLICITUD",
        "Documento solicitud",
        "Documento",
    )
    c_fecha = _pick(sol, "FECHA_SOLICITUD", "Fecha solicitud", "FECHA", "Fecha")

    if c_ref is None:
        raise KeyError("El archivo de solicitud no tiene columna REFERENCIA")

    rows: list[dict[str, object]] = []
    for _, srow in sol.iterrows():
        sociedad = _as_str(srow[c_soc]) if c_soc else ""
        acreedor = _as_str(srow[c_acr]) if c_acr else ""
        moneda = _as_str(srow[c_mon]) if c_mon else ""
        importe = _as_str(srow[c_monto]) if c_monto else ""
        referencia = _as_str(srow[c_ref])
        doc_sol = _as_str(srow[c_doc]) if c_doc else ""
        fecha_sol = _as_str(srow[c_fecha]) if c_fecha else ""

        # Emparejar evidencia SAP: llave tecnica PM-10 = Referencia_Derivada
        sap_row = by_der.get(referencia)
        match_via = "REFERENCIA_DERIVADA" if sap_row is not None else ""
        if sap_row is None:
            # Solo si la solicitud trae la base exacta (sin inventar sufijos)
            sap_row = by_base.get(referencia)
            if sap_row is not None:
                match_via = "REFERENCIA_BASE"

        if sap_row is None:
            estado = "NO_VALIDADO"
            motivo = "NO ENCONTRADO"
            observacion = (
                f"Referencia solicitud '{referencia}' no existe en "
                "MATRIZ_VALIDADORA_TD_USD_COM (Referencia_Derivada/Base)."
            )
            proceso_encontrado = False
            proceso_completo = False
            evidencia = {
                "REFERENCIA_BASE": _referencia_base(referencia),
                "REFERENCIA_DERIVADA": referencia if "-" in referencia else "",
                "DOCUMENTO_KR31CLP": "",
                "DOCUMENTO_CAMBIO_28": "",
                "DOCUMENTO_CAMBIO_36": "",
                "DOCUMENTO_PA25USD": "",
                "VARIANTE": "",
                "ESTADO_PROCESO_SAP": "",
            }
        else:
            proceso_encontrado = True
            completo = _as_str(sap_row.get("Proceso_Completo", "")).upper() == "SI"
            tiene_pa = _as_str(sap_row.get("Tiene_PA25USD", "")).upper() == "SI"
            proceso_completo = completo
            doc_contable = _as_str(sap_row.get("Documento_Contable_Cambio_Moneda", ""))
            evidencia = {
                "REFERENCIA_BASE": _as_str(sap_row.get("Referencia_Base", "")),
                "REFERENCIA_DERIVADA": _as_str(sap_row.get("Referencia_Derivada", "")),
                "DOCUMENTO_KR31CLP": _as_str(sap_row.get("Documento_Inicial_KR31CLP", "")),
                "DOCUMENTO_CAMBIO_28": _as_str(sap_row.get("Documento_Cambio_Moneda_28", "")),
                "DOCUMENTO_CAMBIO_36": _as_str(sap_row.get("Documento_Cambio_Moneda_36", "")),
                "DOCUMENTO_PA25USD": _as_str(sap_row.get("Documento_PA25USD", "")),
                "VARIANTE": _variante_from_sap(sap_row),
                "ESTADO_PROCESO_SAP": _as_str(sap_row.get("Estado_del_proceso", "")),
            }

            if not completo:
                if not tiene_pa:
                    estado = "INCOMPLETO"
                    motivo = "SIN PA25USD"
                    observacion = (
                        "Proceso SAP encontrado pero sin DOCUMENTO_PA25USD "
                        f"(match={match_via})."
                    )
                else:
                    estado = "INCOMPLETO"
                    motivo = "PROCESO INCOMPLETO"
                    observacion = (
                        "Proceso SAP encontrado con Proceso_Completo=NO "
                        f"(match={match_via})."
                    )
            else:
                # Completo: observar si provision tesoreria != doc contable SAP
                if doc_sol and doc_contable and doc_sol != doc_contable:
                    estado = "VALIDADO_CON_OBSERVACION"
                    motivo = "PROVISION_DISTINTA_DOC_CONTABLE"
                    observacion = (
                        f"Proceso completo (match={match_via}). "
                        f"DOCUMENTO_SOLICITUD/PROVISION={doc_sol} distinto de "
                        f"Documento_Contable_Cambio_Moneda={doc_contable}."
                    )
                else:
                    estado = "VALIDADO"
                    motivo = "PROCESO COMPLETO"
                    observacion = f"Proceso SAP completo (match={match_via})."

        if estado not in ESTADOS_VALIDACION:
            raise ValueError(f"Estado invalido: {estado}")

        accion = _accion_recomendada(estado, motivo)

        rows.append(
            {
                "ID_EJECUCION": exec_id,
                "FECHA_EJECUCION": fecha_exec,
                "SOCIEDAD": sociedad,
                "ACREEDOR": acreedor,
                "DOCUMENTO_SOLICITUD": doc_sol,
                "MONEDA_SOLICITADA": moneda,
                "IMPORTE_SOLICITADO": importe,
                "FECHA_SOLICITUD": fecha_sol,
                "ARCHIVO_ORIGEN": archivo_origen,
                **evidencia,
                "PROCESO_ENCONTRADO": _si_no(proceso_encontrado),
                "PROCESO_COMPLETO": _si_no(proceso_completo),
                "ESTADO_VALIDACION": estado,
                "MOTIVO": motivo,
                "OBSERVACION": observacion,
                "ACCION_RECOMENDADA": accion,
                "AÑO": anio,
                "MES": mes,
                "SEMANA": semana,
                "RESPONSABLE": responsable,
                "ESTADO_DASHBOARD": _estado_dashboard(estado),
            }
        )

    mvo = pd.DataFrame(rows, columns=list(MVO_COLUMNS))
    return mvo


def export_mvo(mvo: pd.DataFrame, output_path: Path = DEFAULT_OUTPUT) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        mvo.to_excel(writer, sheet_name="MVO", index=False)
        ws = writer.sheets["MVO"]
        text_cols = {
            "ACREEDOR",
            "DOCUMENTO_SOLICITUD",
            "REFERENCIA_BASE",
            "REFERENCIA_DERIVADA",
            "DOCUMENTO_KR31CLP",
            "DOCUMENTO_CAMBIO_28",
            "DOCUMENTO_CAMBIO_36",
            "DOCUMENTO_PA25USD",
            "IMPORTE_SOLICITADO",
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
    solicitud_path: Path | None = None,
    matriz_sap_path: Path = DEFAULT_MATRIZ_SAP,
    output_path: Path = DEFAULT_OUTPUT,
    responsable: str = "SISTEMA",
) -> tuple[Path, pd.DataFrame]:
    sol_path = resolve_solicitud_path(solicitud_path)
    mvo = build_mvo(
        solicitud_path=sol_path,
        matriz_sap_path=matriz_sap_path,
        responsable=responsable,
    )
    out = export_mvo(mvo, output_path)
    return out, mvo
