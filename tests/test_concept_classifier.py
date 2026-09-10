import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.config.concept_catalog import all_concepts
from src.services.concept_classifier import (
    classify,
    concepts_for,
    currency_group,
    group,
    groups,
    reload,
    search,
    tipo,
    to_standard,
)


def _write_admin(path: Path, rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    frame.to_excel(path, sheet_name="CONCEPTOS_ADMIN", index=False)


class ConceptAdminCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.admin_path = Path(self.tmp.name) / "CONCEPTOS_ADMIN.xlsx"
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "PPA_[C_T_]",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "PPA_[C_T_]",
                    "Concepto estándar": "PPA_[C_T_]",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "OTRO[CERT2]",
                    "Concepto estándar": "OTRO[CERT2]",
                    "Grupo": "OTRO",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "OTRO[CERT]",
                    "Concepto estándar": "OTRO[CERT]",
                    "Grupo": "OTRO",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "COMB[DCAR]",
                    "Concepto estándar": "COMB[DCAR]",
                    "Grupo": "COMB",
                    "Tipo": "COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "EDP_[",
                    "Concepto estándar": "EDP_[",
                    "Grupo": "EDP",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "INACTIVO_X",
                    "Concepto estándar": "INACTIVO_X",
                    "Grupo": "X",
                    "Tipo": "NO_COM",
                    "Activo": "NO",
                },
            ],
        )
        reload(self.admin_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        # Restaurar catálogo real del proyecto para otros tests.
        reload()

    def test_loads_active_rows_only(self) -> None:
        self.assertIn("PPA_[C_T_]", all_concepts())
        self.assertIn("COMB[DCAR]", all_concepts())
        self.assertNotIn("INACTIVO_X", all_concepts())

    def test_alias_maps_to_standard_concept(self) -> None:
        self.assertEqual(search("Factura PPA_[C_T] mes"), "PPA_[C_T_]")
        self.assertEqual(search("Factura PPA_[C_T_] mes"), "PPA_[C_T_]")

    def test_to_standard_normalizes_aliases(self) -> None:
        self.assertEqual(to_standard("PPA_[C_T]"), "PPA_[C_T_]")
        self.assertEqual(to_standard("PPA_[C_T_]"), "PPA_[C_T_]")
        self.assertEqual(to_standard("LEGACY_SEN"), "LEGACY_SEN")
        self.assertEqual(to_standard(""), "")
        self.assertEqual(to_standard(None), "")

    def test_longest_match_and_standard(self) -> None:
        self.assertEqual(search("Pago OTRO[CERT2]"), "OTRO[CERT2]")
        self.assertEqual(search("Pago OTRO[CERT]"), "OTRO[CERT]")

    def test_unknown_remains_unidentified(self) -> None:
        self.assertIsNone(search("Sin concepto admin"))
        result = classify("Sin concepto admin", "CLP")
        self.assertIsNone(result["concepto"])
        self.assertIsNone(result["grupo"])
        self.assertIsNone(result["tipo"])

    def test_classify_includes_tipo(self) -> None:
        result = classify("COMB[DCAR] despacho", "USD")
        self.assertEqual(
            result,
            {
                "grupo": "COMB",
                "concepto": "COMB[DCAR]",
                "moneda": "USD",
                "currency_group": "USD",
                "tipo": "COM",
            },
        )
        self.assertEqual(tipo("COMB[DCAR]"), "COM")
        self.assertEqual(tipo("PPA_[C_T_]"), "NO_COM")

    def test_group_and_helpers(self) -> None:
        self.assertEqual(group("PPA_[C_T_]"), "PPA")
        self.assertEqual(group("EDP_["), "EDP")
        self.assertIn("COMB", groups())
        self.assertIn("COMB[DCAR]", concepts_for("COMB"))
        self.assertEqual(currency_group("CLP"), "NO_USD")


class ProjectAdminCatalogSmokeTests(unittest.TestCase):
    """Validar el CONCEPTOS_ADMIN.xlsx del proyecto."""

    def setUp(self) -> None:
        reload()

    def test_project_admin_file_classifies_seed_concepts(self) -> None:
        self.assertEqual(search("doc COMB[TGNL]"), "COMB[TGNL]")
        self.assertEqual(search("EDP_[ERNC] 01_2026"), "EDP_[")
        self.assertEqual(classify("PPA_[C_T] alias", "CLP")["concepto"], "PPA_[C_T_]")


class Business16EdpDetectionTests(unittest.TestCase):
    """BUSINESS-16: EDP solo se detecta con el patrón EDP_[."""

    def setUp(self) -> None:
        reload()

    def test_detects_edp_bracket_patterns(self) -> None:
        self.assertEqual(search("EDP_[ERNC]"), "EDP_[")
        self.assertEqual(search("EDP_[ABC]"), "EDP_[")
        self.assertEqual(search("EDP_[XXXX]"), "EDP_[")
        self.assertEqual(search("Pago EDP_[ERNC] enero"), "EDP_[")

    def test_rejects_edp_without_bracket_pattern(self) -> None:
        self.assertIsNone(search("EDP"))
        self.assertIsNone(search("PAGO EDP"))
        self.assertIsNone(search("EDP COSTO"))
        self.assertIsNone(search("MI_EDP"))
        self.assertIsNone(search("EDP-XXX"))
        self.assertIsNone(search("EDP_01_2026_SERV"))

    def test_classify_returns_official_concept(self) -> None:
        result = classify("EDP_[ERNC]", "CLP")
        self.assertEqual(result["concepto"], "EDP_[")
        self.assertEqual(result["grupo"], "EDP")
        self.assertEqual(result["tipo"], "NO_COM")

    def test_other_concepts_unaffected(self) -> None:
        self.assertEqual(search("COMB[DCAR] despacho"), "COMB[DCAR]")
        self.assertEqual(search("Factura PPA_[C_T] mes"), "PPA_[C_T_]")
        self.assertEqual(search("Pago OTRO[CERT2]"), "OTRO[CERT2]")


class Business16BEdpPersistenceTests(unittest.TestCase):
    """BUSINESS-16B: el concepto oficial/persistido es EDP_[."""

    def setUp(self) -> None:
        reload()

    def test_to_standard_normalizes_legacy_edp(self) -> None:
        self.assertEqual(to_standard("EDP_"), "EDP_[")
        self.assertEqual(to_standard("EDP_["), "EDP_[")

    def test_search_and_classify_return_edp_bracket(self) -> None:
        self.assertEqual(search("EDP_[ERNC]"), "EDP_[")
        self.assertEqual(classify("EDP_[ERNC]", "CLP")["concepto"], "EDP_[")

    def test_other_concepts_persistence_unaffected(self) -> None:
        self.assertEqual(to_standard("COMB[DCAR]"), "COMB[DCAR]")
        self.assertEqual(to_standard("PPA_[C_T]"), "PPA_[C_T_]")


if __name__ == "__main__":
    unittest.main()
