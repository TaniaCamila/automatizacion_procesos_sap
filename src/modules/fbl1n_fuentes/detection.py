"""
Detección semántica y estado combinado FBL1N (histórico + futuro).

No importa Application, SAP, correo ni publicación.
No escribe state productivo: el llamador decide la ruta.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .module import (
    CombineError,
    CompensationCutoffError,
    IDENTITY_VERSION_V2,
    combined_semantic_sha256,
    combined_source_sha256,
    parse_compensation_cutoff,
    semantic_fbl1n_fingerprint,
)


STATE_SCHEMA_VERSION = "2"
SOURCE_MODE_HISTORICAL = "historical_only"
SOURCE_MODE_PLUS_FUTURE = "historical_plus_future"

DECISION_UNCHANGED = "Unchanged"
DECISION_CHANGED = "Changed"
DECISION_NODATA = "NoData"
DECISION_FAILED = "Failed"
DECISION_HISTORICAL_ANOMALY = "HistoricalAnomaly"

GUARD_OK = "ok"
GUARD_FIRST_RUN = "first_run"
GUARD_LEGACY_MIGRATE = "legacy_migrate"
GUARD_ANOMALY = "anomaly"

MIGRATION_REQUIRED_MESSAGE = (
    "El estado combinado no tiene identity_version "
    f"{IDENTITY_VERSION_V2}. Se requiere la utilidad de migración de "
    "identidad; no se procesa ni se actualiza la línea base."
)


class HistoricalFbl1nChangedError(Exception):
    """El histórico protegido no coincide con la línea base del estado."""


@dataclass(frozen=True)
class SourceDecision:
    status: str
    message: str
    source_mode: str
    historical_file_sha256: str = ""
    historical_semantic_sha256: str = ""
    future_file_sha256: str = ""
    future_semantic_sha256: str = ""
    combined_source_sha256: str = ""
    combined_semantic_sha256: str = ""
    source_fbl1n_sha256: str = ""
    identity_version: str = ""
    future_valid_rows: int = 0
    future_invalid_rows: int = 0
    latest_compensation_date: str | None = None
    columns: int = 0
    migrate_from_legacy: bool = False
    first_run: bool = False


def is_combined_state(last: dict[str, Any] | None) -> bool:
    if not last:
        return False
    if str(last.get("source_mode") or "") == SOURCE_MODE_PLUS_FUTURE:
        return True
    if str(last.get("schema_version") or "") == STATE_SCHEMA_VERSION:
        return True
    return bool(last.get("combined_source_sha256"))


def is_same_historical_file(
    current: dict[str, Any],
    last: dict[str, Any] | None,
) -> bool:
    """Equivalente a is_same_fbl1n: hash físico + tamaño; ignora mtime."""

    if last is None:
        return False
    return (
        current.get("sha256") == last.get("sha256")
        and int(current.get("size") or 0) == int(last.get("size") or 0)
    )


def historical_sha_from_state(last: dict[str, Any] | None) -> str:
    if not last:
        return ""
    return str(last.get("historical_file_sha256") or last.get("sha256") or "")


def has_v2_identity(last: dict[str, Any] | None) -> bool:
    if not last:
        return False
    return (
        str(last.get("identity_version") or "") == IDENTITY_VERSION_V2
        and bool(str(last.get("historical_semantic_sha256") or "").strip())
        and bool(str(last.get("combined_semantic_sha256") or "").strip())
    )


def check_historical_guard(
    current_historical_sha256: str,
    last: dict[str, Any] | None,
) -> str:
    if last is None:
        return GUARD_FIRST_RUN
    current = str(current_historical_sha256 or "")
    if is_combined_state(last):
        if not has_v2_identity(last):
            return GUARD_ANOMALY
        return GUARD_OK
    legacy_sha = str(last.get("sha256") or "")
    if not legacy_sha:
        return GUARD_FIRST_RUN
    if legacy_sha != current:
        return GUARD_ANOMALY
    return GUARD_LEGACY_MIGRATE


def publication_source_sha256(
    *,
    future_enabled: bool,
    historical_sha256: str,
    combined_sha256: str,
) -> str:
    """Alias compatible para publicación/correo (anti-duplicado)."""

    if future_enabled:
        return str(combined_sha256 or "")
    return str(historical_sha256 or "")


def plan_source_detection(
    *,
    future_enabled: bool,
    historical_fp: dict[str, Any],
    last: dict[str, Any] | None,
    future_df: pd.DataFrame | None = None,
    historical_df: pd.DataFrame | None = None,
    future_file_sha256: str = "",
    future_available: bool = True,
    future_error: str | None = None,
    compensation_cutoff: Any = None,
    logger: logging.Logger | None = None,
) -> SourceDecision:
    """Decidir Unchanged/Changed/NoData/Failed/HistoricalAnomaly sin I/O de state."""

    from datetime import date as date_cls

    historical_sha = str(historical_fp.get("sha256") or "")
    if not future_enabled:
        return _plan_historical_only(historical_fp, last, logger=logger)

    try:
        if compensation_cutoff is None:
            from ...config.config import FBL1N_COMPENSATION_CUTOFF

            compensation_cutoff = FBL1N_COMPENSATION_CUTOFF
        cutoff = parse_compensation_cutoff(compensation_cutoff)
    except CompensationCutoffError as exc:
        _log(logger, "Decisión=%s corte inválido/ausente", DECISION_FAILED)
        return SourceDecision(
            status=DECISION_FAILED,
            message=str(exc),
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            first_run=False,
        )

    guard = check_historical_guard(historical_sha, last)
    if guard == GUARD_ANOMALY:
        if last is not None and is_combined_state(last) and not has_v2_identity(last):
            message = MIGRATION_REQUIRED_MESSAGE
        else:
            message = (
                "El FBL1N histórico protegido no coincide con el estado anterior. "
                "Se requiere validación; no se procesa ni se actualiza la línea base."
            )
        _log(logger, "Decisión=%s", DECISION_HISTORICAL_ANOMALY)
        return SourceDecision(
            status=DECISION_HISTORICAL_ANOMALY,
            message=message,
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            first_run=False,
        )

    if not future_available or future_error:
        message = future_error or "El archivo FBL1N futuro no está disponible."
        _log(logger, "Decisión=%s", DECISION_FAILED)
        return SourceDecision(
            status=DECISION_FAILED,
            message=message,
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            first_run=guard == GUARD_FIRST_RUN,
            migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
        )

    try:
        hist_semantic = semantic_fbl1n_fingerprint(
            historical_df,
            compensation_cutoff=cutoff,
            enforce_historical_bound=True,
        )
    except CompensationCutoffError as exc:
        _log(logger, "Decisión=%s histórico supera corte", DECISION_FAILED)
        return SourceDecision(
            status=DECISION_FAILED,
            message=str(exc),
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            first_run=guard == GUARD_FIRST_RUN,
            migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
        )
    except CombineError as exc:
        _log(logger, "Decisión=%s estructura histórica incompatible", DECISION_FAILED)
        return SourceDecision(
            status=DECISION_FAILED,
            message=f"El FBL1N histórico tiene estructura incompatible: {exc}",
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            first_run=guard == GUARD_FIRST_RUN,
            migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
        )

    try:
        semantic = semantic_fbl1n_fingerprint(
            future_df,
            compensation_cutoff=cutoff,
            enforce_historical_bound=False,
        )
    except CombineError as exc:
        _log(logger, "Decisión=%s estructura incompatible", DECISION_FAILED)
        return SourceDecision(
            status=DECISION_FAILED,
            message=f"El FBL1N futuro tiene estructura incompatible: {exc}",
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            historical_semantic_sha256=hist_semantic.sha256,
            first_run=guard == GUARD_FIRST_RUN,
            migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
        )

    _log(
        logger,
        "FBL1N futuro semántico: validas=%d invalidas=%d corte_excluidas=%d "
        "fecha_max=%s cutoff=%s columnas=%d",
        semantic.valid_rows,
        semantic.invalid_rows,
        semantic.cutoff_excluded_rows,
        semantic.latest_compensation_date or "-",
        cutoff.isoformat() if isinstance(cutoff, date_cls) else cutoff,
        len(semantic.columns),
    )

    combined_semantic = combined_semantic_sha256(
        hist_semantic.sha256, semantic.sha256
    )
    combined_v1 = combined_source_sha256(historical_sha, semantic.sha256)

    date_candidates = [
        value
        for value in (
            hist_semantic.latest_compensation_date,
            semantic.latest_compensation_date,
        )
        if value
    ]
    latest_combined_date = max(date_candidates) if date_candidates else None

    if semantic.valid_rows == 0 and semantic.cutoff_excluded_rows == 0:
        _log(logger, "Decisión=%s", DECISION_NODATA)
        return SourceDecision(
            status=DECISION_NODATA,
            message=(
                "FBL1N futuro sin partidas válidas (NoData); "
                f"futuro_invalido={semantic.invalid_rows}."
            ),
            source_mode=SOURCE_MODE_PLUS_FUTURE,
            historical_file_sha256=historical_sha,
            historical_semantic_sha256=hist_semantic.sha256,
            future_file_sha256=str(future_file_sha256 or ""),
            future_semantic_sha256=semantic.sha256,
            combined_semantic_sha256=combined_semantic,
            identity_version=IDENTITY_VERSION_V2,
            future_valid_rows=semantic.valid_rows,
            future_invalid_rows=semantic.invalid_rows,
            latest_compensation_date=latest_combined_date,
            columns=len(semantic.columns),
            first_run=guard == GUARD_FIRST_RUN,
            migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
        )

    previous_semantic = str((last or {}).get("combined_semantic_sha256") or "")
    unchanged = (
        guard == GUARD_OK
        and has_v2_identity(last)
        and bool(previous_semantic)
        and previous_semantic == combined_semantic
    )
    if unchanged:
        status = DECISION_UNCHANGED
        message = "FBL1N combinado sin cambios semánticos"
        alias = str(
            (last or {}).get("combined_source_sha256")
            or (last or {}).get("source_fbl1n_sha256")
            or combined_v1
        )
        combined_alias = alias
    else:
        status = DECISION_CHANGED
        alias = publication_source_sha256(
            future_enabled=True,
            historical_sha256=historical_sha,
            combined_sha256=combined_v1,
        )
        combined_alias = combined_v1
        if guard == GUARD_FIRST_RUN:
            message = "Primera ejecución combinada; se establecerá línea base tras el éxito"
        elif guard == GUARD_LEGACY_MIGRATE:
            message = (
                "Migración desde state legado coincidente; "
                "primera ejecución con futuro"
            )
        else:
            message = "Cambio semántico en el FBL1N combinado"

    _log(logger, "Identidad combinada calculada; alias publicación activo")
    _log(logger, "Decisión=%s", status)
    return SourceDecision(
        status=status,
        message=message,
        source_mode=SOURCE_MODE_PLUS_FUTURE,
        historical_file_sha256=historical_sha,
        historical_semantic_sha256=hist_semantic.sha256,
        future_file_sha256=str(future_file_sha256 or ""),
        future_semantic_sha256=semantic.sha256,
        combined_source_sha256=combined_alias,
        combined_semantic_sha256=combined_semantic,
        source_fbl1n_sha256=alias,
        identity_version=IDENTITY_VERSION_V2,
        future_valid_rows=semantic.valid_rows,
        future_invalid_rows=semantic.invalid_rows,
        latest_compensation_date=latest_combined_date,
        columns=len(semantic.columns),
        first_run=guard == GUARD_FIRST_RUN,
        migrate_from_legacy=guard == GUARD_LEGACY_MIGRATE,
    )


def build_combined_state_payload(
    *,
    historical_fp: dict[str, Any],
    decision: SourceDecision,
    started_at: str,
    last_success_at: str,
    fbl1n_rows: int | None,
    matrix_rows: int | None,
    months: list[str],
    matriz: str,
    dinamicas: str,
    actual: str,
    log: str,
) -> dict[str, Any]:
    """Estado versionado; conserva campos legados del histórico físico."""

    payload = {
        **historical_fp,
        "schema_version": STATE_SCHEMA_VERSION,
        "source_mode": SOURCE_MODE_PLUS_FUTURE,
        "identity_version": decision.identity_version or IDENTITY_VERSION_V2,
        "historical_file_sha256": decision.historical_file_sha256,
        "historical_semantic_sha256": decision.historical_semantic_sha256,
        "future_file_sha256": decision.future_file_sha256,
        "future_semantic_sha256": decision.future_semantic_sha256,
        "combined_source_sha256": decision.combined_source_sha256,
        "combined_semantic_sha256": decision.combined_semantic_sha256,
        "source_fbl1n_sha256": decision.source_fbl1n_sha256,
        "future_valid_rows": decision.future_valid_rows,
        "future_invalid_rows": decision.future_invalid_rows,
        "latest_compensation_date": decision.latest_compensation_date,
        "last_success_at": last_success_at,
        "started_at": started_at,
        "fbl1n_rows": fbl1n_rows,
        "matrix_rows": matrix_rows,
        "months": list(months or []),
        "matriz": matriz,
        "dinamicas": dinamicas,
        "actual": actual,
        "log": log,
    }
    return payload


def _plan_historical_only(
    historical_fp: dict[str, Any],
    last: dict[str, Any] | None,
    *,
    logger: logging.Logger | None = None,
) -> SourceDecision:
    historical_sha = str(historical_fp.get("sha256") or "")
    same = is_same_historical_file(historical_fp, last)
    status = DECISION_UNCHANGED if same else DECISION_CHANGED
    _log(logger, "Decisión=%s modo=%s", status, SOURCE_MODE_HISTORICAL)
    return SourceDecision(
        status=status,
        message="FBL1N histórico sin cambios" if same else "Cambio en FBL1N histórico",
        source_mode=SOURCE_MODE_HISTORICAL,
        historical_file_sha256=historical_sha,
        source_fbl1n_sha256=historical_sha,
        first_run=last is None,
    )


def _log(logger: logging.Logger | None, message: str, *args: Any) -> None:
    if logger is not None:
        logger.info(message, *args)
