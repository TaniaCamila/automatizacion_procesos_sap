import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.config.config import Config
from src.modules.margen.module import InformeMargenModule
from src.processors.fbl1n_processor import FBL1NProcessor
from src.services.conceptos_service import ConceptosService
from src.services.matriz_service import MatrizService


class StubCatalog:
    def __init__(self, values):
        self._values = values

    def get_name(self, code):
        return self._values.get(code, code)

    def exists(self, value):
        return value in self._values

    def values(self):
        return sorted(self._values.keys())

    def count(self):
        return len(self._values)


class TempConceptosConfig(Config):
    def __init__(self, conceptos_path: Path) -> None:
        super().__init__()
        self._conceptos_path = conceptos_path

    @property
    def conceptos_path(self) -> Path:
        return self._conceptos_path


class FBL1NProcessorTests(unittest.TestCase):
    def test_process_preserves_original_columns_and_adds_internal_aliases(self):
        df = pd.DataFrame(
            [
                {
                    "Texto cab.documento": "Pago prueba",
                    "Importe en moneda doc.": "1.000,50",
                    "Moneda del documento": "USD",
                    "Fecha compensación": "15/01/2024",
                    "Sociedad": "10",
                }
            ]
        )

        processor = FBL1NProcessor()
        result = processor.process(df)

        self.assertIn("Texto cab.documento", result.columns)
        self.assertIn("texto_cabdocumento", result.columns)
        self.assertIn("importe_en_moneda_doc", result.columns)
        self.assertIn("moneda_del_documento", result.columns)
        self.assertIn("fecha_compensacion", result.columns)
        self.assertIn("sociedad", result.columns)
        self.assertEqual(result.loc[0, "texto_cabdocumento"], "Pago prueba")
        self.assertAlmostEqual(result.loc[0, "importe_en_moneda_doc"], 1000.5)


class MatrizServiceTests(unittest.TestCase):
    def test_create_matrix_enriches_records_with_catalog_information(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "SEN_[BP__]",
                    "importe_en_moneda_doc": 2500.0,
                    "moneda_del_documento": "USD",
                    "fecha_compensacion": "2024-01-15",
                    "sociedad": "10",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"USD": "USD"}),
            conceptos=StubCatalog({"SEN_[BP__]": "SEN_[BP__]"}),
        )

        result = service.create_matrix(df)

        self.assertIn("sociedad_nombre", result.columns)
        self.assertIn("moneda_valida", result.columns)
        self.assertIn("concepto_detectado", result.columns)
        self.assertIn("concepto_estado", result.columns)
        self.assertIn("mes_compensacion", result.columns)
        self.assertEqual(result.loc[0, "sociedad_nombre"], "Sociedad A")
        self.assertTrue(result.loc[0, "moneda_valida"])
        self.assertEqual(result.loc[0, "concepto_detectado"], "SEN_[BP__]")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")
        self.assertEqual(result.loc[0, "mes_compensacion"], "2024-01")

    def test_create_matrix_marks_unidentified_concepts(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Pago sin concepto conocido",
                    "importe_en_moneda_doc": 100.0,
                    "moneda_del_documento": "USD",
                    "fecha_compensacion": "2024-02-15",
                    "sociedad": "20",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"20": "Sociedad B"}),
            monedas=StubCatalog({"USD": "USD"}),
            conceptos=StubCatalog({"SEN_[BP__]": "SEN_[BP__]"}),
        )

        result = service.create_matrix(df)

        self.assertEqual(result.loc[0, "concepto_detectado"], "")
        self.assertEqual(result.loc[0, "concepto_estado"], "No identificado")

    def test_partial_matching_detects_concept_inside_document_text(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Pago parcial CONCEPTO_PARCIAL_01 liquidación",
                    "importe_en_moneda_doc": 150.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-03-10",
                    "sociedad": "10",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP"}),
            conceptos=StubCatalog({"CONCEPTO_PARCIAL_01": "CONCEPTO_PARCIAL_01"}),
        )

        result = service.create_matrix(df)

        self.assertEqual(result.loc[0, "concepto_detectado"], "CONCEPTO_PARCIAL_01")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")

    def test_longest_match_wins_over_shorter_concept(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Factura PEA_[DIST] servicio regional",
                    "importe_en_moneda_doc": 300.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-04-01",
                    "sociedad": "10",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP"}),
            conceptos=StubCatalog(
                {
                    "PEA_": "PEA_",
                    "PEA_[DIST]": "PEA_[DIST]",
                }
            ),
        )

        result = service.create_matrix(df)

        self.assertEqual(result.loc[0, "concepto_detectado"], "PEA_[DIST]")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")

    def test_unclassified_record_when_no_catalog_match(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Texto libre sin nomenclatura",
                    "importe_en_moneda_doc": 50.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-05-01",
                    "sociedad": "10",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP"}),
            conceptos=StubCatalog(
                {
                    "AAA_[UNO_]": "AAA_[UNO_]",
                    "BBB_[DOS_]": "BBB_[DOS_]",
                }
            ),
        )

        result = service.create_matrix(df)

        self.assertEqual(result.loc[0, "concepto_detectado"], "")
        self.assertEqual(result.loc[0, "concepto_estado"], "No identificado")

    def test_new_concept_added_from_excel_catalog_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "CONCEPTOS.xlsx"
            pd.DataFrame(
                {
                    "Conceptos": [
                        "AAA_[BASE]",
                        "NUEVO_[XYZ_]",
                    ]
                }
            ).to_excel(catalog_path, index=False)

            conceptos = ConceptosService(
                config_obj=TempConceptosConfig(catalog_path),
            )
            conceptos.load()

            df = pd.DataFrame(
                [
                    {
                        "Texto cab.documento": "Documento NUEVO_[XYZ_] con detalle",
                        "importe_en_moneda_doc": 990.0,
                        "moneda_del_documento": "CLP",
                        "fecha_compensacion": "2024-06-15",
                        "sociedad": "10",
                    }
                ]
            )

            service = MatrizService(
                sociedades=StubCatalog({"10": "Sociedad A"}),
                monedas=StubCatalog({"CLP": "CLP"}),
                conceptos=conceptos,
            )

            result = service.create_matrix(df)

            self.assertEqual(result.loc[0, "concepto_detectado"], "NUEVO_[XYZ_]")
            self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")


