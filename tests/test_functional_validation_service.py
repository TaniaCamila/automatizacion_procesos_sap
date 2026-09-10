import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from src.modules.margen.module import InformeMargenModule
from src.services.concept_classifier import reload
from src.services.functional_validation_service import (
    FunctionalValidationService,
    REPORT_TITLE,
)
from src.services.pivot_service import PivotService


def _service() -> FunctionalValidationService:
    sharepoint = MagicMock()
    sharepoint.health_check.return_value = {"configured": True, "missing": []}
    return FunctionalValidationService(
        sharepoint_service=sharepoint,
        logger_obj=logging.getLogger("test.validation"),
    )


def _matrix_row(
    concepto: str,
    *,
    tipo: str,
    mes: str = "2026-01",
    importe: float = 100.0,
) -> dict:
    return {
        "Texto cab.documento": concepto,
        "texto_cabdocumento": concepto,
        "importe_en_moneda_doc": importe,
        "moneda_del_documento": "CLP",
        "concepto_detectado": concepto,
        "concepto": concepto,
        "concepto_estado": "Identificado",
        "grupo": concepto[:4],
        "currency_group": "NO_USD",
        "tipo": tipo,
        "mes_compensacion": mes,
        "anio_compensacion": mes[:4],
    }


def _build_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _matrix_row("COMB[DCAR]", tipo="COM", importe=50.0),
            _matrix_row("PPA_[C_T_]", tipo="NO_COM", importe=80.0, mes="2026-02"),
            _matrix_row("OTRO[CERT]", tipo="NO_COM", importe=20.0, mes="2026-03"),
        ]
    )


def _build_dynamics(matrix: pd.DataFrame) -> dict[str, pd.DataFrame]:
    module = InformeMargenModule.__new__(InformeMargenModule)
    module.logger = logging.getLogger("test.validation.module")
    module.pivot = PivotService(logger_obj=module.logger)
    return InformeMargenModule.generate_td_clp_dynamics(module, matrix)


class FunctionalValidationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reload()
        self.service = _service()
        self.matrix = _build_matrix()
        self.dynamics = _build_dynamics(self.matrix)

    def test_validate_catalog_ok_with_project_admin(self) -> None:
        result = self.service.validate_catalog()
        self.assertTrue(result.ok, result.detail)

    def test_validate_matrix_detects_missing_columns(self) -> None:
        ok = self.service.validate_matrix(self.matrix)
        self.assertTrue(ok.ok)

        broken = self.matrix.drop(columns=["tipo", "grupo"])
        bad = self.service.validate_matrix(broken)
        self.assertFalse(bad.ok)
        self.assertIn("tipo", bad.detail)
        self.assertIn("grupo", bad.detail)

    def test_validate_normalization_detects_alias(self) -> None:
        ok = self.service.validate_normalization(self.matrix)
        self.assertTrue(ok.ok, ok.detail)

        with_alias = pd.concat(
            [
                self.matrix,
                pd.DataFrame([_matrix_row("PPA_[C_T]", tipo="NO_COM")]),
            ],
            ignore_index=True,
        )
        bad = self.service.validate_normalization(with_alias)
        self.assertFalse(bad.ok)
        self.assertIn("PPA_[C_T]", bad.detail)

    def test_validate_dynamics_match_matrix(self) -> None:
        result = self.service.validate_dynamics(self.matrix, self.dynamics)
        self.assertTrue(result.ok, result.detail)

    def test_validate_dynamics_detects_mismatch(self) -> None:
        tampered = {
            name: frame.copy() for name, frame in self.dynamics.items()
        }
        td = tampered["TD_CLP_COM_2026"]
        td.loc[td.index[0], "Total"] = float(td.loc[td.index[0], "Total"]) + 999
        result = self.service.validate_dynamics(self.matrix, tampered)
        self.assertFalse(result.ok)

    def test_validate_amounts_ok_and_mismatch(self) -> None:
        ok = self.service.validate_amounts(self.dynamics)
        self.assertTrue(ok.ok, ok.detail)

        tampered = {
            name: frame.copy() for name, frame in self.dynamics.items()
        }
        td = tampered["TD_CLP_NO_COM"]
        td.loc[td.index[0], "Enero"] = (
            float(td.loc[td.index[0], "Enero"] or 0) + 123
        )
        bad = self.service.validate_amounts(tampered)
        self.assertFalse(bad.ok)

    def test_validate_powerbi_model_checks_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            matrix_file = Path(tmp) / "MATRIZ_FBL1N_TEST.xlsx"
            pivot_file = Path(tmp) / "PIVOT_MARGEN_TEST.xlsx"

            with pd.ExcelWriter(matrix_file) as writer:
                pd.DataFrame({"x": [1]}).to_excel(
                    writer, sheet_name="MATRIZ_FBL1N", index=False
                )
                for name in (
                    "TD_CLP_NO_COM",
                    "TD_CLP_COM_2026",
                    "CLP_USD_NO_COM",
                    "CLP_USD_COM",
                ):
                    pd.DataFrame({"x": [1]}).to_excel(
                        writer, sheet_name=name, index=False
                    )
            with pd.ExcelWriter(pivot_file) as writer:
                for name in (
                    "PIVOT",
                    "TD_CLP_NO_COM",
                    "TD_CLP_COM_2026",
                    "CLP_USD_NO_COM",
                    "CLP_USD_COM",
                    "KPIS",
                    "METADATA",
                ):
                    pd.DataFrame({"x": [1]}).to_excel(
                        writer, sheet_name=name, index=False
                    )

            ok = self.service.validate_powerbi_model(matrix_file, pivot_file)
            self.assertTrue(ok.ok, ok.detail)

            bad = self.service.validate_powerbi_model(matrix_file, None)
            self.assertFalse(bad.ok)
            self.assertIn("KPIS", bad.detail)

    def test_validate_sharepoint_health_check(self) -> None:
        result = self.service.validate_sharepoint()
        self.assertTrue(result.ok)
        self.service.sharepoint_service.health_check.assert_called_once()

    def test_run_builds_summary_with_all_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            matrix_file = Path(tmp) / "MATRIZ_FBL1N_TEST.xlsx"
            pivot_file = Path(tmp) / "PIVOT_MARGEN_TEST.xlsx"
            with pd.ExcelWriter(matrix_file) as writer:
                self.matrix.to_excel(
                    writer, sheet_name="MATRIZ_FBL1N", index=False
                )
                for name, frame in self.dynamics.items():
                    frame.to_excel(writer, sheet_name=name, index=False)
            with pd.ExcelWriter(pivot_file) as writer:
                for name in ("PIVOT", "KPIS", "METADATA"):
                    pd.DataFrame({"x": [1]}).to_excel(
                        writer, sheet_name=name, index=False
                    )
                for name, frame in self.dynamics.items():
                    frame.to_excel(writer, sheet_name=name, index=False)

            report = self.service.run(
                matrix=self.matrix,
                dynamics=self.dynamics,
                matrix_file=matrix_file,
                pivot_file=pivot_file,
            )

        self.assertTrue(report.success, report.summary())
        self.assertEqual(len(report.checks), 7)
        summary = report.summary()
        self.assertIn(REPORT_TITLE, summary)
        self.assertIn("RESULTADO GLOBAL: OK", summary)


if __name__ == "__main__":
    unittest.main()
