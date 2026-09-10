"""Integración controlada FBL1N futuro (flag default-off, datos ficticios)."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.config.config import (
    FBL1N_FUTURE_ENABLED,
    FBL1N_FUTURE_FILE,
    FBL1N_FUTURE_PATH,
    INPUT_DIR,
)
from src.modules.fbl1n_fuentes.module import (
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    SOCIEDAD_COL,
    FutureFbl1nNoDataError,
    FutureFbl1nUnavailableError,
)
from src.modules.margen.module import InformeMargenModule
from src.processors.fbl1n_processor import FBL1NProcessor

ROOT = Path(__file__).resolve().parents[1]
D1_DIR = ROOT / "temp" / "auditoria_dos_fbl1n_20260827_20260827_173610"
D1_HIST = D1_DIR / "FBL1N_HISTORICO_COPIA.xlsx"
D1_FUT = D1_DIR / "FBL1N_FUTURO_COPIA.xlsx"
D1_SUMMARY = D1_DIR / "d3_combine_summary.json"


def _blank_row(**overrides: object) -> dict[str, object]:
    row = {column: None for column in EXPECTED_COLUMNS}
    row.update(overrides)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(EXPECTED_COLUMNS))


def _valid_hist(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL44",
        FECHA_COMP_COL: date(2026, 1, 15),
        "Referencia": "H1",
        "Importe en moneda doc.": 100,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _valid_fut(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL45",
        FECHA_COMP_COL: date(2026, 9, 2),
        "Referencia": "F1",
        "Importe en moneda doc.": 200,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _write_xlsx(path: Path, frame: pd.DataFrame) -> None:
    frame.to_excel(path, index=False, sheet_name="Sheet1")


class FutureConfigTests(unittest.TestCase):
    def test_future_enabled_default_off(self) -> None:
        self.assertFalse(FBL1N_FUTURE_ENABLED)

    def test_future_path_uses_input_dir_filename(self) -> None:
        self.assertEqual(FBL1N_FUTURE_FILE, "FBL1N_FUTURO.xlsx")
        self.assertEqual(FBL1N_FUTURE_PATH.name, "FBL1N_FUTURO.xlsx")
        self.assertEqual(FBL1N_FUTURE_PATH.parent, INPUT_DIR)

    def test_future_path_not_hardcoded_user(self) -> None:
        source = (ROOT / "src" / "config" / "config.py").read_text(encoding="utf-8")
        future_block = []
        capturing = False
        for line in source.splitlines():
            if "FBL1N_FUTURE_" in line:
                capturing = True
            if capturing:
                future_block.append(line)
                if line.startswith("SOCIEDADES_PATH"):
                    break
        text = "\n".join(future_block)
        self.assertIn("FBL1N_FUTURE_ENABLED", text)
        self.assertIn("FBL1N_COMPENSATION_CUTOFF", source)
        self.assertNotIn("Users", text)
        self.assertNotIn("usuario_ejemplo", text)
        self.assertNotIn("C:\\", text)


class FutureIntegrationUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = InformeMargenModule()
        self.module.exporter.export = MagicMock()
        self.received: list[pd.DataFrame] = []

        def _capture(df: pd.DataFrame) -> pd.DataFrame:
            self.received.append(df)
            return df

        self.module.processor.process = _capture

    def test_flag_off_does_not_read_future(self) -> None:
        hist = _frame(_valid_hist())
        calls: list[object] = []

        def fake_load(path: Path | None = None) -> pd.DataFrame:
            calls.append(path)
            return hist

        self.module.loader.load_fbl1n = fake_load  # type: ignore[method-assign]
        with patch(
            "src.modules.fbl1n_fuentes.module.combine_fbl1n_sources"
        ) as mocked_combine:
            self.module.process_fbl1n()
        mocked_combine.assert_not_called()
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0])
        self.assertIsNone(self.module.last_combine_summary)

    def test_flag_off_matches_previous_processor_result(self) -> None:
        hist = _frame(_valid_hist())
        self.module.loader.load_fbl1n = (  # type: ignore[method-assign]
            lambda path=None: hist.copy()
        )
        self.module.processor.process = FBL1NProcessor().process  # type: ignore[method-assign]
        expected = FBL1NProcessor().process(hist.copy())
        result = self.module.process_fbl1n()
        pd.testing.assert_frame_equal(result, expected)
        self.module.exporter.export.assert_not_called()

    def test_flag_on_loads_both_sources_and_combines_before_processor(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(_valid_fut())
        order: list[str] = []
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)

            real_combine = __import__(
                "src.modules.fbl1n_fuentes.module",
                fromlist=["combine_fbl1n_sources"],
            ).combine_fbl1n_sources

            def wrapped(
                historical_df: pd.DataFrame,
                future_df: pd.DataFrame,
                **kwargs: object,
            ):
                order.append("combine")
                return real_combine(historical_df, future_df, **kwargs)

            original_process = self.module.processor.process

            def process_and_mark(df: pd.DataFrame) -> pd.DataFrame:
                order.append("process")
                return original_process(df)

            self.module.processor.process = process_and_mark  # type: ignore[method-assign]
            with patch(
                "src.modules.fbl1n_fuentes.module.combine_fbl1n_sources",
                side_effect=wrapped,
            ):
                result = self.module.process_fbl1n(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        self.assertEqual(order, ["combine", "process"])
        self.assertEqual(len(result), 2)
        self.assertEqual(self.module.last_combine_summary.final_rows, 2)
        self.assertEqual(self.module.last_combine_summary.status, "Succeeded")

    def test_missing_future_file_fail_closed(self) -> None:
        hist = _frame(_valid_hist())
        self.module.loader.load_fbl1n = (  # type: ignore[method-assign]
            lambda path=None: hist
        )
        with self.assertRaises(FutureFbl1nUnavailableError) as ctx:
            self.module.process_fbl1n(
                future_enabled=True,
                future_path=Path("no_existe_FBL1N_FUTURO.xlsx"),
                compensation_cutoff=date(2026, 12, 31),
            )
        self.assertIn("no está disponible", str(ctx.exception))
        self.assertNotIn("Users", str(ctx.exception))
        self.assertEqual(self.received, [])

    def test_locked_future_fail_closed(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(_valid_fut())
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            self.module.loader.is_locked = lambda path: Path(path) == fut_path  # type: ignore[method-assign]
            with self.assertRaises(FutureFbl1nUnavailableError) as ctx:
                self.module.process_fbl1n(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        self.assertIn("bloqueado", str(ctx.exception))
        self.assertEqual(self.received, [])

    def test_unreadable_future_fail_closed(self) -> None:
        hist = _frame(_valid_hist())
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            fut_path.write_text("esto no es un excel", encoding="utf-8")
            with self.assertRaises(FutureFbl1nUnavailableError) as ctx:
                self.module.process_fbl1n(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        self.assertIn("no es legible", str(ctx.exception))
        self.assertEqual(self.received, [])

    def test_incompatible_columns_fail_closed(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(_valid_fut())
        fut = fut.copy()
        fut["Extra"] = "x"
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            with self.assertRaises(FutureFbl1nUnavailableError) as ctx:
                self.module.process_fbl1n(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        self.assertIn("incompatible", str(ctx.exception).lower())
        self.assertEqual(self.received, [])

    def test_nodata_does_not_process_historical_only(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(
            _blank_row(
                **{
                    "Importe en moneda doc.": 999,
                    "Moneda del documento": "CLP",
                }
            )
        )
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            with self.assertRaises(FutureFbl1nNoDataError) as ctx:
                self.module.process_fbl1n(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        self.assertIn("NoData", str(ctx.exception))
        self.assertEqual(self.received, [])
        self.assertEqual(self.module.last_combine_summary.status, "NoData")
        self.assertEqual(self.module.last_combine_summary.historical_rows, 1)
        self.assertEqual(self.module.last_combine_summary.future_invalid_excluded, 1)

    def test_does_not_write_excel(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(_valid_fut())
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            before = {p.name for p in Path(raw).iterdir()}
            self.module.process_fbl1n(
                historical_path=hist_path,
                future_enabled=True,
                future_path=fut_path,
                compensation_cutoff=date(2026, 12, 31),
            )
            after = {p.name for p in Path(raw).iterdir()}
        self.assertEqual(before, after)
        self.module.exporter.export.assert_not_called()

    def test_input_dataframes_not_mutated(self) -> None:
        hist = _frame(_valid_hist())
        fut = _frame(_valid_fut())
        hist_before = hist.copy(deep=True)
        fut_before = fut.copy(deep=True)
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            loaded_hist = pd.read_excel(hist_path)
            loaded_fut = pd.read_excel(fut_path)
            hist_disk = loaded_hist.copy(deep=True)
            fut_disk = loaded_fut.copy(deep=True)
            self.module.prepare_fbl1n_dataframe(
                historical_path=hist_path,
                future_enabled=True,
                future_path=fut_path,
                compensation_cutoff=date(2026, 12, 31),
            )
            pd.testing.assert_frame_equal(pd.read_excel(hist_path), hist_disk)
            pd.testing.assert_frame_equal(pd.read_excel(fut_path), fut_disk)
        pd.testing.assert_frame_equal(hist, hist_before)
        pd.testing.assert_frame_equal(fut, fut_before)

    def test_logs_only_counts(self) -> None:
        hist = _frame(_valid_hist(Name="Proveedor Sensible SA"))
        fut = _frame(_valid_fut())
        with tempfile.TemporaryDirectory() as raw:
            hist_path = Path(raw) / "FBL1N.xlsx"
            fut_path = Path(raw) / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist_path, hist)
            _write_xlsx(fut_path, fut)
            with self.assertLogs("src.modules.margen.module", level="INFO") as cm:
                self.module.prepare_fbl1n_dataframe(
                    historical_path=hist_path,
                    future_enabled=True,
                    future_path=fut_path,
                    compensation_cutoff=date(2026, 12, 31),
                )
        combined_lines = [
            line for line in cm.output if "FBL1N combinado:" in line
        ]
        self.assertEqual(len(combined_lines), 1)
        line = combined_lines[0]
        self.assertIn("historico=1", line)
        self.assertIn("futuro_recibido=1", line)
        self.assertIn("final=2", line)
        self.assertNotIn("Proveedor Sensible", line)
        self.assertNotIn("CL44", line)
        self.assertNotIn("CL45", line)

    def test_existing_process_fbl1n_call_without_kwargs_still_works(self) -> None:
        hist = _frame(_valid_hist())
        self.module.loader.load_fbl1n = (  # type: ignore[method-assign]
            lambda path=None: hist.copy()
        )
        result = self.module.process_fbl1n()
        self.assertEqual(len(result), 1)
        self.assertIsNone(self.module.last_combine_summary)


class D1IsolatedIntegrationTests(unittest.TestCase):
    def test_d1_copies_processor_receives_94238_and_writes_summary(self) -> None:
        self.assertTrue(D1_HIST.is_file(), "falta copia D1 histórica")
        self.assertTrue(D1_FUT.is_file(), "falta copia D1 futura")
        hist_stat = D1_HIST.stat()
        fut_stat = D1_FUT.stat()

        module = InformeMargenModule()
        module.exporter.export = MagicMock()
        received: dict[str, int] = {}

        def capture(df: pd.DataFrame) -> pd.DataFrame:
            received["rows"] = len(df)
            received["columns"] = len(df.columns)
            return df

        module.processor.process = capture  # type: ignore[method-assign]
        module.process_fbl1n(
            historical_path=D1_HIST,
            future_enabled=True,
            future_path=D1_FUT,
            compensation_cutoff=date(2026, 12, 31),
        )
        summary = module.last_combine_summary
        self.assertIsNotNone(summary)
        self.assertEqual(summary.status, "Succeeded")
        self.assertEqual(summary.historical_rows, 91035)
        self.assertEqual(summary.future_rows_received, 3204)
        self.assertEqual(summary.future_invalid_excluded, 1)
        self.assertEqual(summary.cross_matches_excluded, 0)
        self.assertEqual(summary.final_rows, 94238)
        self.assertEqual(summary.columns, 21)
        self.assertEqual(received["rows"], 94238)
        self.assertEqual(received["columns"], 21)
        module.exporter.export.assert_not_called()

        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "stage": "D3",
            "status": summary.status,
            "historical_rows": summary.historical_rows,
            "future_rows_received": summary.future_rows_received,
            "future_invalid_excluded": summary.future_invalid_excluded,
            "cross_matches_excluded": summary.cross_matches_excluded,
            "final_rows": summary.final_rows,
            "columns": summary.columns,
            "processor_received_rows": received["rows"],
            "excel_written": False,
            "expected": {
                "historical_rows": 91035,
                "future_rows_received": 3204,
                "future_invalid_excluded": 1,
                "cross_matches_excluded": 0,
                "final_rows": 94238,
                "columns": 21,
            },
            "match_expected": True,
            "historical_copy": D1_HIST.name,
            "future_copy": D1_FUT.name,
        }
        D1_SUMMARY.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.assertEqual(D1_HIST.stat().st_size, hist_stat.st_size)
        self.assertEqual(D1_FUT.stat().st_size, fut_stat.st_size)
        self.assertEqual(int(D1_HIST.stat().st_mtime_ns), int(hist_stat.st_mtime_ns))
        self.assertEqual(int(D1_FUT.stat().st_mtime_ns), int(fut_stat.st_mtime_ns))