class ClassificationSheetsTests(unittest.TestCase):
    def test_resumen_conceptos_includes_sin_clasificar_row(self):
        matrix = pd.DataFrame(
            [
                {"concepto_detectado": "AAA_[UNO_]"},
                {"concepto_detectado": "AAA_[UNO_]"},
                {"concepto_detectado": "BBB_[DOS_]"},
                {"concepto_detectado": ""},
                {"concepto_detectado": ""},
            ]
        )

        module = InformeMargenModule.__new__(InformeMargenModule)
        resumen = InformeMargenModule.build_resumen_conceptos(module, matrix)

        self.assertEqual(list(resumen.columns), ["Concepto", "Cantidad"])
        self.assertEqual(resumen.iloc[-1]["Concepto"], "SIN CLASIFICAR")
        self.assertEqual(int(resumen.iloc[-1]["Cantidad"]), 2)
        self.assertEqual(int(resumen.loc[resumen["Concepto"] == "AAA_[UNO_]", "Cantidad"].iloc[0]), 2)

    def test_no_clasificados_keeps_sap_text_as_primary_column(self):
        matrix = pd.DataFrame(
            [
                {
                    "Texto cab.documento": "Sin match SAP",
                    "texto_cabdocumento": "Sin match SAP",
                    "Importe en moneda doc.": 10.0,
                    "importe_en_moneda_doc": 10.0,
                    "Moneda del documento": "CLP",
                    "moneda_del_documento": "CLP",
                    "Fecha compensación": "2024-01-01",
                    "fecha_compensacion": "2024-01-01",
                    "Sociedad": "10",
                    "sociedad": "10",
                    "sociedad_nombre": "Sociedad A",
                    "moneda_valida": True,
                    "concepto_detectado": "",
                    "concepto_estado": "No identificado",
                    "mes_compensacion": "2024-01",
                    "anio_compensacion": "2024",
                },
                {
                    "Texto cab.documento": "Con match",
                    "texto_cabdocumento": "Con match",
                    "Importe en moneda doc.": 20.0,
                    "importe_en_moneda_doc": 20.0,
                    "Moneda del documento": "CLP",
                    "moneda_del_documento": "CLP",
                    "Fecha compensación": "2024-01-02",
                    "fecha_compensacion": "2024-01-02",
                    "Sociedad": "10",
                    "sociedad": "10",
                    "sociedad_nombre": "Sociedad A",
                    "moneda_valida": True,
                    "concepto_detectado": "AAA_[UNO_]",
                    "concepto_estado": "Identificado",
                    "mes_compensacion": "2024-01",
                    "anio_compensacion": "2024",
                },
            ]
        )

        module = InformeMargenModule.__new__(InformeMargenModule)
        pending = InformeMargenModule.build_no_clasificados(module, matrix)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.columns[0], "Texto cab.documento")
        self.assertEqual(pending.iloc[0]["Texto cab.documento"], "Sin match SAP")
        self.assertIn("sociedad_nombre", pending.columns)
        self.assertIn("concepto_estado", pending.columns)


