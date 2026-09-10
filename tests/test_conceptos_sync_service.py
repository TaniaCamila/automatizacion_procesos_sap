import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.services import conceptos_sync_service as css
from src.services.conceptos_sync_service import (
    CONCEPTOS_COLUMN,
    GROUP_COLUMN,
    STANDARD_COLUMN,
    ConceptosConcurrentModificationError,
    _temp_xlsx_path,
    os as sync_os,
    sync_conceptos_from_admin,
)


def _write_admin(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_excel(path, sheet_name="CONCEPTOS_ADMIN", index=False)


def _write_conceptos(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_excel(path, sheet_name="CONCEPTOS", index=False)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _leftover_temps(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.name.endswith(".tmp.xlsx")
    )


class ConceptosSyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.admin_path = self.root / "CONCEPTOS_ADMIN.xlsx"
        self.conceptos_path = self.root / "CONCEPTOS.xlsx"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_adds_new_concepts_and_preserves_legacy(self) -> None:
        _write_conceptos(
            self.conceptos_path,
            [{CONCEPTOS_COLUMN: "SEN_[BP__]"}],
        )
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "COMB[DCAR]",
                    "Concepto estándar": "COMB[DCAR]",
                    "Grupo": "COMB",
                    "Tipo": "COM",
                    "Activo": "SI",
                },
                {
                    "Concepto encontrado": "INACTIVO",
                    "Concepto estándar": "INACTIVO",
                    "Grupo": "X",
                    "Tipo": "NO_COM",
                    "Activo": "NO",
                },
            ],
        )

        result = sync_conceptos_from_admin(
            admin_path=self.admin_path,
            conceptos_path=self.conceptos_path,
        )
        frame = pd.read_excel(self.conceptos_path)

        self.assertEqual(result.added, 1)
        self.assertEqual(result.legacy_preserved, 1)
        self.assertTrue(result.changed)
        self.assertTrue(result.written)
        self.assertIn("SEN_[BP__]", frame[CONCEPTOS_COLUMN].tolist())
        self.assertIn("COMB[DCAR]", frame[CONCEPTOS_COLUMN].tolist())
        self.assertNotIn("INACTIVO", frame[CONCEPTOS_COLUMN].tolist())

        comb = frame.loc[frame[CONCEPTOS_COLUMN] == "COMB[DCAR]"].iloc[0]
        self.assertEqual(comb[STANDARD_COLUMN], "COMB[DCAR]")
        self.assertEqual(comb[GROUP_COLUMN], "COMB")

    def test_updates_standard_and_group_without_deleting(self) -> None:
        _write_conceptos(
            self.conceptos_path,
            [
                {
                    CONCEPTOS_COLUMN: "PPA_[C_T]",
                    STANDARD_COLUMN: "OLD",
                    GROUP_COLUMN: "OLD_G",
                },
                {CONCEPTOS_COLUMN: "LEGACY_ONLY"},
            ],
        )
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
            ],
        )

        result = sync_conceptos_from_admin(
            admin_path=self.admin_path,
            conceptos_path=self.conceptos_path,
        )
        frame = pd.read_excel(self.conceptos_path)

        self.assertEqual(result.updated, 1)
        self.assertEqual(result.added, 0)
        self.assertEqual(result.legacy_preserved, 1)
        self.assertTrue(result.changed)
        self.assertTrue(result.written)
        self.assertEqual(len(frame), 2)

        ppa = frame.loc[frame[CONCEPTOS_COLUMN] == "PPA_[C_T]"].iloc[0]
        self.assertEqual(ppa[STANDARD_COLUMN], "PPA_[C_T_]")
        self.assertEqual(ppa[GROUP_COLUMN], "PPA")
        self.assertIn("LEGACY_ONLY", frame[CONCEPTOS_COLUMN].tolist())

    def test_creates_conceptos_when_missing(self) -> None:
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "EDP_[",
                    "Concepto estándar": "EDP_[",
                    "Grupo": "EDP",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )

        result = sync_conceptos_from_admin(
            admin_path=self.admin_path,
            conceptos_path=self.conceptos_path,
        )
        frame = pd.read_excel(self.conceptos_path)

        self.assertTrue(self.conceptos_path.exists())
        self.assertEqual(result.added, 1)
        self.assertTrue(result.changed)
        self.assertTrue(result.written)
        self.assertEqual(frame.iloc[0][CONCEPTOS_COLUMN], "EDP_[")
        self.assertEqual(frame.iloc[0][GROUP_COLUMN], "EDP")
        self.assertTrue(zipfile.is_zipfile(self.conceptos_path))


class ConceptosAtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.admin_path = self.root / "CONCEPTOS_ADMIN.xlsx"
        self.conceptos_path = self.root / "CONCEPTOS.xlsx"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _matching_pair(self) -> None:
        _write_conceptos(
            self.conceptos_path,
            [
                {
                    CONCEPTOS_COLUMN: "PPA_[C_T]",
                    STANDARD_COLUMN: "PPA_[C_T]",
                    GROUP_COLUMN: "PPA",
                },
                {
                    CONCEPTOS_COLUMN: "LEGACY_ONLY",
                    STANDARD_COLUMN: "",
                    GROUP_COLUMN: "",
                },
            ],
        )
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "PPA_[C_T]",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )

    def test_skips_write_when_semantically_equal(self) -> None:
        self._matching_pair()
        before_sha = _file_sha256(self.conceptos_path)
        before_size = self.conceptos_path.stat().st_size
        before_mtime_ns = self.conceptos_path.stat().st_mtime_ns

        with patch.object(pd.DataFrame, "to_excel") as mocked_excel:
            result = sync_conceptos_from_admin(
                admin_path=self.admin_path,
                conceptos_path=self.conceptos_path,
            )

        mocked_excel.assert_not_called()
        self.assertFalse(result.changed)
        self.assertFalse(result.written)
        self.assertEqual(result.added, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(result.legacy_preserved, 1)
        self.assertEqual(_file_sha256(self.conceptos_path), before_sha)
        self.assertEqual(self.conceptos_path.stat().st_size, before_size)
        self.assertEqual(self.conceptos_path.stat().st_mtime_ns, before_mtime_ns)
        self.assertEqual(_leftover_temps(self.root), [])

    def test_atomic_write_on_real_change_preserves_legacy(self) -> None:
        self._matching_pair()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "PPA_[C_T]",
                    "Grupo": "PPA",
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
            ],
        )
        captured: list[Path] = []
        real_replace = sync_os.replace

        def _spy_replace(src: str | Path, dst: str | Path) -> None:
            captured.append(Path(src))
            self.assertTrue(zipfile.is_zipfile(src))
            real_replace(src, dst)

        with patch.object(sync_os, "replace", side_effect=_spy_replace):
            result = sync_conceptos_from_admin(
                admin_path=self.admin_path,
                conceptos_path=self.conceptos_path,
            )

        self.assertTrue(result.changed)
        self.assertTrue(result.written)
        self.assertEqual(result.added, 1)
        self.assertEqual(result.legacy_preserved, 1)
        self.assertEqual(len(captured), 1)
        self.assertTrue(zipfile.is_zipfile(self.conceptos_path))
        frame = pd.read_excel(self.conceptos_path)
        self.assertIn("LEGACY_ONLY", frame[CONCEPTOS_COLUMN].tolist())
        self.assertIn("COMB[DCAR]", frame[CONCEPTOS_COLUMN].tolist())
        self.assertEqual(_leftover_temps(self.root), [])

    def test_missing_destination_uses_temp_and_replace(self) -> None:
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "EDP_[",
                    "Concepto estándar": "EDP_[",
                    "Grupo": "EDP",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        self.assertFalse(self.conceptos_path.exists())
        captured: list[Path] = []
        real_replace = sync_os.replace

        def _spy_replace(src: str | Path, dst: str | Path) -> None:
            src_path = Path(src)
            captured.append(src_path)
            self.assertTrue(src_path.is_file())
            self.assertTrue(zipfile.is_zipfile(src_path))
            real_replace(src, dst)

        with patch.object(sync_os, "replace", side_effect=_spy_replace):
            result = sync_conceptos_from_admin(
                admin_path=self.admin_path,
                conceptos_path=self.conceptos_path,
            )

        self.assertTrue(result.written)
        self.assertTrue(self.conceptos_path.exists())
        self.assertEqual(len(captured), 1)
        self.assertTrue(zipfile.is_zipfile(self.conceptos_path))
        self.assertEqual(_leftover_temps(self.root), [])

    def test_to_excel_failure_preserves_destination(self) -> None:
        self._matching_pair()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "CHANGED",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        before_sha = _file_sha256(self.conceptos_path)

        with patch.object(
            pd.DataFrame,
            "to_excel",
            side_effect=OSError("to_excel boom"),
        ):
            with self.assertRaises(OSError):
                sync_conceptos_from_admin(
                    admin_path=self.admin_path,
                    conceptos_path=self.conceptos_path,
                )

        self.assertEqual(_file_sha256(self.conceptos_path), before_sha)
        self.assertEqual(_leftover_temps(self.root), [])

    def test_validation_failure_preserves_destination(self) -> None:
        self._matching_pair()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "CHANGED",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        before_sha = _file_sha256(self.conceptos_path)

        with patch(
            "src.services.conceptos_sync_service.zipfile.is_zipfile",
            return_value=False,
        ):
            with self.assertRaises(ValueError):
                sync_conceptos_from_admin(
                    admin_path=self.admin_path,
                    conceptos_path=self.conceptos_path,
                )

        self.assertEqual(_file_sha256(self.conceptos_path), before_sha)
        self.assertEqual(_leftover_temps(self.root), [])

    def test_replace_failure_preserves_destination(self) -> None:
        self._matching_pair()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "CHANGED",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        before_sha = _file_sha256(self.conceptos_path)

        with patch.object(
            sync_os,
            "replace",
            side_effect=OSError("replace boom"),
        ):
            with self.assertRaises(OSError):
                sync_conceptos_from_admin(
                    admin_path=self.admin_path,
                    conceptos_path=self.conceptos_path,
                )

        self.assertEqual(_file_sha256(self.conceptos_path), before_sha)
        self.assertEqual(_leftover_temps(self.root), [])

    def test_temp_path_same_folder_unique_xlsx_suffix(self) -> None:
        first = _temp_xlsx_path(self.conceptos_path)
        second = _temp_xlsx_path(self.conceptos_path)
        self.assertEqual(first.parent, self.conceptos_path.parent)
        self.assertTrue(first.name.endswith(".tmp.xlsx"))
        self.assertTrue(second.name.endswith(".tmp.xlsx"))
        self.assertNotEqual(first.name, second.name)
        self.assertFalse(first.name.endswith(".xlsx.tmp"))
        self.assertNotEqual(first.name, "CONCEPTOS.xlsx.tmp")

        self._matching_pair()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "CHANGED",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        captured: list[Path] = []
        real_replace = sync_os.replace

        def _spy_replace(src: str | Path, dst: str | Path) -> None:
            captured.append(Path(src))
            real_replace(src, dst)

        with patch.object(sync_os, "replace", side_effect=_spy_replace):
            sync_conceptos_from_admin(
                admin_path=self.admin_path,
                conceptos_path=self.conceptos_path,
            )

        self.assertEqual(len(captured), 1)
        temp = captured[0]
        self.assertEqual(temp.parent, self.conceptos_path.parent)
        self.assertTrue(temp.name.endswith(".tmp.xlsx"))
        self.assertNotEqual(temp.name, self.conceptos_path.name)


class ConceptosConcurrentGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.admin_path = self.root / "CONCEPTOS_ADMIN.xlsx"
        self.conceptos_path = self.root / "CONCEPTOS.xlsx"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _matching_pair(self) -> None:
        _write_conceptos(
            self.conceptos_path,
            [
                {
                    CONCEPTOS_COLUMN: "PPA_[C_T]",
                    STANDARD_COLUMN: "PPA_[C_T]",
                    GROUP_COLUMN: "PPA",
                },
                {
                    CONCEPTOS_COLUMN: "LEGACY_ONLY",
                    STANDARD_COLUMN: "",
                    GROUP_COLUMN: "",
                },
            ],
        )
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "PPA_[C_T]",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )

    def _admin_forces_write(self) -> None:
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "CHANGED",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )

    def _write_third_party(self, marker: str = "THIRD_[PTY]") -> str:
        _write_conceptos(
            self.conceptos_path,
            [
                {
                    CONCEPTOS_COLUMN: marker,
                    STANDARD_COLUMN: "TP",
                    GROUP_COLUMN: "X",
                }
            ],
        )
        return _file_sha256(self.conceptos_path)

    def _assert_no_temps_or_state(self) -> None:
        self.assertEqual(_leftover_temps(self.root), [])
        leftovers = sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_file() and path.name.startswith("last_")
        )
        self.assertEqual(leftovers, [])

    def test_a_mid_read_disappearance_is_concurrent(self) -> None:
        third_party_sha = self._write_third_party()
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "PPA_[C_T]",
                    "Concepto estándar": "PPA_[C_T]",
                    "Grupo": "PPA",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        original_open = Path.open

        class _VanishingHandle:
            def read(self, *args, **kwargs):
                raise FileNotFoundError("vanished during read")

            def close(self) -> None:
                return None

        def _selective_open(path_self, mode="r", *args, **kwargs):
            if (
                Path(path_self).resolve() == self.conceptos_path.resolve()
                and "b" in str(mode)
            ):
                return _VanishingHandle()
            return original_open(path_self, mode, *args, **kwargs)

        with patch.object(Path, "open", _selective_open):
            with patch.object(sync_os, "replace") as mocked_replace:
                with self.assertRaises(ConceptosConcurrentModificationError):
                    sync_conceptos_from_admin(
                        admin_path=self.admin_path,
                        conceptos_path=self.conceptos_path,
                    )
                mocked_replace.assert_not_called()

        self.assertTrue(self.conceptos_path.is_file())
        self.assertEqual(_file_sha256(self.conceptos_path), third_party_sha)
        self._assert_no_temps_or_state()

    def test_b_destination_changed_before_replace(self) -> None:
        self._matching_pair()
        self._admin_forces_write()
        real_fsync = css._fsync_closed_file
        captured: dict[str, str] = {}

        def _mutate_then_fsync(path: Path) -> None:
            captured["sha"] = self._write_third_party("THIRD_[CHG]")
            real_fsync(path)

        with patch.object(css, "_fsync_closed_file", side_effect=_mutate_then_fsync):
            with patch.object(sync_os, "replace") as mocked_replace:
                with self.assertRaises(ConceptosConcurrentModificationError):
                    sync_conceptos_from_admin(
                        admin_path=self.admin_path,
                        conceptos_path=self.conceptos_path,
                    )
                mocked_replace.assert_not_called()

        frame = pd.read_excel(self.conceptos_path)
        self.assertEqual(frame.iloc[0][CONCEPTOS_COLUMN], "THIRD_[CHG]")
        self.assertEqual(_file_sha256(self.conceptos_path), captured["sha"])
        self._assert_no_temps_or_state()

    def test_c_destination_deleted_before_replace(self) -> None:
        self._matching_pair()
        self._admin_forces_write()
        real_fsync = css._fsync_closed_file

        def _unlink_then_fsync(path: Path) -> None:
            self.conceptos_path.unlink()
            real_fsync(path)

        with patch.object(css, "_fsync_closed_file", side_effect=_unlink_then_fsync):
            with patch.object(sync_os, "replace") as mocked_replace:
                with self.assertRaises(ConceptosConcurrentModificationError):
                    sync_conceptos_from_admin(
                        admin_path=self.admin_path,
                        conceptos_path=self.conceptos_path,
                    )
                mocked_replace.assert_not_called()

        self.assertFalse(self.conceptos_path.exists())
        self._assert_no_temps_or_state()

    def test_d_missing_destination_appears_before_replace(self) -> None:
        _write_admin(
            self.admin_path,
            [
                {
                    "Concepto encontrado": "EDP_[",
                    "Concepto estándar": "EDP_[",
                    "Grupo": "EDP",
                    "Tipo": "NO_COM",
                    "Activo": "SI",
                },
            ],
        )
        self.assertFalse(self.conceptos_path.exists())
        real_fsync = css._fsync_closed_file
        captured: dict[str, str] = {}

        def _appear_then_fsync(path: Path) -> None:
            captured["sha"] = self._write_third_party("THIRD_[NEW]")
            real_fsync(path)

        with patch.object(css, "_fsync_closed_file", side_effect=_appear_then_fsync):
            with patch.object(sync_os, "replace") as mocked_replace:
                with self.assertRaises(ConceptosConcurrentModificationError):
                    sync_conceptos_from_admin(
                        admin_path=self.admin_path,
                        conceptos_path=self.conceptos_path,
                    )
                mocked_replace.assert_not_called()

        self.assertTrue(self.conceptos_path.is_file())
        frame = pd.read_excel(self.conceptos_path)
        self.assertEqual(frame.iloc[0][CONCEPTOS_COLUMN], "THIRD_[NEW]")
        self.assertEqual(_file_sha256(self.conceptos_path), captured["sha"])
        self._assert_no_temps_or_state()

    def test_e_stable_destination_replace_succeeds(self) -> None:
        self._matching_pair()
        self._admin_forces_write()
        result = sync_conceptos_from_admin(
            admin_path=self.admin_path,
            conceptos_path=self.conceptos_path,
        )
        self.assertTrue(result.written)
        self.assertTrue(result.changed)
        self.assertTrue(zipfile.is_zipfile(self.conceptos_path))
        frame = pd.read_excel(self.conceptos_path)
        self.assertEqual(
            frame.loc[frame[CONCEPTOS_COLUMN] == "PPA_[C_T]", STANDARD_COLUMN].iloc[0],
            "CHANGED",
        )
        self._assert_no_temps_or_state()

    def test_f_semantic_skip_does_not_write(self) -> None:
        self._matching_pair()
        before_sha = _file_sha256(self.conceptos_path)
        before_mtime_ns = self.conceptos_path.stat().st_mtime_ns
        with patch.object(pd.DataFrame, "to_excel") as mocked_excel:
            with patch.object(sync_os, "replace") as mocked_replace:
                result = sync_conceptos_from_admin(
                    admin_path=self.admin_path,
                    conceptos_path=self.conceptos_path,
                )
        mocked_excel.assert_not_called()
        mocked_replace.assert_not_called()
        self.assertFalse(result.written)
        self.assertFalse(result.changed)
        self.assertEqual(_file_sha256(self.conceptos_path), before_sha)
        self.assertEqual(self.conceptos_path.stat().st_mtime_ns, before_mtime_ns)
        self._assert_no_temps_or_state()


if __name__ == "__main__":
    unittest.main()
