import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config.sharepoint_config import REQUIRED_ENV_VARS, SharePointConfig
from src.services.sharepoint_service import SharePointService


COMPLETE_ENV = {
    "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/CBO",
    "SHAREPOINT_DOCUMENT_LIBRARY": "Documentos",
    "SHAREPOINT_TARGET_FOLDER": "Operaciones/FBL1N",
    "SHAREPOINT_CLIENT_ID": "client-id",
    "SHAREPOINT_TENANT_ID": "tenant-id",
    "SHAREPOINT_CLIENT_SECRET": "client-secret",
}


class SharePointConfigTests(unittest.TestCase):
    def test_required_env_vars_match_contract(self) -> None:
        self.assertEqual(
            set(REQUIRED_ENV_VARS),
            {
                "SHAREPOINT_SITE_URL",
                "SHAREPOINT_DOCUMENT_LIBRARY",
                "SHAREPOINT_TARGET_FOLDER",
                "SHAREPOINT_CLIENT_ID",
                "SHAREPOINT_TENANT_ID",
                "SHAREPOINT_CLIENT_SECRET",
            },
        )

    @patch.dict(os.environ, COMPLETE_ENV, clear=False)
    def test_from_env_loads_all_fields(self) -> None:
        config = SharePointConfig.from_env()
        self.assertEqual(config.SITE_URL, COMPLETE_ENV["SHAREPOINT_SITE_URL"])
        self.assertEqual(
            config.DOCUMENT_LIBRARY,
            COMPLETE_ENV["SHAREPOINT_DOCUMENT_LIBRARY"],
        )
        self.assertEqual(
            config.TARGET_FOLDER,
            COMPLETE_ENV["SHAREPOINT_TARGET_FOLDER"],
        )
        self.assertEqual(config.CLIENT_ID, COMPLETE_ENV["SHAREPOINT_CLIENT_ID"])
        self.assertEqual(config.TENANT_ID, COMPLETE_ENV["SHAREPOINT_TENANT_ID"])
        self.assertEqual(
            config.CLIENT_SECRET,
            COMPLETE_ENV["SHAREPOINT_CLIENT_SECRET"],
        )
        self.assertTrue(config.is_configured())
        config.validate()

    @patch.dict(
        os.environ,
        {
            "SHAREPOINT_SITE_URL": "",
            "SHAREPOINT_DOCUMENT_LIBRARY": "Documentos",
            "SHAREPOINT_TARGET_FOLDER": "",
            "SHAREPOINT_CLIENT_ID": "id",
            "SHAREPOINT_TENANT_ID": "",
            "SHAREPOINT_CLIENT_SECRET": "secret",
        },
        clear=False,
    )
    def test_validate_raises_when_incomplete(self) -> None:
        config = SharePointConfig.from_env()
        self.assertFalse(config.is_configured())
        self.assertIn("SITE_URL", config.missing_fields())
        self.assertIn("TARGET_FOLDER", config.missing_fields())
        self.assertIn("TENANT_ID", config.missing_fields())
        with self.assertRaises(ValueError) as raised:
            config.validate()
        self.assertIn("SITE_URL", str(raised.exception))


class SharePointServiceTests(unittest.TestCase):
    @patch.dict(os.environ, COMPLETE_ENV, clear=False)
    def test_health_check_configured(self) -> None:
        service = SharePointService()
        status = service.health_check()
        self.assertEqual(status, {"configured": True, "missing": []})

    @patch.dict(
        os.environ,
        {
            "SHAREPOINT_SITE_URL": "",
            "SHAREPOINT_DOCUMENT_LIBRARY": "",
            "SHAREPOINT_TARGET_FOLDER": "",
            "SHAREPOINT_CLIENT_ID": "",
            "SHAREPOINT_TENANT_ID": "",
            "SHAREPOINT_CLIENT_SECRET": "",
        },
        clear=False,
    )
    def test_health_check_reports_missing(self) -> None:
        service = SharePointService(config=SharePointConfig.from_env())
        status = service.health_check()
        self.assertFalse(status["configured"])
        self.assertEqual(
            set(status["missing"]),
            {
                "SITE_URL",
                "DOCUMENT_LIBRARY",
                "TARGET_FOLDER",
                "CLIENT_ID",
                "TENANT_ID",
                "CLIENT_SECRET",
            },
        )

    @patch.dict(os.environ, COMPLETE_ENV, clear=False)
    def test_pending_methods_raise_not_implemented(self) -> None:
        service = SharePointService()
        with self.assertRaises(NotImplementedError):
            service.connect()
        with self.assertRaises(NotImplementedError):
            service.upload_file(Path("data/output/MATRIZ_FBL1N.xlsx"))
        with self.assertRaises(NotImplementedError):
            service.upload_folder(Path("data/output"))
        with self.assertRaises(NotImplementedError):
            service.file_exists("MATRIZ_FBL1N.xlsx")
        with self.assertRaises(NotImplementedError):
            service.list_files()


if __name__ == "__main__":
    unittest.main()
