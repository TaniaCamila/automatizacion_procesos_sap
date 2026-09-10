"""Huella semántica, identidad combinada y detección D4 (datos ficticios)."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.config.config import FBL1N_FUTURE_ENABLED
from src.modules.actualizacion_automatica.module import is_same_fbl1n, save_state
from src.modules.fbl1n_fuentes.detection import (
    DECISION_CHANGED,
    DECISION_FAILED,
    DECISION_HISTORICAL_ANOMALY,
    DECISION_NODATA,
    DECISION_UNCHANGED,
    IDENTITY_VERSION_V2,
    MIGRATION_REQUIRED_MESSAGE,
    SOURCE_MODE_HISTORICAL,
    SOURCE_MODE_PLUS_FUTURE,
    STATE_SCHEMA_VERSION,
    build_combined_state_payload,
    plan_source_detection,
    publication_source_sha256,
)
from src.modules.fbl1n_fuentes.module import (
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    SEMANTIC_VERSION,
    SOCIEDAD_COL,
    combined_semantic_sha256,
    combined_source_sha256,
    semantic_fbl1n_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
PROD_STATE = ROOT / "state" / "last_fbl1n_state.json"
D1_DIR = ROOT / "temp" / "auditoria_dos_fbl1n_20260827_20260827_173610"
D1_HIST = D1_DIR / "FBL1N_HISTORICO_COPIA.xlsx"
D1_FUT = D1_DIR / "FBL1N_FUTURO_COPIA.xlsx"
D1_PADDED = D1_DIR / "d4_FBL1N_FUTURO_META.xlsx"
D1_SUMMARY = D1_DIR / "d4_semantic_summary.json"


def _blank_row(**overrides: object) -> dict[str, object]:
    row = {column: None for column in EXPECTED_COLUMNS}
    row.update(overrides)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(EXPECTED_COLUMNS))


def _hist(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL44",
        FECHA_COMP_COL: date(2026, 1, 15),
        "Referencia": "H1",
        "Importe en moneda doc.": 100,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _fut(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL45",
        FECHA_COMP_COL: date(2026, 9, 2),
        "Referencia": "F1",
        "Importe en moneda doc.": 200,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _fp(sha: str, size: int = 10) -> dict[str, object]:
    return {"sha256": sha, "size": size}


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_xlsx(path: Path, frame: pd.DataFrame) -> None:
    frame.to_excel(path, index=False, sheet_name="Sheet1")


def _pad_xlsx_metadata(source: Path, dest: Path) -> None:
    dest.write_bytes(source.read_bytes())
    with zipfile.ZipFile(dest, "a") as handle:
        handle.writestr("_d4_meta_pad.txt", f"pad-{datetime.now().isoformat()}")


class SemanticFingerprintTests(unittest.TestCase):
    def test_same_content_different_physical_file_same_semantic(self) -> None:
        frame = _frame(_fut(), _fut(Referencia="F2"))
        with tempfile.TemporaryDirectory() as raw:
            first = Path(raw) / "a.xlsx"
            second = Path(raw) / "b.xlsx"
            _write_xlsx(first, frame)
            _pad_xlsx_metadata(first, second)
            loaded_a = pd.read_excel(first)
            loaded_b = pd.read_excel(second)
            sem_a = semantic_fbl1n_fingerprint(loaded_a)
            sem_b = semantic_fbl1n_fingerprint(loaded_b)
            self.assertNotEqual(_sha_file(first), _sha_file(second))
            self.assertEqual(sem_a.sha256, sem_b.sha256)
            self.assertTrue(sem_a.sha256)
            self.assertEqual(sem_a.version, SEMANTIC_VERSION)

    def test_reordered_rows_same_semantic(self) -> None:
        row_a = _fut(Referencia="A")
        row_b = _fut(Referencia="B", **{SOCIEDAD_COL: "CLY8"})
        first = semantic_fbl1n_fingerprint(_frame(row_a, row_b))
        second = semantic_fbl1n_fingerprint(_frame(row_b, row_a))
        self.assertEqual(first.sha256, second.sha256)

    def test_multiplicity_preserved(self) -> None:
        single = semantic_fbl1n_fingerprint(_frame(_fut()))
        doubled = semantic_fbl1n_fingerprint(_frame(_fut(), _fut()))
        self.assertNotEqual(single.sha256, doubled.sha256)
        self.assertEqual(doubled.valid_rows, 2)

    def test_new_row_changes_semantic(self) -> None:
        base = semantic_fbl1n_fingerprint(_frame(_fut()))
        added = semantic_fbl1n_fingerprint(_frame(_fut(), _fut(Referencia="F2")))
        self.assertNotEqual(base.sha256, added.sha256)

    def test_deleted_row_changes_semantic(self) -> None:
        full = semantic_fbl1n_fingerprint(_frame(_fut(), _fut(Referencia="F2")))
        reduced = semantic_fbl1n_fingerprint(_frame(_fut()))
        self.assertNotEqual(full.sha256, reduced.sha256)

    def test_corrected_row_changes_semantic(self) -> None:
        original = semantic_fbl1n_fingerprint(_frame(_fut(Referencia="F1")))
        corrected = semantic_fbl1n_fingerprint(
            _frame(_fut(Referencia="F1-corr"))
        )
        self.assertNotEqual(original.sha256, corrected.sha256)

    def test_sap_footer_excluded(self) -> None:
        footer = _blank_row(
            **{
                "Importe en moneda doc.": 999,
                "Moneda del documento": "CLP",
            }
        )
        with_footer = semantic_fbl1n_fingerprint(_frame(_fut(), footer))
        without = semantic_fbl1n_fingerprint(_frame(_fut()))
        self.assertEqual(with_footer.sha256, without.sha256)
        self.assertEqual(with_footer.invalid_rows, 1)
        self.assertEqual(with_footer.valid_rows, 1)

    def test_latest_compensation_date(self) -> None:
        frame = _frame(
            _fut(**{FECHA_COMP_COL: date(2026, 9, 1)}),
            _fut(Referencia="F2", **{FECHA_COMP_COL: date(2026, 9, 2)}),
            _blank_row(**{"Importe en moneda doc.": 1}),
        )
        semantic = semantic_fbl1n_fingerprint(frame)
        self.assertEqual(semantic.latest_compensation_date, "2026-09-02")
        self.assertEqual(list(semantic.columns), list(EXPECTED_COLUMNS))


class CombinedIdentityAndDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hist_fp = _fp("hist-aaa", 100)
        self.hist_df = _frame(_hist())
        self.future = _frame(_fut())
        self.semantic = semantic_fbl1n_fingerprint(self.future)
        self.hist_semantic = semantic_fbl1n_fingerprint(self.hist_df)
        self.combined = combined_source_sha256(
            "hist-aaa",
            self.semantic.sha256,
        )
        self.combined_semantic = combined_semantic_sha256(
            self.hist_semantic.sha256,
            self.semantic.sha256,
        )

    def _v2_last(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "identity_version": IDENTITY_VERSION_V2,
            "historical_file_sha256": "hist-aaa",
            "historical_semantic_sha256": self.hist_semantic.sha256,
            "sha256": "hist-aaa",
            "size": 100,
            "future_semantic_sha256": self.semantic.sha256,
            "combined_source_sha256": self.combined,
            "combined_semantic_sha256": self.combined_semantic,
            "source_fbl1n_sha256": self.combined,
        }
        payload.update(overrides)
        return payload

    def test_future_without_valid_rows_is_nodata(self) -> None:
        footer = _frame(_blank_row(**{"Importe en moneda doc.": 1}))
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=None,
            historical_df=self.hist_df,
            future_df=footer,
            future_file_sha256="phys-fut",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_NODATA)
        self.assertEqual(decision.future_valid_rows, 0)
        self.assertEqual(decision.future_invalid_rows, 1)

    def test_missing_future_is_failed(self) -> None:
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=None,
            future_available=False,
            future_error="El archivo FBL1N futuro no está disponible: FBL1N_FUTURO.xlsx.",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_FAILED)
        self.assertIn("FBL1N_FUTURO.xlsx", decision.message)
        self.assertNotIn("Users", decision.message)

    def test_historical_changed_is_anomaly(self) -> None:
        last = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "historical_file_sha256": "hist-old",
            "sha256": "hist-old",
            "combined_source_sha256": "prev-combined",
        }
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=last,
            historical_df=self.hist_df,
            future_df=self.future,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_HISTORICAL_ANOMALY)
        self.assertIn("migración", decision.message.lower())
        self.assertEqual(decision.message, MIGRATION_REQUIRED_MESSAGE)

    def test_legacy_matching_migrates_as_changed(self) -> None:
        last = {"sha256": "hist-aaa", "size": 100, "path": "FBL1N.xlsx"}
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=last,
            historical_df=self.hist_df,
            future_df=self.future,
            future_file_sha256="phys-fut",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertTrue(decision.migrate_from_legacy)
        self.assertEqual(decision.combined_source_sha256, self.combined)

    def test_legacy_mismatch_aborts(self) -> None:
        last = {"sha256": "hist-other", "size": 100}
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=last,
            historical_df=self.hist_df,
            future_df=self.future,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_HISTORICAL_ANOMALY)

    def test_first_run_without_state_is_changed(self) -> None:
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=None,
            historical_df=self.hist_df,
            future_df=self.future,
            future_file_sha256="phys-fut",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertTrue(decision.first_run)
        self.assertEqual(decision.source_fbl1n_sha256, self.combined)

    def test_flag_off_matches_previous_hash_and_size(self) -> None:
        last = {"sha256": "hist-aaa", "size": 100}
        footer = _frame(_blank_row(**{"Importe en moneda doc.": 1}))
        decision = plan_source_detection(
            future_enabled=False,
            historical_fp=self.hist_fp,
            last=last,
            future_df=footer,
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.source_mode, SOURCE_MODE_HISTORICAL)
        self.assertEqual(decision.source_fbl1n_sha256, "hist-aaa")
        self.assertTrue(is_same_fbl1n(self.hist_fp, last))

    def test_flag_on_same_combined_is_unchanged(self) -> None:
        last = self._v2_last()
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=_fp("hist-repack", 111),
            last=last,
            historical_df=self.hist_df,
            future_df=self.future,
            future_file_sha256="phys-other",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.source_fbl1n_sha256, self.combined)
        self.assertEqual(decision.combined_source_sha256, self.combined)
        self.assertEqual(decision.combined_semantic_sha256, self.combined_semantic)

    def test_flag_on_new_combined_is_changed(self) -> None:
        last = self._v2_last()
        new_future = _frame(_fut(Referencia="F-new"))
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=last,
            historical_df=self.hist_df,
            future_df=new_future,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertNotEqual(
            decision.combined_semantic_sha256, self.combined_semantic
        )

    def test_publication_alias_uses_combined_when_future_enabled(self) -> None:
        alias = publication_source_sha256(
            future_enabled=True,
            historical_sha256="hist-aaa",
            combined_sha256=self.combined,
        )
        self.assertEqual(alias, self.combined)
        self.assertNotEqual(alias, "hist-aaa")
        off = publication_source_sha256(
            future_enabled=False,
            historical_sha256="hist-aaa",
            combined_sha256=self.combined,
        )
        self.assertEqual(off, "hist-aaa")

    def test_temp_state_not_productive(self) -> None:
        prod_mtime = (
            PROD_STATE.stat().st_mtime_ns if PROD_STATE.is_file() else None
        )
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=None,
            historical_df=self.hist_df,
            future_df=self.future,
            future_file_sha256="phys-fut",
            compensation_cutoff=date(2026, 12, 31),
        )
        payload = build_combined_state_payload(
            historical_fp=self.hist_fp,
            decision=decision,
            started_at="2026-08-28T00:00:00",
            last_success_at="2026-08-28T00:00:01",
            fbl1n_rows=2,
            matrix_rows=2,
            months=["2026-09"],
            matriz="MATRIZ.xlsx",
            dinamicas="DIN.xlsx",
            actual="ACTUAL.xlsx",
            log="run.log",
        )
        self.assertEqual(payload["schema_version"], STATE_SCHEMA_VERSION)
        self.assertEqual(payload["source_mode"], SOURCE_MODE_PLUS_FUTURE)
        self.assertEqual(payload["identity_version"], IDENTITY_VERSION_V2)
        self.assertEqual(payload["source_fbl1n_sha256"], payload["combined_source_sha256"])
        self.assertEqual(payload["sha256"], "hist-aaa")
        self.assertEqual(payload["source_fbl1n_sha256"], self.combined)
        self.assertEqual(payload["combined_semantic_sha256"], self.combined_semantic)
        self.assertEqual(payload["historical_semantic_sha256"], self.hist_semantic.sha256)
        with tempfile.TemporaryDirectory() as raw:
            temp_state = Path(raw) / "last_fbl1n_state.json"
            save_state(payload, temp_state)
            self.assertTrue(temp_state.is_file())
            loaded = json.loads(temp_state.read_text(encoding="utf-8"))
            self.assertEqual(loaded["combined_source_sha256"], self.combined)
        if prod_mtime is not None:
            self.assertEqual(PROD_STATE.stat().st_mtime_ns, prod_mtime)

    def test_logs_only_counts_not_rows(self) -> None:
        logger = logging.getLogger("d4_detection_test")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        buffer: list[str] = []

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                buffer.append(record.getMessage())

        logger.addHandler(_Handler())
        plan_source_detection(
            future_enabled=True,
            historical_fp=self.hist_fp,
            last=None,
            historical_df=self.hist_df,
            future_df=_frame(_fut(Name="Proveedor Sensible SA")),
            logger=logger,
            compensation_cutoff=date(2026, 12, 31),
        )
        text = "\n".join(buffer)
        self.assertIn("validas=1", text)
        self.assertIn("Decisión=Changed", text)
        self.assertNotIn("Proveedor Sensible", text)
        self.assertNotIn("CL45", text)

    def test_default_flag_off(self) -> None:
        self.assertFalse(FBL1N_FUTURE_ENABLED)


class D1SemanticValidationTests(unittest.TestCase):
    def test_d1_copies_semantic_and_unchanged_on_padded_future(self) -> None:
        self.assertTrue(D1_HIST.is_file())
        self.assertTrue(D1_FUT.is_file())
        prod_mtime = (
            PROD_STATE.stat().st_mtime_ns if PROD_STATE.is_file() else None
        )
        hist_stat = D1_HIST.stat()
        fut_stat = D1_FUT.stat()

        historical_sha = _sha_file(D1_HIST)
        future_physical = _sha_file(D1_FUT)
        historical_df = pd.read_excel(D1_HIST)
        future_df = pd.read_excel(D1_FUT)
        semantic = semantic_fbl1n_fingerprint(future_df)
        hist_semantic = semantic_fbl1n_fingerprint(historical_df)
        combined = combined_source_sha256(historical_sha, semantic.sha256)
        combined_semantic = combined_semantic_sha256(
            hist_semantic.sha256, semantic.sha256
        )

        self.assertEqual(semantic.valid_rows, 3203)
        self.assertEqual(semantic.invalid_rows, 1)
        self.assertEqual(semantic.latest_compensation_date, "2026-09-02")
        self.assertEqual(len(semantic.columns), 21)

        _pad_xlsx_metadata(D1_FUT, D1_PADDED)
        padded_physical = _sha_file(D1_PADDED)
        padded_df = pd.read_excel(D1_PADDED)
        padded_semantic = semantic_fbl1n_fingerprint(padded_df)
        self.assertNotEqual(future_physical, padded_physical)
        self.assertEqual(semantic.sha256, padded_semantic.sha256)
        padded_combined = combined_source_sha256(
            historical_sha,
            padded_semantic.sha256,
        )
        self.assertEqual(combined, padded_combined)

        last = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "identity_version": IDENTITY_VERSION_V2,
            "historical_file_sha256": historical_sha,
            "historical_semantic_sha256": hist_semantic.sha256,
            "sha256": historical_sha,
            "size": int(hist_stat.st_size),
            "combined_source_sha256": combined,
            "combined_semantic_sha256": combined_semantic,
        }
        hist_fp = _fp(historical_sha, int(hist_stat.st_size))
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=hist_fp,
            last=last,
            historical_df=historical_df,
            future_df=padded_df,
            future_file_sha256=padded_physical,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.source_fbl1n_sha256, combined)

        first = plan_source_detection(
            future_enabled=True,
            historical_fp=hist_fp,
            last=None,
            historical_df=historical_df,
            future_df=future_df,
            future_file_sha256=future_physical,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(first.status, DECISION_CHANGED)

        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "stage": "D4",
            "historical_file_sha256": historical_sha,
            "future_file_sha256": future_physical,
            "future_padded_file_sha256": padded_physical,
            "future_semantic_sha256": semantic.sha256,
            "padded_semantic_sha256": padded_semantic.sha256,
            "combined_source_sha256": combined,
            "future_valid_rows": semantic.valid_rows,
            "future_invalid_rows": semantic.invalid_rows,
            "latest_compensation_date": semantic.latest_compensation_date,
            "columns": len(semantic.columns),
            "physical_sha_differ": future_physical != padded_physical,
            "semantic_sha_equal": semantic.sha256 == padded_semantic.sha256,
            "combined_equal": combined == padded_combined,
            "padded_decision": decision.status,
            "first_run_decision": first.status,
            "source_fbl1n_sha256_alias": decision.source_fbl1n_sha256,
            "match_expected": (
                semantic.valid_rows == 3203
                and semantic.invalid_rows == 1
                and semantic.latest_compensation_date == "2026-09-02"
                and decision.status == DECISION_UNCHANGED
            ),
        }
        D1_SUMMARY.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.assertEqual(int(D1_HIST.stat().st_mtime_ns), int(hist_stat.st_mtime_ns))
        self.assertEqual(int(D1_FUT.stat().st_mtime_ns), int(fut_stat.st_mtime_ns))
        if prod_mtime is not None:
            self.assertEqual(PROD_STATE.stat().st_mtime_ns, prod_mtime)
