"""
Simulación aislada del orquestador en modo futuro (D6).

Restricciones:
- No usa el arranque productivo del pipeline.
- No usa COM de Outlook ni Excel.
- No ejecuta el script de actualización automática.
- No escribe fuera de un directorio temp/d6_orquestador_*.
- No modifica libros de entrada; solo lectura de copias D1 si se pasan rutas.
- State y logs solo en work_dir.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ...config.config import TEMP_DIR
from ...modules.actualizacion_automatica.mail import (
    MailSendError,
    compose_mail_payload,
    mail_may_be_composed,
)
from .detection import (
    DECISION_CHANGED,
    DECISION_FAILED,
    DECISION_HISTORICAL_ANOMALY,
    DECISION_NODATA,
    DECISION_UNCHANGED,
    SourceDecision,
    build_combined_state_payload,
    plan_source_detection,
)
from .module import CombineSummary, combine_fbl1n_sources


_USE_DECISION_DATE = object()


@dataclass
class DryRunCounters:
    pipeline: int = 0
    publish: int = 0
    mail_compose: int = 0
    outlook_display: int = 0
    outlook_send: int = 0


@dataclass
class DryRunResult:
    decision: str
    message: str
    counters: DryRunCounters = field(default_factory=DryRunCounters)
    historical_rows: int | None = None
    future_rows_received: int | None = None
    future_invalid_excluded: int | None = None
    future_valid_rows: int | None = None
    final_rows: int | None = None
    latest_compensation_date: str | None = None
    mail_subject: str = ""
    mail_body_phrase: str = ""
    state_path: str = ""
    error: str = ""
    combine_summary: CombineSummary | None = None


def assert_d6_work_dir(work_dir: Path) -> Path:
    """Exigir que todas las escrituras queden bajo temp/d6_orquestador_*."""

    resolved = work_dir.resolve()
    temp_root = TEMP_DIR.resolve()
    try:
        resolved.relative_to(temp_root)
    except ValueError as exc:
        raise RuntimeError(
            f"work_dir D6 debe estar dentro de temp/: {resolved.name}"
        ) from exc
    if not any(part.startswith("d6_orquestador") for part in resolved.parts):
        raise RuntimeError("work_dir D6 debe contener d6_orquestador_*")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_d6_json(path: Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    assert_d6_work_dir(target.parent)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def load_d6_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_future_orchestrator_dry(
    *,
    work_dir: Path,
    historical_path: Path | None,
    future_path: Path | None,
    last: dict[str, Any] | None,
    historical_df: pd.DataFrame | None = None,
    future_df: pd.DataFrame | None = None,
    publish_ok: bool = True,
    latest_compensation_date: Any = _USE_DECISION_DATE,
    mail_auto_send: bool = False,
    compensation_cutoff: Any = None,
) -> DryRunResult:
    """
    Orquestador simulado: detección → combine → pipeline/publish/mail ficticios.

    mail_auto_send se ignora para envío: D6 nunca llama Display/Send.
    """

    work_dir = assert_d6_work_dir(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    counters = DryRunCounters()
    if mail_auto_send:
        # Candado D6: aunque el proceso pida send, no se instancia Outlook.
        mail_auto_send = False

    from datetime import date as date_cls
    if compensation_cutoff is None:
        compensation_cutoff = date_cls(2026, 12, 31)

    if historical_path is None or not historical_path.is_file():
        return DryRunResult(
            decision=DECISION_FAILED,
            message="El archivo FBL1N histórico no está disponible.",
            counters=counters,
            error="histórico ausente",
        )

    historical_sha = sha256_file(historical_path)
    historical_fp = {
        "path": historical_path.name,
        "size": int(historical_path.stat().st_size),
        "sha256": historical_sha,
    }

    future_available = future_path is not None and future_path.is_file()
    future_error = None
    future_file_sha = ""
    if not future_available:
        future_error = "El archivo FBL1N futuro no está disponible: FBL1N_FUTURO.xlsx."

    loaded_future = future_df
    if future_available and loaded_future is None:
        loaded_future = pd.read_excel(future_path)
        future_file_sha = sha256_file(future_path)
    elif future_available:
        future_file_sha = sha256_file(future_path)

    loaded_hist = historical_df
    if loaded_hist is None:
        loaded_hist = pd.read_excel(historical_path)
    decision = plan_source_detection(
        future_enabled=True,
        historical_fp=historical_fp,
        last=last,
        historical_df=loaded_hist,
        future_df=loaded_future,
        future_file_sha256=future_file_sha,
        future_available=future_available,
        future_error=future_error,
        compensation_cutoff=compensation_cutoff,
    )

    result = DryRunResult(
        decision=decision.status,
        message=decision.message,
        counters=counters,
        future_valid_rows=decision.future_valid_rows,
        future_invalid_excluded=decision.future_invalid_rows,
        latest_compensation_date=decision.latest_compensation_date,
    )

    if decision.status in {
        DECISION_UNCHANGED,
        DECISION_NODATA,
        DECISION_FAILED,
        DECISION_HISTORICAL_ANOMALY,
    }:
        return result

    if decision.status != DECISION_CHANGED:
        result.error = f"decisión no controlada: {decision.status}"
        return result

    if loaded_hist is None:
        loaded_hist = pd.read_excel(historical_path)
    if loaded_future is None:
        result.decision = DECISION_FAILED
        result.error = "futuro no cargado"
        return result

    combined = combine_fbl1n_sources(
        loaded_hist,
        loaded_future,
        compensation_cutoff=compensation_cutoff,
    )
    summary = combined.summary
    result.combine_summary = summary
    result.historical_rows = summary.historical_rows
    result.future_rows_received = summary.future_rows_received
    result.future_invalid_excluded = summary.future_invalid_excluded
    result.final_rows = summary.final_rows

    counters.pipeline += 1
    counters.publish += 1
    if not publish_ok:
        result.error = "publicación simulada Failed"
        return result

    if latest_compensation_date is _USE_DECISION_DATE:
        iso_date = decision.latest_compensation_date
    else:
        iso_date = latest_compensation_date

    if not mail_may_be_composed(
        future_enabled=True,
        decision=decision.status,
        publish_ok=True,
    ):
        return result

    try:
        payload = compose_mail_payload(
            to="destinatario@example.test",
            sharepoint="https://example.test/sharepoint",
            powerbi="https://example.test/powerbi",
            latest_compensation_date=iso_date,
            future_enabled=True,
        )
    except MailSendError as exc:
        result.error = str(exc)
        return result

    counters.mail_compose += 1
    result.mail_subject = payload.subject
    phrase = (
        "Información actualizada hasta la fecha de compensación "
        f"{_visible(iso_date)}."
    )
    if phrase in payload.body and phrase in (payload.html_body or ""):
        result.mail_body_phrase = phrase

    stamp = datetime.now().isoformat(timespec="seconds")
    state_payload = build_combined_state_payload(
        historical_fp=historical_fp,
        decision=decision,
        started_at=stamp,
        last_success_at=stamp,
        fbl1n_rows=summary.final_rows,
        matrix_rows=summary.final_rows,
        months=["2026-09"],
        matriz="SIMULATED_MATRIZ.xlsx",
        dinamicas="SIMULATED_DINAMICAS.xlsx",
        actual="SIMULATED_ACTUAL.xlsx",
        log="d6_orquestador.log",
    )
    state_path = work_dir / "pipeline_state.json"
    write_d6_json(state_path, state_payload)
    result.state_path = state_path.name
    return result


def _visible(iso_date: str | None) -> str:
    text = str(iso_date or "")
    if len(text) != 10:
        return ""
    year, month, day = text.split("-")
    return f"{day}/{month}/{year}"