class ClpPivotExclusionTests(unittest.TestCase):
    """BUSINESS-01: PEA_[DEDC] + USD se excluye solo del Pivot CLP."""

    def _build_matrix_row(
        self,
        texto: str,
        *,
        concepto: str = "PEA_[DEDC]",
        moneda: str = "CLP",
        mes: str = "2025-12",
        importe: float = 100.0,
    ) -> dict:
        return {
            "Texto cab.documento": texto,
            "texto_cabdocumento": texto,
            "importe_en_moneda_doc": importe,
            "moneda_del_documento": moneda,
            "concepto_detectado": concepto,
            "concepto_estado": "Identificado" if concepto else "No identificado",
            "mes_compensacion": mes,
            "anio_compensacion": mes[:4],
        }

    def test_pea_dedc_without_usd_remains_in_clp_pivot_source(self):
        matrix = pd.DataFrame(
            [self._build_matrix_row("PEA_[DEDC][dic25]")]
        )
        module = InformeMargenModule.__new__(InformeMargenModule)

        filtered, excluded = InformeMargenModule.apply_clp_pivot_exclusions(
            module,
            matrix,
        )

        self.assertEqual(excluded, 0)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(
            filtered.iloc[0]["Texto cab.documento"],
            "PEA_[DEDC][dic25]",
        )

    def test_pea_dedc_dic25_usd_excluded_from_clp_pivot_source(self):
        matrix = pd.DataFrame(
            [self._build_matrix_row("PEA_[DEDC][dic25]USD[SGSO]")]
        )
        module = InformeMargenModule.__new__(InformeMargenModule)

        filtered, excluded = InformeMargenModule.apply_clp_pivot_exclusions(
            module,
            matrix,
        )

        self.assertEqual(excluded, 1)
        self.assertEqual(len(filtered), 0)

    def test_pea_dedc_ene26_usd_excluded_from_clp_pivot_source(self):
        matrix = pd.DataFrame(
            [self._build_matrix_row("PEA_[DEDC][ene26]USD[SGSO]")]
        )
        module = InformeMargenModule.__new__(InformeMargenModule)

        filtered, excluded = InformeMargenModule.apply_clp_pivot_exclusions(
            module,
            matrix,
        )

        self.assertEqual(excluded, 1)
        self.assertEqual(len(filtered), 0)

    def test_pea_dedc_mar27_usd_excluded_independent_of_month(self):
        matrix = pd.DataFrame(
            [self._build_matrix_row("PEA_[DEDC][mar27]USD[SGSO]")]
        )
        module = InformeMargenModule.__new__(InformeMargenModule)

        filtered, excluded = InformeMargenModule.apply_clp_pivot_exclusions(
            module,
            matrix,
        )

        self.assertEqual(excluded, 1)
        self.assertEqual(len(filtered), 0)

    def test_exclusion_does_not_alter_matrix_classification_columns(self):
        matrix = pd.DataFrame(
            [
                self._build_matrix_row("PEA_[DEDC][dic25]"),
                self._build_matrix_row("PEA_[DEDC][dic25]USD[SGSO]"),
                self._build_matrix_row(
                    "PEA_[DEDC][ene26]USD[SGSO]",
                    mes="2026-01",
                ),
                self._build_matrix_row(
                    "OTRO_[XXXX]",
                    concepto="OTRO_[XXXX]",
                ),
            ]
        )
        original = matrix.copy(deep=True)
        module = InformeMargenModule.__new__(InformeMargenModule)

        filtered, excluded = InformeMargenModule.apply_clp_pivot_exclusions(
            module,
            matrix,
        )

        self.assertEqual(excluded, 2)
        self.assertEqual(len(filtered), 2)
        pd.testing.assert_frame_equal(matrix, original)
        self.assertTrue(
            (matrix["concepto_detectado"] == original["concepto_detectado"]).all()
        )
        self.assertTrue(
            (matrix["concepto_estado"] == original["concepto_estado"]).all()
        )
        remaining_texts = set(filtered["Texto cab.documento"])
        self.assertEqual(
            remaining_texts,
            {"PEA_[DEDC][dic25]", "OTRO_[XXXX]"},
        )

    def test_generate_pivot_clp_omits_pea_dedc_usd_rows(self):
        from src.services.pivot_service import PivotService

        matrix = pd.DataFrame(
            [
                self._build_matrix_row("PEA_[DEDC][dic25]", importe=10.0),
                self._build_matrix_row(
                    "PEA_[DEDC][dic25]USD[SGSO]",
                    importe=999.0,
                ),
                self._build_matrix_row(
                    "PEA_[DEDC][ene26]USD[SGSO]",
                    importe=888.0,
                    mes="2026-01",
                ),
                self._build_matrix_row(
                    "PEA_[DEDC][mar27]USD[SGSO]",
                    importe=777.0,
                    mes="2027-03",
                ),
            ]
        )

        module = InformeMargenModule.__new__(InformeMargenModule)
        module.logger = __import__("logging").getLogger("test.clp.exclusion")
        module.pivot = PivotService(logger_obj=module.logger)

        pivot = InformeMargenModule.generate_pivot_clp(module, matrix)

        self.assertEqual(module._last_clp_exclusion_count, 3)
        self.assertIn("Concepto de Pago", pivot.columns)
        self.assertTrue((pivot["Concepto de Pago"] == "PEA_[DEDC]").any())
        # Solo el registro sin USD aporta al importe del concepto.
        total_col = "All" if "All" in pivot.columns else pivot.columns[-1]
        pea_row = pivot.loc[pivot["Concepto de Pago"] == "PEA_[DEDC]"].iloc[0]
        self.assertEqual(float(pea_row[total_col]), 10.0)


