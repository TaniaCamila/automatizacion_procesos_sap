"""Pruebas del ExcelLoader, incluida la ruta opcional de FBL1N."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.loaders.excel_loader import ExcelLoader


class ExcelLoaderFbl1nTests(unittest.TestCase):
    def test_load_fbl1n_without_path_uses_config(self) -> None:
        loader = ExcelLoader()
        sentinel = pd.DataFrame({"a": [1]})
        with patch.object(loader, "load_excel", return_value=sentinel) as mocked:
            result = loader.load_fbl1n()
        mocked.assert_called_once_with(loader.config.fbl1n_path)
        self.assertIs(result, sentinel)

    def test_load_fbl1n_with_path_uses_argument(self) -> None:
        loader = ExcelLoader()
        target = Path("FBL1N_FUTURO.xlsx")
        sentinel = pd.DataFrame({"a": [2]})
        with patch.object(loader, "load_excel", return_value=sentinel) as mocked:
            result = loader.load_fbl1n(target)
        mocked.assert_called_once_with(target)
        self.assertIs(result, sentinel)

    def test_missing_file_error_uses_filename_only(self) -> None:
        loader = ExcelLoader()
        missing = Path("no_existe_fbl1n.xlsx")
        with self.assertRaises(FileNotFoundError) as ctx:
            loader._read_excel(missing)
        self.assertIn("no_existe_fbl1n.xlsx", str(ctx.exception))
        self.assertNotIn("Users", str(ctx.exception))
        self.assertEqual(ctx.exception.args[0], "no_existe_fbl1n.xlsx")

    def test_is_locked_false_for_readable_file(self) -> None:
        loader = ExcelLoader()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "readable.xlsx"
            path.write_bytes(b"ok")
            self.assertFalse(loader.is_locked(path))

    def test_is_locked_false_when_missing(self) -> None:
        loader = ExcelLoader()
        self.assertFalse(loader.is_locked(Path("no_existe_lock.xlsx")))

    def test_load_excel_roundtrip_temp_file(self) -> None:
        loader = ExcelLoader()
        frame = pd.DataFrame({"Sociedad": ["CL44"], "Valor": [1]})
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "mini.xlsx"
            frame.to_excel(path, index=False)
            loaded = loader.load_excel(path)
        self.assertEqual(list(loaded["Sociedad"]), ["CL44"])
        self.assertEqual(len(loaded), 1)
