"""
Módulo EF-03 — Tablas dinámicas operacionales.

Construye TABLAS_DINAMICAS_OPERACIONALES.xlsx desde MVO.
NO modifica datos. NO usa SAP ni MATRIZ_VALIDADORA ni RESUMEN.
NO modifica pipeline ni módulos anteriores.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MVO = ROOT / "data" / "output" / "MATRIZ_VALIDACION_OPERACIONAL.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "TABLAS_DINAMICAS_OPERACIONALES.xlsx"

ESTADOS_ORDEN: tuple[str, ...] = (
    "VALIDADO",
    "VALIDADO_CON_OBSERVACION",
    "NO_VALIDADO",
    "INCOMPLETO",
)

VARIANTES_ORDEN: tuple[str, ...] = ("KN", "KR", "SIN_VARIANTE")


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
    required = {"ESTADO_VALIDACION", "ACCION_RECOMENDADA", "SOCIEDAD"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Columnas ausentes en MVO: {sorted(missing)}")
    return df


def build_td_estado_general(mvo: pd.DataFrame) -> pd.DataFrame:
    total = len(mvo)
    estados = mvo["ESTADO_VALIDACION"].map(_as_str).str.upper()
    counts = estados.value_counts()

    rows = []
    for estado in ESTADOS_ORDEN:
        cant = int(counts.get(estado, 0))
        rows.append(
            {
                "ESTADO_VALIDACION": estado,
                "CANTIDAD_SOLICITUDES": cant,
                "PORCENTAJE": _pct(cant, total),
            }
        )
    # Estados adicionales no contemplados (si aparecieran)
    extras = sorted(set(counts.index.tolist()) - set(ESTADOS_ORDEN))
    for estado in extras:
        if not estado:
            continue
        cant = int(counts.get(estado, 0))
        rows.append(
            {
                "ESTADO_VALIDACION": estado,
                "CANTIDAD_SOLICITUDES": cant,
                "PORCENTAJE": _pct(cant, total),
            }
        )
    return pd.DataFrame(rows)


def build_td_acciones(mvo: pd.DataFrame) -> pd.DataFrame:
    acciones = mvo["ACCION_RECOMENDADA"].map(_as_str)
    acciones = acciones.map(lambda a: a if a else "(SIN_ACCION)")
    vc = acciones.value_counts()
    return pd.DataFrame(
        [
            {"ACCION_RECOMENDADA": accion, "CANTIDAD": int(cant)}
            for accion, cant in vc.items()
        ]
    )


def build_td_variantes(mvo: pd.DataFrame) -> pd.DataFrame:
    if "VARIANTE" not in mvo.columns:
        variantes = pd.Series(["SIN_VARIANTE"] * len(mvo))
    else:
        variantes = mvo["VARIANTE"].map(_as_str)
        variantes = variantes.map(
            lambda v: "SIN_VARIANTE" if (not v or v.upper() in {"(SIN_VARIANTE)", "SIN_VARIANTE"}) else v.upper()
        )
        # Normalizar etiquetas KN/KR / KN|KR
        def _norm_var(v: str) -> str:
            if v in {"KN", "KR", "SIN_VARIANTE"}:
                return v
            if v in {"KN|KR", "KR|KN"}:
                return v
            if not v:
                return "SIN_VARIANTE"
            return v

        variantes = variantes.map(_norm_var)

    counts = variantes.value_counts()
    rows = []
    seen: set[str] = set()
    for variante in VARIANTES_ORDEN:
        cant = int(counts.get(variante, 0))
        rows.append({"VARIANTE": variante, "CANTIDAD": cant})
        seen.add(variante)
    # Otras variantes (ej. KN|KR) al final, mayor a menor
    extras = [
        (v, int(c))
        for v, c in counts.items()
        if v not in seen
    ]
    extras.sort(key=lambda x: (-x[1], x[0]))
    for variante, cant in extras:
        rows.append({"VARIANTE": variante, "CANTIDAD": cant})
    return pd.DataFrame(rows)


def build_td_sociedades(mvo: pd.DataFrame) -> pd.DataFrame:
    work = mvo.copy()
    work["_soc"] = work["SOCIEDAD"].map(_as_str)
    work["_soc"] = work["_soc"].map(lambda s: s if s else "(SIN_SOCIEDAD)")
    work["_est"] = work["ESTADO_VALIDACION"].map(_as_str).str.upper()

    rows = []
    for sociedad, g in work.groupby("_soc", sort=True):
        est = g["_est"]
        rows.append(
            {
                "SOCIEDAD": sociedad,
                "CANTIDAD_SOLICITUDES": int(len(g)),
                "CANTIDAD_VALIDADAS": int((est == "VALIDADO").sum()),
                "CANTIDAD_NO_VALIDADAS": int((est == "NO_VALIDADO").sum()),
                "CANTIDAD_INCOMPLETAS": int((est == "INCOMPLETO").sum()),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["CANTIDAD_SOLICITUDES", "SOCIEDAD"], ascending=[False, True]
    ).reset_index(drop=True)


def build_tablas(mvo: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "TD_ESTADO_GENERAL": build_td_estado_general(mvo),
        "TD_ACCIONES": build_td_acciones(mvo),
        "TD_VARIANTES": build_td_variantes(mvo),
        "TD_SOCIEDADES": build_td_sociedades(mvo),
    }


def export_tablas(
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
    sheets = build_tablas(mvo)
    out = export_tablas(sheets, Path(output_path))
    return out, sheets
