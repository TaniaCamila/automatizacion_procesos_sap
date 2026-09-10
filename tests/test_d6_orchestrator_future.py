"""D6: orquestador aislado en modo futuro (copias D1, state temporal)."""

from __future__ import annotations

import json
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config.config import FBL1N_FUTURE_ENABLED, ROOT_DIR, TEMP_DIR
from src.modules.fbl1n_fuentes.dry_run import (
    load_d6_state,
    run_future_orchestrator_dry,
    sha256_file,
    write_d6_json,
)
from src.modules.fbl1n_fuentes.module import EXPECTED_COLUMNS, FECHA_COMP_COL

D1_DIR = ROOT_DIR / "temp" / "auditoria_dos_fbl1n_20260827_20260827_173610"
D1_HIST = D1_DIR / "FBL1N_HISTORICO_COPIA.xlsx"
D1_FUT = D1_DIR / "FBL1N_FUTURO_COPIA.xlsx"
WORK_DIR = TEMP_DIR / "d6_orquestador_isolated"
PROD_STATE = ROOT_DIR / "state" / "last_fbl1n_state.json"
PROD_MAIL = ROOT_DIR / "state" / "last_mail_state.json"
PROD_PUB = ROOT_DIR / "state" / "last_publish_state.json"
FUTURE_SUBJECT = (
    "Detalle Pagos_Resumen en CLP y USD - Fecha de compensación 02/09/2026"
)
FUTURE_PHRASE = "Información actualizada hasta la fecha de compensación 02/09/2026."


def _mtime(path: Path) -> int | None:
    if not path.is_file():
        return None
    return int(path.stat().st_mtime_ns)


def _footer_only() -> pd.DataFrame:
    row = {column: None for column in EXPECTED_COLUMNS}
    row["Importe en moneda doc."] = 1
    row["Moneda del documento"] = "CLP"
    return pd.DataFrame([row], columns=list(EXPECTED_COLUMNS))


def _pad_copy(source: Path, dest: Path) -> None:
    dest.write_bytes(source.read_bytes())
    with zipfile.ZipFile(dest, "a") as handle:
        handle.writestr("_d6_meta_pad.txt", f"pad-{datetime.now().isoformat()}")


