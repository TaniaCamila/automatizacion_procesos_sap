"""Pruebas unitarias del combinador FBL1N (datos ficticios)."""

from __future__ import annotations

import unittest
from datetime import date, datetime

import pandas as pd

from src.modules.fbl1n_fuentes.module import (
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    SOCIEDAD_COL,
    STATUS_NODATA,
    STATUS_SUCCEEDED,
    CombineError,
    combine_fbl1n_sources,
    fingerprint_frame,
    fingerprint_row,
)


def _blank_row(**overrides: object) -> dict[str, object]:
    row = {column: None for column in EXPECTED_COLUMNS}
    row.update(overrides)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(EXPECTED_COLUMNS))


class CombineFbl1nSourcesTests(unittest.TestCase):
    def test_compatible_columns_succeed(self) -> None:
        historical = _frame(
            _blank_row(
                **{
                    SOCIEDAD_COL: "CL44",
                    FECHA_COMP_COL: date(2026, 1, 15),
                    "Referencia": "H1",
                }
            )
        )
        future = _frame(
            _blank_row(
                **{
                    SOCIEDAD_COL: "CL45",
                    FECHA_COMP_COL: date(2026, 9, 2),
                    "Referencia": "F1",
                }
            )
        )
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.status, STATUS_SUCCEEDED)
        self.assertEqual(result.summary.final_rows, 2)
        self.assertEqual(list(result.combined.columns), list(EXPECTED_COLUMNS))

    def test_incompatible_columns_raise(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = historical.copy()
        future = future.rename(columns={SOCIEDAD_COL: "Soc"})
        with self.assertRaises(CombineError):
            combine_fbl1n_sources(historical, future)

    def test_extra_columns_raise(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = historical.copy()
        future["Extra"] = 1
        with self.assertRaises(CombineError) as ctx:
            combine_fbl1n_sources(historical, future)
        message = str(ctx.exception).lower()
        self.assertTrue(
            "adicionales" in message or "21 columnas" in message,
            msg=message,
        )

    def test_column_order_incompatible_raise(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = historical[list(reversed(list(EXPECTED_COLUMNS)))]
        with self.assertRaises(CombineError) as ctx:
            combine_fbl1n_sources(historical, future)
        self.assertIn("orden", str(ctx.exception).lower())

    def test_historical_empty_raises(self) -> None:
        historical = pd.DataFrame(columns=list(EXPECTED_COLUMNS))
        future = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-09-02"}))
        with self.assertRaises(CombineError) as ctx:
            combine_fbl1n_sources(historical, future)
        self.assertIn("vacío", str(ctx.exception).lower())

    def test_future_none_raises(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        with self.assertRaises(CombineError) as ctx:
            combine_fbl1n_sources(historical, None)  # type: ignore[arg-type]
        self.assertIn("recibido", str(ctx.exception).lower())

    def test_historical_intact(self) -> None:
        historical = _frame(
            _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "H1"}),
            _blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-01-02", "Referencia": "H2"}),
        )
        future = _frame(
            _blank_row(**{SOCIEDAD_COL: "CLYD", FECHA_COMP_COL: "2026-09-02", "Referencia": "F1"}),
        )
        result = combine_fbl1n_sources(historical, future)
        restored = result.combined.iloc[:2]
        pd.testing.assert_frame_equal(
            restored.reset_index(drop=True),
            historical.reset_index(drop=True),
            check_dtype=False,
        )

    def test_internal_historical_duplicates_preserved(self) -> None:
        row = _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "DUP"})
        historical = _frame(row, dict(row))
        future = _frame(
            _blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-09-02", "Referencia": "F1"}),
        )
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.historical_rows, 2)
        self.assertEqual(len(result.combined.iloc[:2]), 2)
        self.assertEqual(result.summary.final_rows, 3)

    def test_internal_future_duplicates_preserved(self) -> None:
        historical = _frame(
            _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "H1"}),
        )
        row = _blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-09-02", "Referencia": "F-DUP"})
        future = _frame(row, dict(row))
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.future_rows_received, 2)
        self.assertEqual(result.summary.cross_matches_excluded, 0)
        self.assertEqual(result.summary.final_rows, 3)

    def test_cross_match_excluded_historical_precedence(self) -> None:
        shared = _blank_row(
            **{
                SOCIEDAD_COL: "CL44",
                FECHA_COMP_COL: date(2026, 8, 1),
                "Referencia": "SAME",
                "Importe en moneda doc.": 100,
            }
        )
        historical = _frame(shared, _blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-01-02", "Name": "H"}))
        future = _frame(
            dict(shared),
            _blank_row(**{SOCIEDAD_COL: "CLYD", FECHA_COMP_COL: "2026-09-02", "Referencia": "NEW"}),
        )
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.cross_matches_excluded, 1)
        self.assertEqual(result.summary.final_rows, 3)
        self.assertTrue(pd.isna(result.combined.iloc[0]["Name"]))
        self.assertNotIn("NEW", list(result.combined.iloc[:2]["Referencia"]))
        self.assertEqual(result.combined.iloc[-1]["Referencia"], "NEW")

    def test_future_without_sociedad_excluded(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = _frame(_blank_row(**{FECHA_COMP_COL: "2026-09-02", "Referencia": "NO-SOC"}))
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.future_invalid_excluded, 1)
        self.assertEqual(result.summary.final_rows, 1)
        self.assertEqual(result.summary.status, STATUS_NODATA)

    def test_future_without_fecha_excluded(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = _frame(_blank_row(**{SOCIEDAD_COL: "CL45", "Referencia": "NO-FECHA"}))
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.future_invalid_excluded, 1)
        self.assertEqual(result.summary.status, STATUS_NODATA)

    def test_sap_footer_only_amounts_excluded(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = _frame(
            _blank_row(
                **{
                    "Importe en moneda doc.": 999,
                    "Moneda del documento": "CLP",
                    "Importe valorado ML2": 999,
                    "Mon.local 2": "CLP",
                    "Importe en moneda local": 999,
                    "Moneda local": "CLP",
                }
            )
        )
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.future_invalid_excluded, 1)
        self.assertEqual(result.summary.final_rows, 1)
        self.assertEqual(result.summary.status, STATUS_NODATA)

    def test_input_dataframes_not_mutated(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "H"}))
        future = _frame(_blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-09-02", "Referencia": "F"}))
        hist_before = historical.copy()
        fut_before = future.copy()
        combine_fbl1n_sources(historical, future)
        pd.testing.assert_frame_equal(historical, hist_before)
        pd.testing.assert_frame_equal(future, fut_before)

    def test_column_order_preserved(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = _frame(_blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-09-02"}))
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(list(result.combined.columns), list(EXPECTED_COLUMNS))

    def test_null_normalization_equivalent(self) -> None:
        columns = list(EXPECTED_COLUMNS)
        left = fingerprint_row(columns, tuple(None for _ in columns))
        right = fingerprint_row(columns, tuple(float("nan") for _ in columns))
        empty = fingerprint_row(columns, tuple("" for _ in columns))
        self.assertEqual(left, right)
        self.assertEqual(left, empty)

    def test_date_normalization_iso(self) -> None:
        columns = list(EXPECTED_COLUMNS)
        idx = columns.index(FECHA_COMP_COL)
        a = [None] * 21
        b = [None] * 21
        c = [None] * 21
        a[idx] = date(2026, 9, 2)
        b[idx] = datetime(2026, 9, 2, 13, 45)
        c[idx] = "02.09.2026"
        self.assertEqual(fingerprint_row(columns, tuple(a)), fingerprint_row(columns, tuple(b)))
        self.assertEqual(fingerprint_row(columns, tuple(a)), fingerprint_row(columns, tuple(c)))

    def test_numeric_normalization_regional(self) -> None:
        columns = list(EXPECTED_COLUMNS)
        idx = columns.index("Importe en moneda doc.")
        a = [None] * 21
        b = [None] * 21
        c = [None] * 21
        a[idx] = 1000.5
        b[idx] = "1.000,50"
        c[idx] = "1000.5"
        self.assertEqual(fingerprint_row(columns, tuple(a)), fingerprint_row(columns, tuple(b)))
        self.assertEqual(fingerprint_row(columns, tuple(a)), fingerprint_row(columns, tuple(c)))

    def test_amounts_are_not_fingerprinted_as_dates(self) -> None:
        columns = list(EXPECTED_COLUMNS)
        amount_idx = columns.index("Importe en moneda doc.")
        date_idx = columns.index(FECHA_COMP_COL)
        as_amount = [None] * 21
        as_date = [None] * 21
        as_amount[amount_idx] = datetime(2026, 9, 2)
        as_date[date_idx] = datetime(2026, 9, 2)
        self.assertNotEqual(
            fingerprint_row(columns, tuple(as_amount)),
            fingerprint_row(columns, tuple(as_date)),
        )

    def test_future_without_valid_rows_is_nodata(self) -> None:
        historical = _frame(_blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}))
        future = pd.DataFrame(columns=list(EXPECTED_COLUMNS))
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.status, STATUS_NODATA)
        self.assertEqual(result.summary.final_rows, 1)
        self.assertEqual(result.summary.future_rows_received, 0)

    def test_summary_counts(self) -> None:
        historical = _frame(
            _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "H"}),
        )
        shared = _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01", "Referencia": "H"})
        future = _frame(
            dict(shared),
            _blank_row(**{FECHA_COMP_COL: "2026-09-02"}),
            _blank_row(**{SOCIEDAD_COL: "CLYD", FECHA_COMP_COL: "2026-09-02", "Referencia": "OK"}),
        )
        result = combine_fbl1n_sources(historical, future)
        self.assertEqual(result.summary.historical_rows, 1)
        self.assertEqual(result.summary.future_rows_received, 3)
        self.assertEqual(result.summary.future_invalid_excluded, 1)
        self.assertEqual(result.summary.cross_matches_excluded, 1)
        self.assertEqual(result.summary.final_rows, 2)
        self.assertEqual(result.summary.columns, 21)

    def test_fingerprint_frame_index_aligned(self) -> None:
        frame = _frame(
            _blank_row(**{SOCIEDAD_COL: "CL44", FECHA_COMP_COL: "2026-01-01"}),
            _blank_row(**{SOCIEDAD_COL: "CL45", FECHA_COMP_COL: "2026-01-02"}),
        )
        series = fingerprint_frame(frame)
        self.assertEqual(list(series.index), list(frame.index))
        self.assertEqual(len(set(series)), 2)


if __name__ == "__main__":
    unittest.main()
