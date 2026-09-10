"""P8E — corte FBL1N_COMPENSATION_CUTOFF=2026-08-31 (sin Outlook/pipeline)."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from src.modules.actualizacion_automatica.mail import (
    POWERBI_UPDATE_NOTICE,
    build_mail_subject,
    compose_mail_payload,
)
from src.modules.fbl1n_fuentes.detection import (
    DECISION_CHANGED,
    DECISION_FAILED,
    DECISION_UNCHANGED,
    IDENTITY_VERSION_V2,
    SOURCE_MODE_PLUS_FUTURE,
    STATE_SCHEMA_VERSION,
    plan_source_detection,
)
from src.modules.fbl1n_fuentes.module import (
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    SOCIEDAD_COL,
    STATUS_SUCCEEDED,
    CompensationCutoffError,
    combine_fbl1n_sources,
    parse_compensation_cutoff,
    semantic_fbl1n_fingerprint,
)

CUTOFF = date(2026, 8, 31)
FAKE_SP = "https://example.test/sharepoint"


def _blank_row(**overrides: object) -> dict[str, object]:
    row = {column: None for column in EXPECTED_COLUMNS}
    row.update(overrides)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(EXPECTED_COLUMNS))


def _hist(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL44",
        FECHA_COMP_COL: date(2026, 8, 31),
        "Referencia": "H1",
        "Importe en moneda doc.": 100,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _fut(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL45",
        FECHA_COMP_COL: date(2026, 9, 1),
        "Referencia": "F1",
        "Importe en moneda doc.": 200,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _fp(sha: str = "hist-sha", size: int = 10) -> dict[str, object]:
    return {"sha256": sha, "size": size}


def _baseline_state(hist_df: pd.DataFrame, fut_df: pd.DataFrame) -> dict[str, object]:
    decision = plan_source_detection(
        future_enabled=True,
        historical_fp=_fp(),
        last=None,
        historical_df=hist_df,
        future_df=fut_df,
        future_file_sha256="fut-file",
        compensation_cutoff=CUTOFF,
    )
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "source_mode": SOURCE_MODE_PLUS_FUTURE,
        "identity_version": IDENTITY_VERSION_V2,
        "sha256": "hist-sha",
        "size": 10,
        "historical_file_sha256": "hist-sha",
        "historical_semantic_sha256": decision.historical_semantic_sha256,
        "combined_semantic_sha256": decision.combined_semantic_sha256,
        "combined_source_sha256": decision.combined_source_sha256,
        "source_fbl1n_sha256": decision.source_fbl1n_sha256,
        "future_semantic_sha256": decision.future_semantic_sha256,
    }


class CompensationCutoffParseTests(unittest.TestCase):
    def test_valid_cutoff(self) -> None:
        self.assertEqual(parse_compensation_cutoff("2026-08-31"), CUTOFF)
        self.assertEqual(parse_compensation_cutoff(CUTOFF), CUTOFF)

    def test_absent_or_invalid_fail_closed(self) -> None:
        for raw in (None, "", "  ", "31/08/2026", "2026-13-01", "agosto"):
            with self.subTest(raw=raw):
                with self.assertRaises(CompensationCutoffError):
                    parse_compensation_cutoff(raw)

    def test_detection_absent_cutoff_failed(self) -> None:
        hist = _frame(_hist())
        fut = _frame(_fut())
        with patch(
            "src.config.config.FBL1N_COMPENSATION_CUTOFF",
            None,
        ):
            decision = plan_source_detection(
                future_enabled=True,
                historical_fp=_fp(),
                last=None,
                historical_df=hist,
                future_df=fut,
                compensation_cutoff=None,
            )
        self.assertEqual(decision.status, DECISION_FAILED)
        self.assertIn("COMPENSATION_CUTOFF", decision.message)


class CutoffSemanticAndCombineTests(unittest.TestCase):
    def test_future_keeps_only_on_or_before_cutoff(self) -> None:
        hist = _frame(_hist(Referencia="H-ONLY"))
        fut = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 8, 31), "Referencia": "ON-CUT"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "D01"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 2), "Referencia": "D02"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 3), "Referencia": "D03"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 4), "Referencia": "D04"}),
        )
        sem = semantic_fbl1n_fingerprint(fut, compensation_cutoff=CUTOFF)
        self.assertEqual(sem.valid_rows, 1)
        self.assertEqual(sem.cutoff_excluded_rows, 4)
        self.assertEqual(sem.latest_compensation_date, "2026-08-31")

        combined = combine_fbl1n_sources(hist, fut, compensation_cutoff=CUTOFF)
        self.assertEqual(combined.summary.future_cutoff_excluded, 4)
        self.assertEqual(combined.summary.final_rows, 2)
        refs = set(combined.combined["Referencia"].astype(str))
        self.assertIn("ON-CUT", refs)
        self.assertIn("H-ONLY", refs)
        for bad in ("D01", "D02", "D03", "D04"):
            self.assertNotIn(bad, refs)

    def test_post_cutoff_additions_unchanged(self) -> None:
        hist = _frame(_hist())
        fut_base = _frame(_fut(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "SEP1"}))
        last = _baseline_state(hist, fut_base)
        fut_more = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "SEP1"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 2), "Referencia": "SEP2"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 4), "Referencia": "SEP4"}),
        )
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=_fp(),
            last=last,
            historical_df=hist,
            future_df=fut_more,
            compensation_cutoff=CUTOFF,
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.future_valid_rows, 0)
        self.assertEqual(decision.latest_compensation_date, "2026-08-31")

    def test_on_or_before_cutoff_change_is_changed(self) -> None:
        hist = _frame(_hist())
        fut_empty_after = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "SEP"})
        )
        last = _baseline_state(hist, fut_empty_after)
        fut_new = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 8, 30), "Referencia": "NEW-AUG"}),
            _fut(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "SEP"}),
        )
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=_fp(),
            last=last,
            historical_df=hist,
            future_df=fut_new,
            compensation_cutoff=CUTOFF,
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertEqual(decision.future_valid_rows, 1)
        self.assertEqual(decision.latest_compensation_date, "2026-08-31")

    def test_historical_after_cutoff_failed(self) -> None:
        hist = _frame(
            _hist(**{FECHA_COMP_COL: date(2026, 9, 1), "Referencia": "BAD-HIST"})
        )
        fut = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 8, 31), "Referencia": "OK"})
        )
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=_fp(),
            last=None,
            historical_df=hist,
            future_df=fut,
            compensation_cutoff=CUTOFF,
        )
        self.assertEqual(decision.status, DECISION_FAILED)
        self.assertIn("histórico", decision.message.lower())

        with self.assertRaises(CompensationCutoffError):
            combine_fbl1n_sources(hist, fut, compensation_cutoff=CUTOFF)

    def test_combined_92056_no_cross_duplication(self) -> None:
        n = 92056
        data = {column: [None] * n for column in EXPECTED_COLUMNS}
        data[SOCIEDAD_COL] = ["CL44"] * n
        data[FECHA_COMP_COL] = [date(2026, 8, 31)] * n
        data["Referencia"] = [f"H{i}" for i in range(n)]
        hist = pd.DataFrame(data, columns=list(EXPECTED_COLUMNS))
        # Futuro: cruces + posteriores al corte (no deben alterar el cierre).
        fut = _frame(
            _blank_row(
                **{
                    SOCIEDAD_COL: "CL44",
                    FECHA_COMP_COL: date(2026, 8, 31),
                    "Referencia": "H0",
                }
            ),
            _fut(FECHA_COMP_COL=date(2026, 9, 1), Referencia="POST"),
            _fut(FECHA_COMP_COL=date(2026, 9, 4), Referencia="POST4"),
        )
        result = combine_fbl1n_sources(hist, fut, compensation_cutoff=CUTOFF)
        self.assertEqual(result.summary.status, STATUS_SUCCEEDED)
        self.assertEqual(result.summary.final_rows, 92056)
        self.assertEqual(result.summary.cross_matches_excluded, 1)
        self.assertEqual(result.summary.future_cutoff_excluded, 2)
        sem = semantic_fbl1n_fingerprint(fut, compensation_cutoff=CUTOFF)
        self.assertEqual(sem.latest_compensation_date, "2026-08-31")


class CutoffMailGuardTests(unittest.TestCase):
    def test_mail_agosto_and_powerbi_notice_without_send(self) -> None:
        with patch(
            "src.modules.actualizacion_automatica.mail.send_outlook_mail",
            side_effect=AssertionError("no send"),
        ):
            payload = compose_mail_payload(
                to="destinatario@example.test",
                sharepoint=FAKE_SP,
                powerbi="https://example.test/powerbi",
                period_label="Agosto-2026",
                future_enabled=False,
            )
        self.assertEqual(
            payload.subject,
            build_mail_subject("Agosto-2026", future_enabled=False),
        )
        self.assertEqual(
            payload.subject,
            "Detalle Pagos_Resumen en CLP y USD - Agosto 2026",
        )
        self.assertIn(POWERBI_UPDATE_NOTICE, payload.body)
        self.assertIn(FAKE_SP, payload.body)
        self.assertNotIn("Ver Dashboard Power BI", payload.html_body or "")
        self.assertIsNone(payload.powerbi_link)


if __name__ == "__main__":
    unittest.main()