class Business13TdClpDynamicsTests(unittest.TestCase):
    """BUSINESS-13: dinámicas CLP según Tipo ADMIN (COM / NO_COM)."""

    def setUp(self) -> None:
        from src.services.concept_classifier import reload
        from src.services.pivot_service import PivotService

        reload()
        self.module = InformeMargenModule.__new__(InformeMargenModule)
        self.module.logger = __import__("logging").getLogger("test.td.clp")
        self.module.pivot = PivotService(logger_obj=self.module.logger)

    def _row(
        self,
        concepto: str,
        *,
        tipo: str,
        mes: str = "2026-01",
        importe: float = 100.0,
        texto: str | None = None,
    ) -> dict:
        text = texto if texto is not None else concepto
        return {
            "Texto cab.documento": text,
            "texto_cabdocumento": text,
            "importe_en_moneda_doc": importe,
            "moneda_del_documento": "CLP",
            "concepto_detectado": concepto,
            "concepto_estado": "Identificado",
            "concepto": concepto,
            "tipo": tipo,
            "mes_compensacion": mes,
            "anio_compensacion": mes[:4],
        }

    def test_dynamics_split_by_admin_tipo_and_share_structure(self) -> None:
        matrix = pd.DataFrame(
            [
                self._row("COMB[DCAR]", tipo="COM", importe=50.0, mes="2026-01"),
                self._row("COMB[TGNL]", tipo="COM", importe=25.0, mes="2026-02"),
                self._row("PPA_[C_T_]", tipo="NO_COM", importe=80.0, mes="2026-01"),
                self._row("OTRO[CERT]", tipo="NO_COM", importe=20.0, mes="2026-03"),
                self._row("SEN_[BP__]", tipo="", importe=999.0, mes="2026-01"),
            ]
        )

        dynamics = InformeMargenModule.generate_td_clp_dynamics(self.module, matrix)
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

        self.assertEqual(
            set(dynamics.keys()),
            {
                "TD_CLP_NO_COM",
                "TD_CLP_COM_2026",
                "CLP_USD_NO_COM",
                "CLP_USD_COM",
            },
        )
        for sheet_name, frame in dynamics.items():
            with self.subTest(sheet=sheet_name):
                self.assertEqual(list(frame.columns), expected_cols)

        com = dynamics["TD_CLP_COM_2026"]
        no_com = dynamics["TD_CLP_NO_COM"]

        com_concepts = set(com["Concepto de Pago"].astype(str)) - {"All"}
        no_com_concepts = set(no_com["Concepto de Pago"].astype(str)) - {"All"}

        self.assertTrue({"COMB[DCAR]", "COMB[TGNL]"}.issubset(com_concepts))
        self.assertTrue({"PPA_[C_T_]", "OTRO[CERT]"}.issubset(no_com_concepts))
        self.assertNotIn("COMB[DCAR]", no_com_concepts)
        self.assertNotIn("PPA_[C_T_]", com_concepts)
        # BUSINESS-15A: tipo vacío (SEN) pertenece a NO_COM, nunca a COM.
        self.assertNotIn("SEN_[BP__]", com_concepts)
        self.assertIn("SEN_[BP__]", no_com_concepts)

        comb_row = com.loc[com["Concepto de Pago"] == "COMB[DCAR]"].iloc[0]
        self.assertEqual(float(comb_row["Enero"]), 50.0)
        self.assertEqual(float(comb_row["Total"]), 50.0)

    def test_dynamics_segment_clp_usd_by_sociedad_texto_acreedor(self) -> None:
        """BUSINESS-18A: mueve CLP+USD a CLP_USD_* sin duplicar."""

        matrix = pd.DataFrame(
            [
                {
                    **self._row(
                        "COMB[CGNA]",
                        tipo="COM",
                        importe=100.0,
                        mes="2026-12",
                        texto="COMB[CGNA][Dic25]USD",
                    ),
                    "Sociedad": "CL44",
                    "Acreedor": "2000326095",
                },
                {
                    **self._row(
                        "PPA_[C_F_]",
                        tipo="NO_COM",
                        importe=55.0,
                        mes="2026-12",
                        texto="PPA_[C_F_][Dic25]USD[SGSO]",
                    ),
                    "Sociedad": "CLYD",
                    "Acreedor": "2000118098",
                },
                {
                    **self._row(
                        "COMB[DCAR]",
                        tipo="COM",
                        importe=50.0,
                        mes="2026-01",
                        texto="COMB[DCAR] CLP normal",
                    ),
                    "Sociedad": "CL44",
                    "Acreedor": "2000326095",
                },
                {
                    **self._row(
                        "OTRO[CERT]",
                        tipo="NO_COM",
                        importe=20.0,
                        mes="2026-03",
                        texto="OTRO[CERT] CLP normal",
                    ),
                    "Sociedad": "CL44",
                    "Acreedor": "2000649969",
                },
            ]
        )

        dynamics = InformeMargenModule.generate_td_clp_dynamics(
            self.module, matrix
        )

        usd_com = dynamics["CLP_USD_COM"]
        usd_no_com = dynamics["CLP_USD_NO_COM"]
        td_com = dynamics["TD_CLP_COM_2026"]
        td_no_com = dynamics["TD_CLP_NO_COM"]

        def _concepts(frame: pd.DataFrame) -> set[str]:
            if frame.empty:
                return set()
            return set(frame["Concepto de Pago"].astype(str)) - {"All", "Total"}

        def _sum_total(frame: pd.DataFrame) -> float:
            if frame.empty or "Total" not in frame.columns:
                return 0.0
            concepts = frame["Concepto de Pago"].fillna("").astype(str)
            work = frame.loc[~concepts.isin(["All", "Total"])]
            return float(
                pd.to_numeric(work["Total"], errors="coerce").fillna(0).sum()
            )

        self.assertEqual(_concepts(usd_com), {"COMB[CGNA]"})
        self.assertEqual(_sum_total(usd_com), 100.0)
        self.assertEqual(_concepts(usd_no_com), {"PPA_[C_F_]"})
        self.assertEqual(_sum_total(usd_no_com), 55.0)

        self.assertEqual(_concepts(td_com), {"COMB[DCAR]"})
        self.assertEqual(_concepts(td_no_com), {"OTRO[CERT]"})
        self.assertNotIn("COMB[CGNA]", _concepts(td_com))
        self.assertNotIn("PPA_[C_F_]", _concepts(td_no_com))

        self.assertAlmostEqual(
            _sum_total(td_com) + _sum_total(usd_com),
            150.0,
        )
        self.assertAlmostEqual(
            _sum_total(td_no_com) + _sum_total(usd_no_com),
            75.0,
        )


