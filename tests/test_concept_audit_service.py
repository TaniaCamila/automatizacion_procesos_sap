import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.services.concept_audit_service import ConceptAuditService


class ConceptAuditServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ConceptAuditService()

    def test_build_report_splits_usd_and_no_usd_by_currency_group(self) -> None:
        matrix = pd.DataFrame(
            [
                {"grupo": "PPA", "concepto": "PPA_[C_T_]", "currency_group": "USD"},
                {"grupo": "PPA", "concepto": "PPA_[C_T_]", "currency_group": "USD"},
                {"grupo": "PPA", "concepto": "PPA_[C_T_]", "currency_group": "NO_USD"},
                {"grupo": "OTRO", "concepto": "OTRO[CERT]", "currency_group": "NO_USD"},
                {"grupo": "OTRO", "concepto": "OTRO[CERT2]", "currency_group": "USD"},
                {"grupo": "", "concepto": "", "currency_group": "USD"},
            ]
        )

        report = self.service.build_report(matrix)

        self.assertEqual(
            list(report.columns),
            ["Grupo", "Concepto", "USD", "NO_USD", "TOTAL"],
        )
        self.assertEqual(list(report["Grupo"]), ["OTRO", "OTRO", "PPA"])
        self.assertEqual(
            list(report["Concepto"]),
            ["OTRO[CERT2]", "OTRO[CERT]", "PPA_[C_T_]"],
        )

        ppa = report.loc[report["Concepto"] == "PPA_[C_T_]"].iloc[0]
        self.assertEqual(int(ppa["USD"]), 2)
        self.assertEqual(int(ppa["NO_USD"]), 1)
        self.assertEqual(int(ppa["TOTAL"]), 3)

        cert = report.loc[report["Concepto"] == "OTRO[CERT]"].iloc[0]
        self.assertEqual(int(cert["USD"]), 0)
        self.assertEqual(int(cert["NO_USD"]), 1)
        self.assertEqual(int(cert["TOTAL"]), 1)

    def test_build_report_ignores_currency_column_and_uses_currency_group(self) -> None:
        matrix = pd.DataFrame(
            [
                {
                    "grupo": "COST",
                    "concepto": "COST[RENE]",
                    "currency_group": "NO_USD",
                    "moneda_del_documento": "USD",
                }
            ]
        )

        report = self.service.build_report(matrix)
        self.assertEqual(int(report.loc[0, "USD"]), 0)
        self.assertEqual(int(report.loc[0, "NO_USD"]), 1)

    def test_build_report_requires_business_03_columns(self) -> None:
        with self.assertRaises(ValueError):
            self.service.build_report(pd.DataFrame({"concepto": ["X"]}))

    def test_build_report_empty_when_no_detected_concepts(self) -> None:
        matrix = pd.DataFrame(
            [
                {"grupo": "", "concepto": "", "currency_group": "USD"},
            ]
        )
        report = self.service.build_report(matrix)
        self.assertTrue(report.empty)
        self.assertEqual(
            list(report.columns),
            ["Grupo", "Concepto", "USD", "NO_USD", "TOTAL"],
        )

    def test_export_writes_concept_audit_workbook(self) -> None:
        report = pd.DataFrame(
            [
                {
                    "Grupo": "COOR",
                    "Concepto": "COOR[CSPF]",
                    "USD": 1,
                    "NO_USD": 2,
                    "TOTAL": 3,
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CONCEPT_AUDIT_20260721_120000.xlsx"
            output = self.service.export(report, path=path)
            self.assertTrue(output.exists())
            self.assertTrue(output.name.startswith("CONCEPT_AUDIT_"))
            loaded = pd.read_excel(output)
            self.assertEqual(list(loaded.columns), list(report.columns))
            self.assertEqual(int(loaded.loc[0, "TOTAL"]), 3)

    def test_generate_builds_and_exports(self) -> None:
        matrix = pd.DataFrame(
            [
                {"grupo": "PPA", "concepto": "PPA_[C_F_]", "currency_group": "USD"},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CONCEPT_AUDIT_TEST.xlsx"
            report, output = self.service.generate(matrix, path=path)
            self.assertEqual(len(report), 1)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
