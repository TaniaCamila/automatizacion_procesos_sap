"""Tests mínimos para scripts/reanudar_desde_dinamicas.py (sin Outlook/pipeline real)."""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.modules.dinamicas_finales.module import (
    FINAL_SHEET_ORDER,
    HIERARCHICAL_SHEETS,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reanudar_desde_dinamicas.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("reanudar_desde_dinamicas", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


MOD = _load_mod()


def _canonical_sheet_order() -> list[str]:
    return list(FINAL_SHEET_ORDER) + [f"DATOS_{name}"[:31] for name in HIERARCHICAL_SHEETS]


def _write_business_xlsx(
    path: Path,
    *,
    sheets: list[str] | None = None,
    cell_value: str = "100",
    pivot_cache: str = "cache-v1",
    pivot_table: str = "pivot-v1",
    styles: str = "styles-v1",
    shared: str = "shared-v1",
    table_xml: str = "table-v1",
    doc_props: str = "docProps-v1",
    custom_xml: str = "customXml-v1",
) -> None:
    """OOXML mínimo con 16 hojas y partes de negocio comparables."""

    names = list(sheets if sheets is not None else _canonical_sheet_order())
    sheet_elems = "".join(
        f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(names, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_elems}</sheets></workbook>"
    ).encode("utf-8")

    def sheet_xml(value: str) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData><row r="1"><c r="A1"><v>{value}</v></c></row></sheetData>'
            "</worksheet>"
        ).encode("utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/sharedStrings.xml", f"<sst>{shared}</sst>")
        zf.writestr("xl/styles.xml", f"<styleSheet>{styles}</styleSheet>")
        for idx, _name in enumerate(names, start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml(cell_value))
        zf.writestr("xl/pivotCache/pivotCacheDefinition1.xml", f"<pcd>{pivot_cache}</pcd>")
        zf.writestr("xl/pivotTables/pivotTable1.xml", f"<pt>{pivot_table}</pt>")
        zf.writestr("xl/tables/table1.xml", f"<table>{table_xml}</table>")
        # Metadatos OneDrive/SharePoint: no deben afectar equivalencia.
        zf.writestr("docProps/core.xml", f"<core>{doc_props}</core>")
        zf.writestr("docProps/app.xml", f"<app>{doc_props}-app</app>")
        zf.writestr("customXml/item1.xml", f"<item>{custom_xml}</item>")
        zf.writestr(
            "customXml/itemProps1.xml",
            f'<ds:datastoreItem xmlns:ds="http://schemas.openxmlformats.org/officeDocument/2006/customXml">'
            f"<ds:schemaRefs/><guid>{custom_xml}-guid</guid></ds:datastoreItem>",
        )


def _fake_decision(**overrides):
    base = SimpleNamespace(
        status=MOD.DECISION_CHANGED,
        message="changed",
        source_fbl1n_sha256="alias-abc",
        identity_version="fbl1n-combined-v2",
        historical_file_sha256="hfile",
        historical_semantic_sha256="hsem",
        future_file_sha256="ffile",
        future_semantic_sha256="fsem",
        combined_source_sha256="alias-abc",
        combined_semantic_sha256="csem",
        future_valid_rows=1,
        future_invalid_rows=0,
        latest_compensation_date="2026-08-31",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _plan(tmp: Path, **overrides) -> MOD.ResumePlan:
    matriz = tmp / "MATRIZ.xlsx"
    dinamicas = tmp / "DIN.xlsx"
    actual = tmp / "ACTUAL.xlsx"
    for path in (matriz, dinamicas, actual):
        path.write_bytes(b"PK\x03\x04fake")
    base = MOD.ResumePlan(
        matriz=matriz,
        dinamicas=dinamicas,
        actual=actual,
        cutoff=date(2026, 8, 31),
        decision_status=MOD.DECISION_CHANGED,
        alias="alias-abc",
        historical_fp={"sha256": "hfile", "size": 1},
        decision=_fake_decision(),
        last_state={"sha256": "old", "size": 1},
        fbl_rows=92056,
        matrix_rows=92056,
        months=["2026-08"],
        month_labels=["Agosto 2026"],
        latest_compensation_date="2026-08-31",
        dinamicas_sha256="dinsha",
        actual_sha256="actsha-different",
        actual_matches_dinamicas=True,
        state_cas={
            "last_fbl1n_state.json": "",
            "last_publish_state.json": "",
            "last_mail_state.json": "",
        },
        published_cas={
            MOD.DINAMICAS_DEST_NAME: "",
            MOD.PAGO_ME_DEST_NAME: "",
        },
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestReanudarDesdeDinamicas(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_reanudar")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())

    def test_dry_run_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            tracked: list[Path] = []

            real_write_text = Path.write_text
            real_write_bytes = Path.write_bytes
            real_mkdir = Path.mkdir
            real_open = Path.open
            real_replace = getattr(__import__("os"), "replace")

            def track_write_text(self, *a, **k):
                tracked.append(Path(self))
                return real_write_text(self, *a, **k)

            def track_write_bytes(self, *a, **k):
                tracked.append(Path(self))
                return real_write_bytes(self, *a, **k)

            def track_mkdir(self, *a, **k):
                tracked.append(Path(self))
                return real_mkdir(self, *a, **k)

            def track_open(self, mode="r", *a, **k):
                if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
                    tracked.append(Path(self))
                return real_open(self, mode, *a, **k)

            def track_replace(src, dst, *a, **k):
                tracked.append(Path(dst))
                return real_replace(src, dst, *a, **k)

            plan = _plan(tmp)
            with (
                patch.object(MOD, "build_plan", return_value=plan) as bp,
                patch.object(Path, "write_text", track_write_text),
                patch.object(Path, "write_bytes", track_write_bytes),
                patch.object(Path, "mkdir", track_mkdir),
                patch.object(Path, "open", track_open),
                patch("os.replace", track_replace),
            ):
                code = MOD.main(
                    ["--matriz", str(plan.matriz), "--dinamicas", str(plan.dinamicas)]
                )
            self.assertEqual(code, 0)
            bp.assert_called_once()
            self.assertEqual(tracked, [], f"dry-run escribió: {tracked}")

    def test_happy_path_apply_mocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            work = tmp / "work"
            state = tmp / "state"
            pub = tmp / "pub"
            state.mkdir()
            pub.mkdir()
            plan = _plan(tmp)
            fake_publish = SimpleNamespace(
                status=MOD.PUBLISH_SUCCEEDED, error=None
            )
            fake_mail = SimpleNamespace(
                status=MOD.MAIL_PENDING,
                executed=False,
                mail_subject="Fecha de compensación 31/08/2026",
            )
            lock = MagicMock()
            with (
                patch.object(MOD, "precheck_runtime"),
                patch.object(MOD, "_require_config", return_value=date(2026, 8, 31)),
                patch.object(MOD, "_verify_cas"),
                patch.object(MOD, "resolve_state_dir", return_value=state),
                patch.object(MOD, "PUBLICATION_DIR", pub),
                patch.object(MOD, "PipelineLock", return_value=lock),
                patch.object(MOD, "run_publish", return_value=fake_publish) as rp,
                patch.object(MOD, "build_combined_state_payload", return_value={"ok": 1}) as bcs,
                patch.object(MOD, "save_state") as ss,
                patch.object(MOD, "run_mail_stage", return_value=fake_mail) as rm,
                patch.object(
                    MOD,
                    "load_publish_state",
                    return_value={"publish_status": MOD.PUBLISH_SUCCEEDED},
                ),
                patch.object(MOD, "sha256_file", return_value="x" * 64),
            ):
                after = MOD.apply_plan(plan, logger=self.logger, work_dir=work)
            self.assertEqual(after["publish_status"], MOD.PUBLISH_SUCCEEDED)
            self.assertEqual(after["mail_status"], MOD.MAIL_PENDING)
            rp.assert_called_once()
            bcs.assert_called_once()
            ss.assert_called_once()
            rm.assert_called_once()
            self.assertTrue((work / "MANIFEST_BEFORE.json").is_file())
            self.assertTrue((work / "MANIFEST_AFTER.json").is_file())
            lock.acquire.assert_called_once()
            lock.release.assert_called_once()

    def test_validation_failure_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            wrote: list[str] = []

            def boom_save(*_a, **_k):
                wrote.append("save_state")

            with (
                patch.object(MOD, "_require_config", return_value=date(2026, 8, 31)),
                patch.object(MOD, "precheck_runtime"),
                patch.object(MOD, "load_state", return_value=None),
                patch.object(MOD, "save_state", side_effect=boom_save),
                patch.object(MOD, "run_publish", side_effect=AssertionError("no publish")),
            ):
                with self.assertRaises(MOD.ResumeAborted):
                    MOD.build_plan(
                        matriz=tmp / "m.xlsx",
                        dinamicas=tmp / "d.xlsx",
                        logger=self.logger,
                        skip_runtime_precheck=True,
                    )
            self.assertEqual(wrote, [])

    def test_post_write_failure_triggers_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            work = tmp / "work"
            state = tmp / "state"
            pub = tmp / "pub"
            state.mkdir()
            pub.mkdir()
            fbl = state / "last_fbl1n_state.json"
            fbl.write_text('{"v":1}', encoding="utf-8")
            din = pub / MOD.DINAMICAS_DEST_NAME
            din.write_bytes(b"old-din")
            plan = _plan(
                tmp,
                state_cas={
                    "last_fbl1n_state.json": MOD.sha256_file(fbl),
                    "last_publish_state.json": "",
                    "last_mail_state.json": "",
                },
                published_cas={
                    MOD.DINAMICAS_DEST_NAME: MOD.sha256_file(din),
                    MOD.PAGO_ME_DEST_NAME: "",
                },
            )
            lock = MagicMock()

            def publish_side_effect(*_a, **_k):
                din.write_bytes(b"new-din-should-rollback")
                return SimpleNamespace(status=MOD.PUBLISH_SUCCEEDED, error=None)

            with (
                patch.object(MOD, "precheck_runtime"),
                patch.object(MOD, "_require_config", return_value=date(2026, 8, 31)),
                patch.object(MOD, "resolve_state_dir", return_value=state),
                patch.object(MOD, "PUBLICATION_DIR", pub),
                patch.object(MOD, "PipelineLock", return_value=lock),
                patch.object(MOD, "run_publish", side_effect=publish_side_effect),
                patch.object(
                    MOD,
                    "build_combined_state_payload",
                    return_value={"ok": 1},
                ),
                patch.object(
                    MOD, "save_state", side_effect=RuntimeError("boom-after-publish")
                ),
                patch.object(MOD, "run_mail_stage", side_effect=AssertionError("no mail")),
            ):
                with self.assertRaises(MOD.ResumeAborted) as ctx:
                    MOD.apply_plan(
                        plan,
                        logger=self.logger,
                        work_dir=work,
                        skip_runtime_precheck=True,
                    )
            self.assertIn("rollback", str(ctx.exception).lower())
            self.assertEqual(fbl.read_text(encoding="utf-8"), '{"v":1}')
            self.assertEqual(din.read_bytes(), b"old-din")
            self.assertIn("boom-after-publish", str(ctx.exception))

    def test_mail_auto_send_true_aborts(self) -> None:
        with patch.object(MOD, "MAIL_AUTO_SEND", True):
            with self.assertRaises(MOD.ResumeAborted) as ctx:
                MOD._require_config()
            self.assertIn("MAIL_AUTO_SEND", str(ctx.exception))

    def test_no_outlook_instantiation_on_mail_pending_path(self) -> None:
        """Con AUTO_SEND=false, run_mail_stage no debe tocar win32com/Outlook."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            work = tmp / "work"
            state = tmp / "state"
            pub = tmp / "pub"
            state.mkdir()
            pub.mkdir()
            plan = _plan(tmp)
            lock = MagicMock()
            outlook_calls: list[str] = []

            def guard_dispatch(*_a, **_k):
                outlook_calls.append("Dispatch")
                raise AssertionError("Outlook no debe instanciarse")

            fake_publish = SimpleNamespace(status=MOD.PUBLISH_SUCCEEDED, error=None)

            from src.modules.actualizacion_automatica import mail as mail_mod

            with (
                patch.object(MOD, "precheck_runtime"),
                patch.object(MOD, "_require_config", return_value=date(2026, 8, 31)),
                patch.object(MOD, "_verify_cas"),
                patch.object(MOD, "resolve_state_dir", return_value=state),
                patch.object(MOD, "PUBLICATION_DIR", pub),
                patch.object(MOD, "PipelineLock", return_value=lock),
                patch.object(MOD, "run_publish", return_value=fake_publish),
                patch.object(MOD, "build_combined_state_payload", return_value={"ok": 1}),
                patch.object(MOD, "save_state"),
                patch.object(
                    MOD,
                    "load_publish_state",
                    return_value={"publish_status": MOD.PUBLISH_SUCCEEDED},
                ),
                patch.object(mail_mod, "MAIL_AUTO_SEND", False),
                patch.object(
                    mail_mod,
                    "_cfg",
                    return_value=SimpleNamespace(
                        MAIL_AUTO_SEND=False,
                        MAIL_TO="a@test.com",
                        MAIL_CC="",
                        MAIL_BCC="",
                        MAIL_SHAREPOINT_LINK="https://example.test/sp",
                        MAIL_POWERBI_LINK="",
                    ),
                ),
                patch.object(mail_mod, "needs_mail_retry", return_value=True),
                patch.object(mail_mod, "write_mail_state"),
                patch("win32com.client.Dispatch", side_effect=guard_dispatch),
            ):
                with patch.object(MOD, "run_mail_stage", mail_mod.run_mail_stage):
                    after = MOD.apply_plan(
                        plan,
                        logger=self.logger,
                        work_dir=work,
                        skip_runtime_precheck=True,
                    )
            self.assertEqual(after["mail_status"], MOD.MAIL_PENDING)
            self.assertEqual(outlook_calls, [])

    def test_ooxml_same_business_diff_onedrive_meta_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            left = tmp / "actual.xlsx"
            right = tmp / "dinamicas.xlsx"
            _write_business_xlsx(
                left, doc_props="onedrive-A", custom_xml="guid-AAAA"
            )
            _write_business_xlsx(
                right, doc_props="onedrive-B", custom_xml="guid-BBBB"
            )
            self.assertNotEqual(MOD.sha256_file(left), MOD.sha256_file(right))
            MOD.assert_business_ooxml_equivalent(
                left, right, logger=self.logger
            )

    def test_ooxml_different_cell_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            left = tmp / "actual.xlsx"
            right = tmp / "dinamicas.xlsx"
            _write_business_xlsx(left, cell_value="100")
            _write_business_xlsx(right, cell_value="101")
            with self.assertRaises(MOD.ResumeAborted) as ctx:
                MOD.assert_business_ooxml_equivalent(left, right, logger=self.logger)
            self.assertIn("worksheets", str(ctx.exception).lower())

    def test_ooxml_different_pivot_cache_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            left = tmp / "actual.xlsx"
            right = tmp / "dinamicas.xlsx"
            _write_business_xlsx(left, pivot_cache="cache-A")
            _write_business_xlsx(right, pivot_cache="cache-B")
            with self.assertRaises(MOD.ResumeAborted) as ctx:
                MOD.assert_business_ooxml_equivalent(left, right, logger=self.logger)
            self.assertIn("pivotcache", str(ctx.exception).lower())

    def test_apply_allows_non_pipeline_python(self) -> None:
        """IDE/LSP python no debe abortar --apply (fallo visto en Operador)."""
        with tempfile.TemporaryDirectory() as td:
            with (
                patch.object(MOD, "resolve_state_dir", return_value=Path(td)),
                patch.object(
                    MOD,
                    "_count_blocking_processes",
                    return_value=(
                        {
                            "EXCEL": 0,
                            "saplogon": 0,
                            "cscript": 0,
                            "wscript": 0,
                            "PBIDesktop": 0,
                            "python_pipeline": 0,
                        },
                        1,
                    ),
                ),
            ):
                MOD.precheck_runtime(apply=True, logger=self.logger)

    def test_apply_blocks_pipeline_python(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with (
                patch.object(MOD, "resolve_state_dir", return_value=Path(td)),
                patch.object(
                    MOD,
                    "_count_blocking_processes",
                    return_value=(
                        {
                            "EXCEL": 0,
                            "saplogon": 0,
                            "cscript": 0,
                            "wscript": 0,
                            "PBIDesktop": 0,
                            "python_pipeline": 1,
                        },
                        0,
                    ),
                ),
            ):
                with self.assertRaises(MOD.ResumeAborted) as ctx:
                    MOD.precheck_runtime(apply=True, logger=self.logger)
                self.assertIn("pipeline", str(ctx.exception).lower())

    def test_ooxml_sheet_added_or_removed_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base = _canonical_sheet_order()
            left = tmp / "actual.xlsx"
            right_add = tmp / "dinamicas_add.xlsx"
            right_drop = tmp / "dinamicas_drop.xlsx"
            _write_business_xlsx(left, sheets=base)
            _write_business_xlsx(right_add, sheets=base + ["EXTRA_SHEET"])
            with self.assertRaises(MOD.ResumeAborted) as ctx_add:
                MOD.assert_business_ooxml_equivalent(
                    left, right_add, logger=self.logger
                )
            self.assertIn("hojas", str(ctx_add.exception).lower())

            _write_business_xlsx(right_drop, sheets=base[:-1])
            with self.assertRaises(MOD.ResumeAborted) as ctx_drop:
                MOD.assert_business_ooxml_equivalent(
                    left, right_drop, logger=self.logger
                )
            self.assertIn("hojas", str(ctx_drop.exception).lower())


if __name__ == "__main__":
    unittest.main()