class Business03ClassifierIntegrationTests(unittest.TestCase):
    """BUSINESS-03: columnas grupo/concepto/currency_group en la matriz."""

    def test_create_matrix_adds_business_classification_columns(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Liquidación PPA_[C_T_] abril",
                    "importe_en_moneda_doc": 1000.0,
                    "moneda_del_documento": "USD",
                    "fecha_compensacion": "2024-05-01",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "Pago OTRO[CERT2] honorarios",
                    "importe_en_moneda_doc": 500.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-05-02",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "Sin patrón de negocio",
                    "importe_en_moneda_doc": 10.0,
                    "moneda_del_documento": "EUR",
                    "fecha_compensacion": "2024-05-03",
                    "sociedad": "10",
                },
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"USD": "USD", "CLP": "CLP", "EUR": "EUR"}),
            conceptos=StubCatalog({"SEN_[BP__]": "SEN_[BP__]"}),
        )

        result = service.create_matrix(df)

        self.assertIn("grupo", result.columns)
        self.assertIn("concepto", result.columns)
        self.assertIn("currency_group", result.columns)
        self.assertIn("tipo", result.columns)

        self.assertEqual(result.loc[0, "concepto"], "PPA_[C_T_]")
        self.assertEqual(result.loc[0, "concepto_detectado"], "PPA_[C_T_]")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")
        self.assertEqual(result.loc[0, "grupo"], "PPA")
        self.assertEqual(result.loc[0, "currency_group"], "USD")
        self.assertEqual(result.loc[0, "tipo"], "NO_COM")

        self.assertEqual(result.loc[1, "concepto"], "OTRO[CERT2]")
        self.assertEqual(result.loc[1, "concepto_detectado"], "OTRO[CERT2]")
        self.assertEqual(result.loc[1, "concepto_estado"], "Identificado")
        self.assertEqual(result.loc[1, "grupo"], "OTRO")
        self.assertEqual(result.loc[1, "currency_group"], "NO_USD")
        self.assertEqual(result.loc[1, "tipo"], "NO_COM")

        self.assertEqual(result.loc[2, "concepto"], "")
        self.assertEqual(result.loc[2, "concepto_detectado"], "")
        self.assertEqual(result.loc[2, "concepto_estado"], "No identificado")
        self.assertEqual(result.loc[2, "grupo"], "")
        self.assertEqual(result.loc[2, "currency_group"], "NO_USD")
        self.assertEqual(result.loc[2, "tipo"], "")

    def test_business_classification_syncs_concepto_detectado_when_present(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Factura PEA_[DIST] + COST[RENE]",
                    "importe_en_moneda_doc": 200.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-06-01",
                    "sociedad": "10",
                }
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP"}),
            conceptos=StubCatalog(
                {
                    "PEA_": "PEA_",
                    "PEA_[DIST]": "PEA_[DIST]",
                }
            ),
        )

        result = service.create_matrix(df)

        # BUG-01: la clasificación de negocio prevalece en concepto_detectado.
        self.assertEqual(result.loc[0, "concepto"], "COST[RENE]")
        self.assertEqual(result.loc[0, "concepto_detectado"], "COST[RENE]")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")
        self.assertEqual(result.loc[0, "grupo"], "COST")
        self.assertEqual(result.loc[0, "currency_group"], "NO_USD")

    def test_business16b_persists_edp_bracket_not_edp_underscore(self):
        """BUSINESS-16B: Concepto de Pago persistido es EDP_[."""

        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "EDP_[ERNC] 01_2026",
                    "importe_en_moneda_doc": 100.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2026-01-15",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "EDP_01_2026_SERV",
                    "importe_en_moneda_doc": 50.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2026-01-16",
                    "sociedad": "10",
                },
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP"}),
            conceptos=StubCatalog({"EDP_[": "EDP_["}),
        )

        result = service.create_matrix(df)

        self.assertEqual(result.loc[0, "concepto"], "EDP_[")
        self.assertEqual(result.loc[0, "concepto_detectado"], "EDP_[")
        self.assertEqual(result.loc[0, "concepto_estado"], "Identificado")
        self.assertEqual(result.loc[0, "grupo"], "EDP")
        self.assertEqual(result.loc[0, "tipo"], "NO_COM")
        self.assertNotEqual(result.loc[0, "concepto_detectado"], "EDP_")

        # BUSINESS-16: sin EDP_[ no se clasifica.
        self.assertEqual(result.loc[1, "concepto"], "")
        self.assertEqual(result.loc[1, "concepto_detectado"], "")

    def test_bug01_syncs_original_columns_with_business_concepts(self):
        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Pago PPA_[C_T_] mes",
                    "importe_en_moneda_doc": 1.0,
                    "moneda_del_documento": "USD",
                    "fecha_compensacion": "2024-01-01",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "Factura OTRO[CERT] servicios",
                    "importe_en_moneda_doc": 2.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-01-02",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "COOR[CSPF] coordinación",
                    "importe_en_moneda_doc": 3.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-01-03",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "PEA_[DEDC] deducible",
                    "importe_en_moneda_doc": 4.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-01-04",
                    "sociedad": "10",
                },
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"USD": "USD", "CLP": "CLP"}),
            conceptos=StubCatalog({"PEA_[DEDC]": "PEA_[DEDC]"}),
        )

        result = service.create_matrix(df)

        expected = {
            0: ("PPA_[C_T_]", "PPA_[C_T_]", "Identificado"),
            1: ("OTRO[CERT]", "OTRO[CERT]", "Identificado"),
            2: ("COOR[CSPF]", "COOR[CSPF]", "Identificado"),
            # PEA_[DEDC] viene del catálogo Excel (no está en concept_catalog).
            3: ("", "PEA_[DEDC]", "Identificado"),
        }
        for index, (concepto, detectado, estado) in expected.items():
            with self.subTest(index=index):
                self.assertEqual(result.loc[index, "concepto"], concepto)
                self.assertEqual(result.loc[index, "concepto_detectado"], detectado)
                self.assertEqual(result.loc[index, "concepto_estado"], estado)

    def test_business_12b_matrix_stores_only_standard_concept(self):
        """Alias y estándar deben persistirse solo como Concepto estándar."""

        df = pd.DataFrame(
            [
                {
                    "texto_cabdocumento": "Liquidación PPA_[C_T] abril",
                    "importe_en_moneda_doc": 100.0,
                    "moneda_del_documento": "CLP",
                    "fecha_compensacion": "2024-05-01",
                    "sociedad": "10",
                },
                {
                    "texto_cabdocumento": "Liquidación PPA_[C_T_] abril",
                    "importe_en_moneda_doc": 200.0,
                    "moneda_del_documento": "USD",
                    "fecha_compensacion": "2024-05-02",
                    "sociedad": "10",
                },
            ]
        )

        service = MatrizService(
            sociedades=StubCatalog({"10": "Sociedad A"}),
            monedas=StubCatalog({"CLP": "CLP", "USD": "USD"}),
            # Catálogo legacy puede contener la variante alias.
            conceptos=StubCatalog(
                {
                    "PPA_[C_T]": "PPA_[C_T]",
                    "PPA_[C_T_]": "PPA_[C_T_]",
                }
            ),
        )

        result = service.create_matrix(df)

        for index in (0, 1):
            with self.subTest(index=index):
                self.assertEqual(result.loc[index, "concepto"], "PPA_[C_T_]")
                self.assertEqual(
                    result.loc[index, "concepto_detectado"],
                    "PPA_[C_T_]",
                )
                self.assertNotEqual(
                    result.loc[index, "concepto_detectado"],
                    "PPA_[C_T]",
                )
                self.assertNotEqual(result.loc[index, "concepto"], "PPA_[C_T]")

        # Nunca ambas variantes en la matriz.
        stored = set(result["concepto_detectado"].tolist()) | set(
            result["concepto"].tolist()
        )
        self.assertEqual(stored, {"PPA_[C_T_]"})


if __name__ == "__main__":
    unittest.main()