class D6OrchestratorIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prod = {
            "pipeline": _mtime(PROD_STATE),
            "mail": _mtime(PROD_MAIL),
            "publish": _mtime(PROD_PUB),
            "hist": _mtime(D1_HIST),
            "fut": _mtime(D1_FUT),
        }
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        cls.hist_df = pd.read_excel(D1_HIST)
        cls.fut_df = pd.read_excel(D1_FUT)
        cls.hist_sha = sha256_file(D1_HIST)
        cls.fut_sha = sha256_file(D1_FUT)

    def _assert_prod_untouched(self) -> None:
        self.assertEqual(_mtime(PROD_STATE), self.prod["pipeline"])
        self.assertEqual(_mtime(PROD_MAIL), self.prod["mail"])
        self.assertEqual(_mtime(PROD_PUB), self.prod["publish"])
        self.assertEqual(_mtime(D1_HIST), self.prod["hist"])
        self.assertEqual(_mtime(D1_FUT), self.prod["fut"])

    def test_00_static_review_dry_run_module(self) -> None:
        source = (
            ROOT_DIR / "src" / "modules" / "fbl1n_fuentes" / "dry_run.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from src.app", source)
        self.assertNotIn("import win32com", source)
        self.assertNotIn("win32com.client", source)
        self.assertNotIn("run_actualizacion(", source)
        self.assertNotIn("run_actualizacion_automatica", source)
        self.assertNotIn(".Display(", source)
        self.assertNotIn(".Send(", source)
        self.assertIn("d6_orquestador", source)

    def test_01_first_run_changed(self) -> None:
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=None,
            historical_df=self.hist_df,
            future_df=self.fut_df,
            mail_auto_send=False,
        )
        self.assertEqual(result.decision, "Changed")
        self.assertEqual(result.historical_rows, 91035)
        self.assertEqual(result.future_rows_received, 3204)
        self.assertEqual(result.future_invalid_excluded, 1)
        self.assertEqual(result.future_valid_rows, 3203)
        self.assertEqual(result.final_rows, 94238)
        self.assertEqual(result.latest_compensation_date, "2026-09-02")
        self.assertEqual(result.mail_subject, FUTURE_SUBJECT)
        self.assertEqual(result.mail_body_phrase, FUTURE_PHRASE)
        self.assertEqual(result.counters.pipeline, 1)
        self.assertEqual(result.counters.publish, 1)
        self.assertEqual(result.counters.mail_compose, 1)
        self.assertEqual(result.counters.outlook_display, 0)
        self.assertEqual(result.counters.outlook_send, 0)
        self.assertTrue((WORK_DIR / "pipeline_state.json").is_file())
        self._assert_prod_untouched()

    def test_02_second_run_unchanged(self) -> None:
        last = load_d6_state(WORK_DIR / "pipeline_state.json")
        self.assertIsNotNone(last)
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=last,
            historical_df=self.hist_df,
            future_df=self.fut_df,
        )
        self.assertEqual(result.decision, "Unchanged")
        self.assertEqual(result.counters.pipeline, 0)
        self.assertEqual(result.counters.publish, 0)
        self.assertEqual(result.counters.mail_compose, 0)
        self.assertEqual(result.counters.outlook_display, 0)
        self.assertEqual(result.counters.outlook_send, 0)
        self._assert_prod_untouched()

    def test_03_nodata(self) -> None:
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=None,
            historical_df=self.hist_df,
            future_df=_footer_only(),
        )
        self.assertEqual(result.decision, "NoData")
        self.assertEqual(result.counters.pipeline, 0)
        self.assertEqual(result.counters.publish, 0)
        self.assertEqual(result.counters.mail_compose, 0)
        self._assert_prod_untouched()

    def test_04_future_missing(self) -> None:
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=None,
            last=None,
            historical_df=self.hist_df,
        )
        self.assertEqual(result.decision, "Failed")
        self.assertEqual(result.counters.pipeline, 0)
        self.assertEqual(result.counters.mail_compose, 0)
        self._assert_prod_untouched()

    def test_05_historical_altered(self) -> None:
        last = {
            "schema_version": "2",
            "source_mode": "historical_plus_future",
            "historical_file_sha256": "sha-historico-distinto",
            "sha256": "sha-historico-distinto",
            "combined_source_sha256": "previo",
        }
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=last,
            historical_df=self.hist_df,
            future_df=self.fut_df,
        )
        self.assertEqual(result.decision, "HistoricalAnomaly")
        self.assertIn("migración", result.message.lower())
        self.assertEqual(result.counters.pipeline, 0)
        self.assertEqual(result.counters.mail_compose, 0)
        self._assert_prod_untouched()

    def test_06_publish_failed(self) -> None:
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR / "publish_fail",
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=None,
            historical_df=self.hist_df,
            future_df=self.fut_df,
            publish_ok=False,
        )
        self.assertEqual(result.decision, "Changed")
        self.assertEqual(result.counters.pipeline, 1)
        self.assertEqual(result.counters.publish, 1)
        self.assertEqual(result.counters.mail_compose, 0)
        self.assertIn("Failed", result.error)
        self.assertFalse((WORK_DIR / "publish_fail" / "pipeline_state.json").exists())
        self._assert_prod_untouched()

    def test_07_invalid_date_fail_closed(self) -> None:
        missing = run_future_orchestrator_dry(
            work_dir=WORK_DIR / "bad_date",
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=None,
            historical_df=self.hist_df,
            future_df=self.fut_df,
            latest_compensation_date=None,
        )
        invalid = run_future_orchestrator_dry(
            work_dir=WORK_DIR / "bad_date",
            historical_path=D1_HIST,
            future_path=D1_FUT,
            last=None,
            historical_df=self.hist_df,
            future_df=self.fut_df,
            latest_compensation_date="02/09/2026",
        )
        self.assertEqual(missing.decision, "Changed")
        self.assertEqual(missing.counters.mail_compose, 0)
        self.assertEqual(missing.counters.outlook_send, 0)
        self.assertIn("ausente", missing.error)
        self.assertEqual(invalid.counters.mail_compose, 0)
        self.assertIn("inválida", invalid.error)
        self._assert_prod_untouched()

    def test_08_same_content_different_physical_file(self) -> None:
        last = load_d6_state(WORK_DIR / "pipeline_state.json")
        padded = WORK_DIR / "FBL1N_FUTURO_PADDED.xlsx"
        _pad_copy(D1_FUT, padded)
        self.assertNotEqual(sha256_file(padded), self.fut_sha)
        padded_df = pd.read_excel(padded)
        result = run_future_orchestrator_dry(
            work_dir=WORK_DIR,
            historical_path=D1_HIST,
            future_path=padded,
            last=last,
            historical_df=self.hist_df,
            future_df=padded_df,
        )
        self.assertEqual(result.decision, "Unchanged")
        self.assertEqual(result.counters.pipeline, 0)
        self.assertEqual(result.counters.publish, 0)
        self.assertEqual(result.counters.mail_compose, 0)
        self._assert_prod_untouched()

    def test_09_default_flag_off_and_summary(self) -> None:
        self.assertFalse(FBL1N_FUTURE_ENABLED)
        summary = {
            "stage": "D6",
            "flag_process_only": True,
            "mail_auto_send": False,
            "outlook_display": 0,
            "outlook_send": 0,
            "work_dir": WORK_DIR.name,
            "scenarios": {
                "first_run": "Changed",
                "second_run": "Unchanged",
                "nodata": "NoData",
                "future_missing": "Failed",
                "historical_altered": "HistoricalAnomaly",
                "publish_failed": "Changed_no_mail",
                "invalid_date": "fail_closed",
                "padded_future": "Unchanged",
            },
        }
        write_d6_json(WORK_DIR / "d6_summary.json", summary)
        self._assert_prod_untouched()
        self.assertFalse(FBL1N_FUTURE_ENABLED)
