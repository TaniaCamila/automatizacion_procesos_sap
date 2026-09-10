import logging
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.services.pivot_report_service import PivotReportService


def _matrix() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "concepto_detectado": "COMB[DCAR]",
                "Fecha compensación": "2026-01-15",
                "Importe en moneda doc.": 50.0,
                "tipo": "COM",
                "moneda_del_documento": "CLP",
                "sociedad": "CL44",
                "acreedor": "2000999999",
                "texto_cabdocumento": "COMB[DCAR]",
            },
            {
                "concepto_detectado": "PPA_[C_T_]",
                "Fecha compensación": "2026-02-10",
                "Importe en moneda doc.": 80.0,
                "tipo": "NO_COM",
                "moneda_del_documento": "CLP",
                "sociedad": "CL44",
                "acreedor": "2000999999",
                "texto_cabdocumento": "PPA_[C_T_]",
            },
            {
                "concepto_detectado": "PPA_[C_T_]",
                "Fecha compensación": "2026-02-20",
                "Importe en moneda doc.": 20.0,
                "tipo": "NO_COM",
                "moneda_del_documento": "USD",
                "sociedad": "CL44",
                "acreedor": "2000999999",
                "texto_cabdocumento": "PPA_[C_T_] USD",
            },
            {
                "concepto_detectado": "SEN_[BP__]",
                "Fecha compensación": "2026-03-01",
                "Importe en moneda doc.": 999.0,
                "tipo": "",
                "moneda_del_documento": "CLP",
                "sociedad": "CL44",
                "acreedor": "2000999999",
                "texto_cabdocumento": "SEN_[BP__]",
            },
        ]
    )


_EXPECTED_TD_SHEETS = {
    "TD_CLP_NO_COM",
    "TD_CLP_COM_2026",
    "CLP_USD_NO_COM",
    "CLP_USD_COM",
}


class PivotReportTdDynamicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PivotReportService(
            logger_obj=logging.getLogger("test.pivot.report")
        )

    def test_build_td_dynamics_splits_by_persisted_tipo(self) -> None:
        dynamics = self.service.build_td_dynamics(_matrix())

        expected_cols = [
            "Concepto de Pago",
            "Enero",
            "Febrero",
            "Marzo",
            "Abril",
            "Mayo",
            "Junio",
            "Julio",
            "Agosto",
            "Septiembre",
            "Octubre",
            "Noviembre",
            "Diciembre",
            "Total",
        ]
        self.assertEqual(set(dynamics.keys()), _EXPECTED_TD_SHEETS)
        for frame in dynamics.values():
            self.assertEqual(list(frame.columns), expected_cols)

        com = dynamics["TD_CLP_COM_2026"]
        no_com = dynamics["TD_CLP_NO_COM"]

        self.assertEqual(
            com["Concepto de Pago"].tolist(),
            ["COMB[DCAR]"],
        )
        self.assertEqual(float(com.iloc[0]["Enero"]), 50.0)
        self.assertEqual(float(com.iloc[0]["Total"]), 50.0)

        # NO_COM: solo CLP (la fila USD de PPA queda fuera).
        # BUSINESS-15A: tipo vacío (SEN) pertenece a NO_COM.
        self.assertEqual(
            no_com["Concepto de Pago"].tolist(),
            ["PPA_[C_T_]", "SEN_[BP__]"],
        )
        ppa = no_com.loc[no_com["Concepto de Pago"] == "PPA_[C_T_]"].iloc[0]
        self.assertEqual(float(ppa["Febrero"]), 80.0)
        self.assertEqual(float(ppa["Total"]), 80.0)
        sen = no_com.loc[no_com["Concepto de Pago"] == "SEN_[BP__]"].iloc[0]
        self.assertEqual(float(sen["Marzo"]), 999.0)

        # Nada con tipo vacío entra a COM.
        self.assertNotIn("SEN_[BP__]", com["Concepto de Pago"].tolist())
        self.assertTrue(dynamics["CLP_USD_COM"].empty)
        self.assertTrue(dynamics["CLP_USD_NO_COM"].empty)

    def test_build_td_dynamics_segments_clp_usd(self) -> None:
        """BUSINESS-18A: CL44/CLYD + USD + acreedor → CLP_USD_*."""

        matrix = pd.DataFrame(
            [
                {
                    "concepto_detectado": "COMB[CGNA]",
                    "Fecha compensación": "2026-12-01",
                    "Importe en moneda doc.": 100.0,
                    "tipo": "COM",
                    "moneda_del_documento": "CLP",
                    "sociedad": "CL44",
                    "acreedor": "2000326095",
                    "texto_cabdocumento": "COMB[CGNA][Dic25]USD",
                },
                {
                    "concepto_detectado": "PPA_[C_F_]",
                    "Fecha compensación": "2026-11-01",
                    "Importe en moneda doc.": 40.0,
                    "tipo": "NO_COM",
                    "moneda_del_documento": "CLP",
                    "sociedad": "CLYD",
                    "acreedor": "2000118098",
                    "texto_cabdocumento": "PPA_[C_F_][Nov25]USD[L][IV]",
                },
                {
                    "concepto_detectado": "COMB[DCAR]",
                    "Fecha compensación": "2026-01-15",
                    "Importe en moneda doc.": 50.0,
                    "tipo": "COM",
                    "moneda_del_documento": "CLP",
                    "sociedad": "CL44",
                    "acreedor": "2000999999",
                    "texto_cabdocumento": "COMB[DCAR] sin usd",
                },
            ]
        )
        dynamics = self.service.build_td_dynamics(matrix)

        self.assertEqual(
            dynamics["CLP_USD_COM"]["Concepto de Pago"].tolist(),
            ["COMB[CGNA]"],
        )
        self.assertEqual(
            float(dynamics["CLP_USD_COM"].iloc[0]["Total"]),
            100.0,
        )
        self.assertEqual(
            dynamics["CLP_USD_NO_COM"]["Concepto de Pago"].tolist(),
            ["PPA_[C_F_]"],
        )
        self.assertEqual(
            float(dynamics["CLP_USD_NO_COM"].iloc[0]["Total"]),
            40.0,
        )
        self.assertEqual(
            dynamics["TD_CLP_COM_2026"]["Concepto de Pago"].tolist(),
            ["COMB[DCAR]"],
        )
        self.assertTrue(dynamics["TD_CLP_NO_COM"].empty)
        # Sin duplicados: el USD no queda en TD_CLP_*.
        self.assertNotIn(
            "COMB[CGNA]",
            dynamics["TD_CLP_COM_2026"]["Concepto de Pago"].tolist(),
        )
        self.assertNotIn(
            "PPA_[C_F_]",
            dynamics["TD_CLP_NO_COM"]["Concepto de Pago"].tolist(),
        )

    def test_build_td_dynamics_requires_exact_concept_for_acreedor(self) -> None:
        """BUSINESS-18B: concepto distinto al mapeado no se mueve."""

        matrix = pd.DataFrame(
            [
                {
                    # Acreedor 2000326095 espera COMB[CGNA], no COMB[TGNL].
                    "concepto_detectado": "COMB[TGNL]",
                    "Fecha compensación": "2026-12-01",
                    "Importe en moneda doc.": 100.0,
                    "tipo": "COM",
                    "moneda_del_documento": "CLP",
                    "sociedad": "CL44",
                    "acreedor": "2000326095",
                    "texto_cabdocumento": "COMB[TGNL][Dic25]USD",
                },
                {
                    "concepto_detectado": "COMB[CGNA]",
                    "Fecha compensación": "2026-12-01",
                    "Importe en moneda doc.": 50.0,
                    "tipo": "COM",
                    "moneda_del_documento": "CLP",
                    "sociedad": "CL44",
                    "acreedor": "2000326095",
                    "texto_cabdocumento": "COMB[CGNA][Dic25]USD",
                },
            ]
        )
        dynamics = self.service.build_td_dynamics(matrix)

        self.assertEqual(
            dynamics["CLP_USD_COM"]["Concepto de Pago"].tolist(),
            ["COMB[CGNA]"],
        )
        self.assertEqual(
            dynamics["TD_CLP_COM_2026"]["Concepto de Pago"].tolist(),
            ["COMB[TGNL]"],
        )
        self.assertNotIn(
            "COMB[TGNL]",
            dynamics["CLP_USD_COM"]["Concepto de Pago"].tolist(),
        )

    def test_build_td_dynamics_without_tipo_column(self) -> None:
        """BUSINESS-15A: sin columna tipo, nada es COM → todo a NO_COM."""

        matrix = _matrix().drop(columns=["tipo"])
        dynamics = self.service.build_td_dynamics(matrix)

        self.assertTrue(dynamics["TD_CLP_COM_2026"].empty)
        no_com_concepts = dynamics["TD_CLP_NO_COM"]["Concepto de Pago"].tolist()
        self.assertIn("COMB[DCAR]", no_com_concepts)
        self.assertIn("PPA_[C_T_]", no_com_concepts)
        self.assertIn("SEN_[BP__]", no_com_concepts)

    def test_export_keeps_pivot_and_adds_td_sheets(self) -> None:
        matrix = _matrix()
        pivot = self.service.build_pivot(matrix)
        dynamics = self.service.build_td_dynamics(matrix)

        with tempfile.TemporaryDirectory() as tmp:
            output = self.service.export(
                pivot,
                path=Path(tmp) / "PIVOT_MARGEN_TEST.xlsx",
                td_dynamics=dynamics,
            )
            with pd.ExcelFile(output) as excel:
                sheets = list(excel.sheet_names)

        # BUSINESS-15: PIVOT se mantiene y se agregan las dinámicas TD.
        self.assertEqual(
            sheets,
            [
                "PIVOT",
                "TD_CLP_NO_COM",
                "TD_CLP_COM_2026",
                "CLP_USD_NO_COM",
                "CLP_USD_COM",
                "KPIS",
                "METADATA",
            ],
        )


if __name__ == "__main__":
    unittest.main()
