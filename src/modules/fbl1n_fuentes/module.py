"""
Combinador FBL1N histórico + futuro.

Opera solo sobre DataFrames recibidos. No carga archivos, no toca
01_INPUT, no importa Application, orquestador, SAP ni correo.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


EXPECTED_COLUMNS: tuple[str, ...] = (
    "Bloqueo de pago",
    "Clase de documento",
    "Referencia",
    "Importe en moneda doc.",
    "Moneda del documento",
    "Importe valorado ML2",
    "Mon.local 2",
    "Importe en moneda local",
    "Moneda local",
    "Fecha de documento",
    "Fecha contabiliz.",
    "Sociedad",
    "Acreedor",
    "Name",
    "Nº documento",
    "Doc.compensación",
    "Fecha compensación",
    "Texto cab.documento",
    "Documento compras",
    "Tp.cambio efectivo",
    "Clave contabiliz.",
)

SOCIEDAD_COL = "Sociedad"
FECHA_COMP_COL = "Fecha compensación"
NULL_MARK = "<NULL>"
FIELD_SEP = "\x1f"
EXCEL_EPOCH = datetime(1899, 12, 30)

_DATE_COLUMNS = frozenset(
    {
        "Fecha de documento",
        "Fecha contabiliz.",
        "Fecha compensación",
    }
)
_NUMERIC_COLUMNS = frozenset(
    {
        "Importe en moneda doc.",
        "Importe valorado ML2",
        "Importe en moneda local",
        "Acreedor",
        "Nº documento",
        "Doc.compensación",
        "Documento compras",
        "Tp.cambio efectivo",
        "Clave contabiliz.",
    }
)

STATUS_SUCCEEDED = "Succeeded"
STATUS_NODATA = "NoData"


class CombineError(Exception):
    """Error de contrato o de estructura al combinar fuentes FBL1N."""


class CompensationCutoffError(CombineError):
    """Corte de compensación ausente, inválido o violado por el histórico."""


class FutureFbl1nError(Exception):
    """Error controlado al integrar el FBL1N futuro."""


class FutureFbl1nUnavailableError(FutureFbl1nError):
    """Archivo futuro ausente, bloqueado, ilegible o con estructura incompatible."""


class FutureFbl1nNoDataError(FutureFbl1nError):
    """Modo futuro habilitado pero sin partidas válidas; no se procesa solo el histórico."""


@dataclass(frozen=True)
class CombineSummary:
    status: str
    historical_rows: int
    future_rows_received: int
    future_invalid_excluded: int
    future_cutoff_excluded: int
    cross_matches_excluded: int
    final_rows: int
    columns: int


@dataclass(frozen=True)
class CombineResult:
    combined: pd.DataFrame
    summary: CombineSummary


def parse_compensation_cutoff(raw: str | date | None) -> date:
    """Parsear corte YYYY-MM-DD. Vacío/None/inválido → CompensationCutoffError."""

    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise CompensationCutoffError(
            "FBL1N_COMPENSATION_CUTOFF ausente; se exige YYYY-MM-DD en modo futuro."
        )
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match is None:
        raise CompensationCutoffError(
            f"FBL1N_COMPENSATION_CUTOFF inválido ({text!r}); se exige YYYY-MM-DD."
        )
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise CompensationCutoffError(
            f"FBL1N_COMPENSATION_CUTOFF inválido ({text!r}); no es una fecha calendario."
        ) from exc


def combine_fbl1n_sources(
    historical_df: pd.DataFrame,
    future_df: pd.DataFrame,
    *,
    compensation_cutoff: date | str | None = None,
) -> CombineResult:
    """Combinar histórico protegido y futuro SAP según reglas D1.1 (+ corte opcional)."""

    if not isinstance(historical_df, pd.DataFrame):
        raise CombineError("El histórico no es un DataFrame.")
    if future_df is None:
        raise CombineError("El futuro no fue recibido.")
    if not isinstance(future_df, pd.DataFrame):
        raise CombineError("El futuro no es un DataFrame legible.")

    historical = historical_df.copy()
    future = future_df.copy()

    _validate_columns(historical, "histórico")
    _validate_columns(future, "futuro")
    if list(historical.columns) != list(future.columns):
        _raise_column_mismatch(historical, future)

    if historical.empty:
        raise CombineError("El DataFrame histórico está vacío.")

    cutoff: date | None = None
    if compensation_cutoff is not None:
        cutoff = parse_compensation_cutoff(compensation_cutoff)
        assert_historical_within_cutoff(historical, cutoff)

    valid_mask = _required_fields_present(future)
    invalid_count = int((~valid_mask).sum())
    future_valid = future.loc[valid_mask].copy()

    cutoff_excluded = 0
    if cutoff is not None:
        within = _compensation_within_cutoff_mask(future_valid, cutoff)
        cutoff_excluded = int((~within).sum())
        future_valid = future_valid.loc[within].copy()

    historical_fps = set(fingerprint_frame(historical))
    future_fps = fingerprint_frame(future_valid)
    cross_mask = future_fps.isin(historical_fps)
    cross_count = int(cross_mask.sum())
    future_kept = future_valid.loc[~cross_mask].copy()

    combined = pd.concat([historical, future_kept], ignore_index=True)

    if len(future_kept) > 0:
        status = STATUS_SUCCEEDED
    elif cutoff is not None and cutoff_excluded > 0:
        # Cierre: futuro solo traía fechas > corte; el histórico permanece.
        status = STATUS_SUCCEEDED
    else:
        status = STATUS_NODATA

    summary = CombineSummary(
        status=status,
        historical_rows=int(len(historical)),
        future_rows_received=int(len(future)),
        future_invalid_excluded=invalid_count,
        future_cutoff_excluded=cutoff_excluded,
        cross_matches_excluded=cross_count,
        final_rows=int(len(combined)),
        columns=int(len(combined.columns)),
    )
    return CombineResult(combined=combined, summary=summary)


def fingerprint_frame(frame: pd.DataFrame) -> pd.Series:
    """Huella SHA256 por fila, en el orden de columnas del DataFrame."""

    if frame.empty:
        return pd.Series(dtype=str)
    columns = list(frame.columns)
    values: list[str] = []
    for row in frame.itertuples(index=False, name=None):
        values.append(fingerprint_row(columns, row))
    return pd.Series(values, index=frame.index, dtype=str)


def fingerprint_row(columns: list[str], values: tuple[Any, ...]) -> str:
    """Huella determinista de una fila (21 columnas en orden original)."""

    parts = [
        _canonical_cell(column, value)
        for column, value in zip(columns, values, strict=True)
    ]
    payload = FIELD_SEP.join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_columns(frame: pd.DataFrame, label: str) -> None:
    columns = list(frame.columns)
    missing = [name for name in EXPECTED_COLUMNS if name not in columns]
    extra = [name for name in columns if name not in EXPECTED_COLUMNS]
    if missing:
        raise CombineError(
            f"El {label} no tiene columnas obligatorias: {missing}."
        )
    if extra:
        raise CombineError(
            f"El {label} tiene columnas adicionales: {extra}."
        )
    if len(columns) != len(EXPECTED_COLUMNS):
        raise CombineError(
            f"El {label} debe tener {len(EXPECTED_COLUMNS)} columnas; "
            f"tiene {len(columns)}."
        )
    if columns != list(EXPECTED_COLUMNS):
        raise CombineError(
            f"El {label} tiene un orden de columnas incompatible."
        )
    if SOCIEDAD_COL not in columns:
        raise CombineError(f"El {label} no tiene la columna {SOCIEDAD_COL!r}.")
    if FECHA_COMP_COL not in columns:
        raise CombineError(
            f"El {label} no tiene la columna {FECHA_COMP_COL!r}."
        )


def _raise_column_mismatch(
    historical: pd.DataFrame,
    future: pd.DataFrame,
) -> None:
    hist_cols = list(historical.columns)
    fut_cols = list(future.columns)
    missing = [name for name in hist_cols if name not in fut_cols]
    extra = [name for name in fut_cols if name not in hist_cols]
    if missing:
        raise CombineError(
            f"El futuro no tiene columnas presentes en el histórico: {missing}."
        )
    if extra:
        raise CombineError(
            f"El futuro tiene columnas adicionales respecto del histórico: {extra}."
        )
    raise CombineError("El futuro tiene un orden de columnas incompatible.")


def _required_fields_present(frame: pd.DataFrame) -> pd.Series:
    sociedad = frame[SOCIEDAD_COL].map(_is_present)
    fecha = frame[FECHA_COMP_COL].map(_is_present)
    return sociedad & fecha


def _is_present(value: Any) -> bool:
    return _canonical_text_or_null(value) != NULL_MARK


def _canonical_cell(column: str, value: Any) -> str:
    if column in _DATE_COLUMNS:
        return _canonical_date(value)
    if column in _NUMERIC_COLUMNS:
        return _canonical_number(value)
    return _canonical_text_or_null(value)


def _canonical_text_or_null(value: Any) -> str:
    if _is_null(value):
        return NULL_MARK
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return _canonical_date(value)
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "nat", "<na>"}:
        return NULL_MARK
    return text


def _canonical_date(value: Any) -> str:
    if _is_null(value):
        return NULL_MARK
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return NULL_MARK
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        text = str(value).strip()
        return NULL_MARK if text == "" else text
    return parsed.date().isoformat()


def _canonical_number(value: Any) -> str:
    if _is_null(value):
        return NULL_MARK
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (pd.Timestamp, datetime, date)):
        serial = _excel_serial(value)
        if serial is None:
            return NULL_MARK
        return _format_decimal(serial)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return NULL_MARK
        return _format_decimal(value)
    if isinstance(value, Decimal):
        return _format_decimal(value)
    text = str(value).strip()
    if text == "":
        return NULL_MARK
    parsed = _parse_regional_number(text)
    if parsed is None:
        return text
    return _format_decimal(parsed)


def _excel_serial(value: Any) -> float | None:
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        value = value.to_pydatetime()
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if not isinstance(value, datetime):
        return None
    delta = value.replace(tzinfo=None) - EXCEL_EPOCH
    return delta.total_seconds() / 86400.0


def _parse_regional_number(text: str) -> Decimal | None:
    compact = text.replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", compact):
        compact = compact.replace(".", "").replace(",", ".")
    elif "," in compact and "." not in compact:
        compact = compact.replace(",", ".")
    try:
        return Decimal(compact)
    except InvalidOperation:
        return None


def _format_decimal(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return str(value)
    if number == number.to_integral_value():
        return str(int(number))
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return False


SEMANTIC_VERSION = "fbl1n-semantic-v1"
COMBINED_IDENTITY_VERSION = "fbl1n-combined-v1"
COMBINED_IDENTITY_VERSION_V2 = "fbl1n-combined-v2"
IDENTITY_VERSION_V2 = "fbl1n-combined-v2"


@dataclass(frozen=True)
class SemanticFingerprint:
    sha256: str
    valid_rows: int
    invalid_rows: int
    cutoff_excluded_rows: int
    latest_compensation_date: str | None
    columns: tuple[str, ...]
    version: str = SEMANTIC_VERSION


def assert_historical_within_cutoff(
    historical_df: pd.DataFrame,
    cutoff: date,
) -> None:
    """Abortar si el histórico válido tiene Fecha compensación > cutoff."""

    if historical_df is None or not isinstance(historical_df, pd.DataFrame):
        raise CombineError("La fuente FBL1N histórica no es un DataFrame legible.")
    _validate_columns(historical_df, "histórico")
    valid = historical_df.loc[_required_fields_present(historical_df)]
    if valid.empty:
        return
    beyond = ~_compensation_within_cutoff_mask(valid, cutoff)
    if bool(beyond.any()):
        raise CompensationCutoffError(
            "El FBL1N histórico contiene Fecha compensación posterior al corte "
            f"{cutoff.isoformat()}; no se oculta silenciosamente."
        )


def _parse_compensation_date_value(value: Any) -> date | None:
    text = _canonical_date(value)
    if text == NULL_MARK:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _compensation_within_cutoff_mask(
    frame: pd.DataFrame,
    cutoff: date,
) -> pd.Series:
    """True si la fecha es parseable y <= cutoff. Fechas no ISO → False (excluir)."""

    flags: list[bool] = []
    for value in frame[FECHA_COMP_COL]:
        parsed = _parse_compensation_date_value(value)
        flags.append(parsed is not None and parsed <= cutoff)
    return pd.Series(flags, index=frame.index, dtype=bool)


def semantic_fbl1n_fingerprint(
    source_df: pd.DataFrame,
    *,
    compensation_cutoff: date | str | None = None,
    enforce_historical_bound: bool = False,
) -> SemanticFingerprint:
    """
    Huella semántica de una fuente FBL1N (21 columnas; datos, no el archivo).

    Sirve para histórico y futuro. Excluye filas sin Sociedad o Fecha
    compensación. Conserva multiplicidad. El orden de filas no altera el SHA256.

    Con compensation_cutoff: tras validar columnas/campos, excluye del hash las
    filas con Fecha compensación > corte (futuro). Si enforce_historical_bound,
    aborta ante cualquier fecha histórica > corte.
    """

    if source_df is None or not isinstance(source_df, pd.DataFrame):
        raise CombineError("La fuente FBL1N no es un DataFrame legible.")

    frame = source_df.copy()
    _validate_columns(frame, "FBL1N")
    valid_mask = _required_fields_present(frame)
    invalid_rows = int((~valid_mask).sum())
    valid = frame.loc[valid_mask]

    cutoff: date | None = None
    cutoff_excluded = 0
    if compensation_cutoff is not None:
        cutoff = parse_compensation_cutoff(compensation_cutoff)
        if enforce_historical_bound:
            assert_historical_within_cutoff(frame, cutoff)
        within = _compensation_within_cutoff_mask(valid, cutoff)
        cutoff_excluded = int((~within).sum())
        valid = valid.loc[within]

    ordered = sorted(fingerprint_frame(valid).tolist())
    payload = (SEMANTIC_VERSION + "\n" + "\n".join(ordered)).encode("utf-8")
    return SemanticFingerprint(
        sha256=hashlib.sha256(payload).hexdigest(),
        valid_rows=int(len(valid)),
        invalid_rows=invalid_rows,
        cutoff_excluded_rows=cutoff_excluded,
        latest_compensation_date=_latest_compensation_date(valid),
        columns=tuple(EXPECTED_COLUMNS),
        version=SEMANTIC_VERSION,
    )


def combined_source_sha256(
    historical_file_sha256: str,
    future_semantic_sha256: str,
) -> str:
    """Identidad combinada v1 (P3.2): SHA físico histórico + semántica futura."""

    payload = (
        f"{COMBINED_IDENTITY_VERSION}\n"
        f"{historical_file_sha256}\n"
        f"{future_semantic_sha256}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def combined_source_sha256_v1(
    historical_file_sha256: str,
    future_semantic_sha256: str,
) -> str:
    """Alias explícito de la identidad v1 para auditar P3.2."""

    return combined_source_sha256(historical_file_sha256, future_semantic_sha256)


def combined_semantic_sha256(
    historical_semantic_sha256: str,
    future_semantic_sha256: str,
) -> str:
    """Identidad combinada v2: semántica histórica + semántica futura."""

    payload = (
        f"{COMBINED_IDENTITY_VERSION_V2}\n"
        f"{historical_semantic_sha256}\n"
        f"{future_semantic_sha256}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _latest_compensation_date(valid: pd.DataFrame) -> str | None:
    if valid.empty or FECHA_COMP_COL not in valid.columns:
        return None
    dates: list[str] = []
    for value in valid[FECHA_COMP_COL]:
        text = _canonical_date(value)
        if text != NULL_MARK:
            dates.append(text)
    if not dates:
        return None
    return max(dates)
