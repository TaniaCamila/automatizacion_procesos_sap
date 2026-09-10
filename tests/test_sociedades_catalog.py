import unittest

from src.services.sociedades_service import SociedadesService


class SociedadesCatalogTestCase(unittest.TestCase):
    def test_load_uses_actual_catalog_headers(self) -> None:
        service = SociedadesService()

        service.load()

        self.assertGreater(service.count(), 0)
        self.assertEqual(service.get_name("CL19"), "Sociedad Ejemplo")


if __name__ == "__main__":
    unittest.main()
