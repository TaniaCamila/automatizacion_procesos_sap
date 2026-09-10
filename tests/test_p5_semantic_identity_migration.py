"""P5B: identidad semántica v2 y utilidad de migración (tempfile)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

from src.modules.actualizacion_automatica.mail import mail_may_be_composed
from src.modules.fbl1n_fuentes.detection import (
    DECISION_CHANGED,
    DECISION_FAILED,
    DECISION_HISTORICAL_ANOMALY,
    DECISION_UNCHANGED,
    IDENTITY_VERSION_V2,
    MIGRATION_REQUIRED_MESSAGE,
    SOURCE_MODE_PLUS_FUTURE,
    STATE_SCHEMA_VERSION,
    plan_source_detection,
)
from src.modules.fbl1n_fuentes.dry_run import run_future_orchestrator_dry
from src.modules.fbl1n_fuentes.module import (
    COMBINED_IDENTITY_VERSION,
    COMBINED_IDENTITY_VERSION_V2,
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    SOCIEDAD_COL,
    combined_semantic_sha256,
    combined_source_sha256,
    combined_source_sha256_v1,
    semantic_fbl1n_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
UTIL_PATH = ROOT / "scripts" / "migrar_identidad_semantica_fbl1n.py"
PROD_STATE = ROOT / "state" / "last_fbl1n_state.json"
PROD_PUBLISH = ROOT / "state" / "last_publish_state.json"
PROD_MAIL = ROOT / "state" / "last_mail_state.json"


def _load_util():
    spec = importlib.util.spec_from_file_location(
        "migrar_identidad_semantica_fbl1n", UTIL_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


UTIL = _load_util()


def _blank_row(**overrides: object) -> dict[str, object]:
    row = {column: None for column in EXPECTED_COLUMNS}
    row.update(overrides)
    return row


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(EXPECTED_COLUMNS))


def _hist(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL44",
        FECHA_COMP_COL: date(2026, 1, 15),
        "Referencia": "H1",
        "Importe en moneda doc.": 100,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _fut(**overrides: object) -> dict[str, object]:
    payload = {
        SOCIEDAD_COL: "CL45",
        FECHA_COMP_COL: date(2026, 9, 2),
        "Referencia": "F1",
        "Importe en moneda doc.": 200,
    }
    payload.update(overrides)
    return _blank_row(**payload)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _sig(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha_file(path),
    }


def _write_xlsx(path: Path, frame: pd.DataFrame, sheet: str = "Sheet1") -> None:
    frame.to_excel(path, index=False, sheet_name=sheet)


def _pad_xlsx(source: Path, dest: Path) -> None:
    dest.write_bytes(source.read_bytes())
    with zipfile.ZipFile(dest, "a") as handle:
        handle.writestr("_p5_meta_pad.txt", f"pad-{datetime.now().isoformat()}")


def _write_actual_16(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "S01"
    for index in range(2, 17):
        workbook.create_sheet(f"S{index:02d}")
    workbook.save(path)


def _fp(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": path.name,
        "size": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha_file(path),
    }


class SemanticIdentityContractTests(unittest.TestCase):
    def test_v1_domain_preserved_and_v2_uses_semantic_pair(self) -> None:
        hist = semantic_fbl1n_fingerprint(_frame(_hist()))
        fut = semantic_fbl1n_fingerprint(_frame(_fut()))
        v1 = combined_source_sha256("phys-hist", fut.sha256)
        v1_alias = combined_source_sha256_v1("phys-hist", fut.sha256)
        v2 = combined_semantic_sha256(hist.sha256, fut.sha256)
        self.assertEqual(v1, v1_alias)
        self.assertNotEqual(v1, v2)
        self.assertEqual(COMBINED_IDENTITY_VERSION, "fbl1n-combined-v1")
        self.assertEqual(COMBINED_IDENTITY_VERSION_V2, "fbl1n-combined-v2")
        self.assertEqual(IDENTITY_VERSION_V2, "fbl1n-combined-v2")


class SemanticDetectionP5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.hist_df = _frame(_hist())
        self.future_df = _frame(_fut())
        self.hist_sem = semantic_fbl1n_fingerprint(self.hist_df)
        self.fut_sem = semantic_fbl1n_fingerprint(self.future_df)
        self.combined_v1 = combined_source_sha256("hist-phys", self.fut_sem.sha256)
        self.combined_v2 = combined_semantic_sha256(
            self.hist_sem.sha256, self.fut_sem.sha256
        )
        self.last_v2 = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "identity_version": IDENTITY_VERSION_V2,
            "historical_file_sha256": "hist-phys",
            "historical_semantic_sha256": self.hist_sem.sha256,
            "sha256": "hist-phys",
            "size": 10,
            "future_semantic_sha256": self.fut_sem.sha256,
            "combined_source_sha256": self.combined_v1,
            "combined_semantic_sha256": self.combined_v2,
            "source_fbl1n_sha256": self.combined_v1,
        }

    def test_repacked_historical_is_unchanged(self) -> None:
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-repack", "size": 99},
            last=self.last_v2,
            historical_df=self.hist_df,
            future_df=self.future_df,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.source_fbl1n_sha256, self.combined_v1)
        self.assertEqual(decision.combined_source_sha256, self.combined_v1)

    def test_different_historical_row_is_changed(self) -> None:
        other = _frame(_hist(Referencia="H-other"))
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-phys", "size": 10},
            last=self.last_v2,
            historical_df=other,
            future_df=self.future_df,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertNotEqual(decision.combined_semantic_sha256, self.combined_v2)

    def test_repacked_future_is_unchanged(self) -> None:
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-phys", "size": 10},
            last=self.last_v2,
            historical_df=self.hist_df,
            future_df=self.future_df,
            future_file_sha256="fut-repack",
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_UNCHANGED)
        self.assertEqual(decision.source_fbl1n_sha256, self.combined_v1)

    def test_new_future_row_is_changed(self) -> None:
        added = _frame(_fut(), _fut(Referencia="F-new"))
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-phys", "size": 10},
            last=self.last_v2,
            historical_df=self.hist_df,
            future_df=added,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_CHANGED)
        self.assertNotEqual(decision.combined_semantic_sha256, self.combined_v2)

    def test_missing_historical_column_is_failed(self) -> None:
        broken = self.hist_df.drop(columns=[SOCIEDAD_COL])
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-phys", "size": 10},
            last=self.last_v2,
            historical_df=broken,
            future_df=self.future_df,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_FAILED)
        self.assertIn("estructura incompatible", decision.message.lower())

    def test_combined_state_without_identity_version_requires_migration(self) -> None:
        last = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "historical_file_sha256": "hist-phys",
            "sha256": "hist-phys",
            "combined_source_sha256": self.combined_v1,
        }
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp={"sha256": "hist-repack", "size": 99},
            last=last,
            historical_df=self.hist_df,
            future_df=self.future_df,
            compensation_cutoff=date(2026, 12, 31),
        )
        self.assertEqual(decision.status, DECISION_HISTORICAL_ANOMALY)
        self.assertEqual(decision.message, MIGRATION_REQUIRED_MESSAGE)

    def test_unchanged_succeeded_pending_skips_publish_mail_outlook(self) -> None:
        self.assertFalse(
            mail_may_be_composed(
                future_enabled=True,
                decision=DECISION_UNCHANGED,
                publish_ok=True,
            )
        )
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            hist = work / "FBL1N.xlsx"
            future = work / "FBL1N_FUTURO.xlsx"
            _write_xlsx(hist, self.hist_df)
            _write_xlsx(future, self.future_df)
            padded = work / "FBL1N_PADDED.xlsx"
            _pad_xlsx(hist, padded)
            self.assertNotEqual(_sha_file(hist), _sha_file(padded))
            last = {
                **self.last_v2,
                "historical_file_sha256": _sha_file(hist),
                "sha256": _sha_file(hist),
                "size": int(hist.stat().st_size),
            }
            with patch(
                "src.modules.fbl1n_fuentes.dry_run.assert_d6_work_dir",
                side_effect=lambda path: Path(path).resolve(),
            ):
                result = run_future_orchestrator_dry(
                    work_dir=work,
                    historical_path=padded,
                    future_path=future,
                    last=last,
                    historical_df=self.hist_df,
                    future_df=self.future_df,
                )
            self.assertEqual(result.decision, DECISION_UNCHANGED)
            self.assertEqual(result.counters.pipeline, 0)
            self.assertEqual(result.counters.publish, 0)
            self.assertEqual(result.counters.mail_compose, 0)
            self.assertEqual(result.counters.outlook_display, 0)
            self.assertEqual(result.counters.outlook_send, 0)


class MigrationUtilityP5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_mail = os.environ.get("MAIL_AUTO_SEND")
        os.environ["MAIL_AUTO_SEND"] = "false"
        self.hist_df = _frame(_hist())
        self.future_df = _frame(_fut())
        self.hist_sem = semantic_fbl1n_fingerprint(self.hist_df)
        self.fut_sem = semantic_fbl1n_fingerprint(self.future_df)

    def tearDown(self) -> None:
        if self._prev_mail is None:
            os.environ.pop("MAIL_AUTO_SEND", None)
        else:
            os.environ["MAIL_AUTO_SEND"] = self._prev_mail

    def _build_fixture(self, root: Path, *, repack_hist: bool = True) -> dict[str, Path]:
        hist = root / "FBL1N.xlsx"
        future = root / "FBL1N_FUTURO.xlsx"
        matriz = root / "MATRIZ.xlsx"
        output_actual = root / "ACTUAL_OUT.xlsx"
        published = root / "ACTUAL_PUB.xlsx"
        state_dir = root / "state"
        backup_dir = root / "backup"
        state_dir.mkdir()
        _write_xlsx(hist, self.hist_df)
        _write_xlsx(future, self.future_df)
        _write_xlsx(matriz, self.hist_df, sheet="MATRIZ_FBL1N")
        _write_actual_16(output_actual)
        published.write_bytes(output_actual.read_bytes())
        current_hist = hist
        if repack_hist:
            current_hist = root / "FBL1N_repack.xlsx"
            _pad_xlsx(hist, current_hist)
        hist_meta = _fp(hist)
        current_meta = _fp(current_hist)
        fut_meta = _fp(future)
        combined_v1 = combined_source_sha256_v1(
            str(hist_meta["sha256"]), self.fut_sem.sha256
        )
        last = {
            "schema_version": STATE_SCHEMA_VERSION,
            "source_mode": SOURCE_MODE_PLUS_FUTURE,
            "path": "FBL1N.xlsx",
            "sha256": hist_meta["sha256"],
            "size": hist_meta["size"],
            "mtime": hist_meta["mtime"],
            "historical_file_sha256": hist_meta["sha256"],
            "future_file_sha256": fut_meta["sha256"],
            "future_semantic_sha256": self.fut_sem.sha256,
            "combined_source_sha256": combined_v1,
            "source_fbl1n_sha256": combined_v1,
            "last_success_at": "2026-09-02T13:07:05",
            "started_at": "2026-09-02T13:00:00",
            "fbl1n_rows": 2,
            "matrix_rows": 1,
            "months": ["2026-09"],
            "matriz": "MATRIZ.xlsx",
            "dinamicas": "DIN.xlsx",
            "actual": "ACTUAL.xlsx",
            "log": "run.log",
        }
        publish = {
            "source_fbl1n_sha256": combined_v1,
            "publish_status": "Succeeded",
        }
        mail = {
            "source_fbl1n_sha256": combined_v1,
            "mail_status": "Pending",
        }
        fbl1n_state = state_dir / "last_fbl1n_state.json"
        publish_state = state_dir / "last_publish_state.json"
        mail_state = state_dir / "last_mail_state.json"
        fbl1n_state.write_text(json.dumps(last, indent=2), encoding="utf-8")
        publish_state.write_text(json.dumps(publish, indent=2), encoding="utf-8")
        mail_state.write_text(json.dumps(mail, indent=2), encoding="utf-8")
        return {
            "historical": current_hist,
            "original_historical": hist,
            "future": future,
            "matriz": matriz,
            "output_actual": output_actual,
            "published_actual": published,
            "state_dir": state_dir,
            "backup_dir": backup_dir,
            "fbl1n_state": fbl1n_state,
            "publish_state": publish_state,
            "mail_state": mail_state,
            "combined_v1": combined_v1,  # type: ignore[dict-item]
            "legacy_hist_sha": str(hist_meta["sha256"]),
            "current_hist_sha": str(current_meta["sha256"]),
        }

    def _cfg(
        self,
        fixture: dict[str, Path],
        *,
        apply: bool = False,
        rollback: bool = False,
    ) -> object:
        return UTIL.MigrationConfig(
            historical=fixture["historical"],
            future=fixture["future"],
            matriz=fixture["matriz"],
            output_actual=fixture["output_actual"],
            published_actual=fixture["published_actual"],
            state_dir=fixture["state_dir"],
            backup_dir=fixture["backup_dir"],
            expected_historical_semantic_sha256=self.hist_sem.sha256,
            expected_future_file_sha256=_sha_file(fixture["future"]),
            expected_future_semantic_sha256=self.fut_sem.sha256,
            expected_legacy_historical_file_sha256=str(fixture["legacy_hist_sha"]),
            expected_legacy_combined_source_sha256=str(fixture["combined_v1"]),
            matriz_expected_rows=1,
            apply=apply,
            rollback=rollback,
        )

    def _manifest(self, fixture: dict[str, Path]) -> dict[str, object]:
        path = fixture["backup_dir"] / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _known_tmps(self, fixture: dict[str, Path]) -> list[Path]:
        return [
            fixture["state_dir"] / "last_fbl1n_state.json.tmp",
            fixture["state_dir"] / "last_fbl1n_state.json.rollback.tmp",
            fixture["backup_dir"] / "manifest.json.tmp",
        ]

    def test_utility_without_apply_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            before = {
                name: _sig(fixture[name])
                for name in ("fbl1n_state", "publish_state", "mail_state")
            }
            result = UTIL.run(self._cfg(fixture, apply=False))
            self.assertTrue(result.ok)
            self.assertFalse(result.applied)
            self.assertFalse(fixture["backup_dir"].exists())
            for name, signature in before.items():
                self.assertEqual(_sig(fixture[name]), signature)
            for tmp in self._known_tmps(fixture):
                self.assertFalse(tmp.exists())

    def test_apply_and_rollback_flags_rejected_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            before = {
                name: _sig(fixture[name])
                for name in ("fbl1n_state", "publish_state", "mail_state")
            }
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(self._cfg(fixture, apply=True, rollback=True))
            self.assertIn("mutuamente excluyentes", str(raised.exception).lower())
            with self.assertRaises(SystemExit) as exited:
                UTIL.parse_args(
                    [
                        "--state-dir",
                        str(fixture["state_dir"]),
                        "--apply",
                        "--rollback",
                    ]
                )
            self.assertEqual(exited.exception.code, 2)
            self.assertFalse(fixture["backup_dir"].exists())
            for name, signature in before.items():
                self.assertEqual(_sig(fixture[name]), signature)

    def test_preexisting_backup_dir_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            fixture["backup_dir"].mkdir()
            (fixture["backup_dir"] / "stale.txt").write_text("old", encoding="utf-8")
            before = _sig(fixture["fbl1n_state"])
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(self._cfg(fixture, apply=True))
            self.assertIn("ya existe", str(raised.exception).lower())
            self.assertEqual(_sig(fixture["fbl1n_state"]), before)
            self.assertTrue((fixture["backup_dir"] / "stale.txt").is_file())
            self.assertFalse((fixture["backup_dir"] / "manifest.json").exists())

    def test_happy_path_only_fbl1n_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            publish_before = _sig(fixture["publish_state"])
            mail_before = _sig(fixture["mail_state"])
            fbl1n_before = _sig(fixture["fbl1n_state"])
            original = json.loads(
                fixture["fbl1n_state"].read_text(encoding="utf-8")
            )
            result = UTIL.run(self._cfg(fixture, apply=True))
            self.assertTrue(result.ok)
            self.assertTrue(result.applied)
            self.assertEqual(result.written, ["last_fbl1n_state.json"])
            fbl1n_after = json.loads(
                fixture["fbl1n_state"].read_text(encoding="utf-8")
            )
            self.assertNotEqual(_sig(fixture["fbl1n_state"]), fbl1n_before)
            self.assertEqual(_sig(fixture["publish_state"]), publish_before)
            self.assertEqual(_sig(fixture["mail_state"]), mail_before)
            self.assertEqual(fbl1n_after["identity_version"], IDENTITY_VERSION_V2)
            self.assertEqual(
                fbl1n_after["combined_source_sha256"], original["combined_source_sha256"]
            )
            self.assertEqual(
                fbl1n_after["source_fbl1n_sha256"], original["source_fbl1n_sha256"]
            )
            self.assertEqual(fbl1n_after["last_success_at"], original["last_success_at"])
            self.assertEqual(fbl1n_after["matriz"], original["matriz"])
            self.assertEqual(fbl1n_after["path"], original["path"])
            self.assertEqual(fbl1n_after["fbl1n_rows"], original["fbl1n_rows"])
            self.assertEqual(
                fbl1n_after["historical_file_sha256"], fixture["current_hist_sha"]
            )
            self.assertEqual(
                fbl1n_after["legacy_historical_file_sha256"],
                fixture["legacy_hist_sha"],
            )
            self.assertEqual(
                fbl1n_after["identity_migration"]["kind"], "semantic_identity_v2"
            )
            self.assertNotIn("identity_migration", json.loads(
                fixture["publish_state"].read_text(encoding="utf-8")
            ))
            self.assertNotIn("identity_migration", json.loads(
                fixture["mail_state"].read_text(encoding="utf-8")
            ))
            manifest = self._manifest(fixture)
            self.assertEqual(manifest["status"], "applied")
            self.assertEqual(manifest["fbl1n_sha256_before"], fbl1n_before["sha256"])
            self.assertEqual(manifest["fbl1n_sha256_after"], _sha_file(fixture["fbl1n_state"]))
            self.assertIsNotNone(manifest["applied_at"])
            self.assertIsNone(manifest["rolled_back_at"])
            uuid.UUID(str(manifest["migration_id"]))

    def test_publish_mail_keep_sha_and_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            publish_before = _sig(fixture["publish_state"])
            mail_before = _sig(fixture["mail_state"])
            UTIL.run(self._cfg(fixture, apply=True))
            self.assertEqual(_sig(fixture["publish_state"]), publish_before)
            self.assertEqual(_sig(fixture["mail_state"]), mail_before)
            self.assertEqual(
                json.loads(fixture["publish_state"].read_text(encoding="utf-8"))[
                    "source_fbl1n_sha256"
                ],
                fixture["combined_v1"],
            )
            self.assertEqual(
                json.loads(fixture["mail_state"].read_text(encoding="utf-8"))[
                    "source_fbl1n_sha256"
                ],
                fixture["combined_v1"],
            )
            manifest = self._manifest(fixture)
            self.assertEqual(manifest["publish_sha256_expected"], publish_before["sha256"])
            self.assertEqual(manifest["mail_sha256_expected"], mail_before["sha256"])

    def test_precheck_failure_writes_nothing(self) -> None:
        cases = (
            "mail",
            "lock",
            "migrated",
        )
        for case in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as raw:
                    fixture = self._build_fixture(Path(raw))
                    before = {
                        name: _sig(fixture[name])
                        for name in ("fbl1n_state", "publish_state", "mail_state")
                    }
                    cfg = self._cfg(fixture, apply=True)
                    if case == "mail":
                        with patch.dict(os.environ, {"MAIL_AUTO_SEND": "true"}):
                            with self.assertRaises(UTIL.MigrationError):
                                UTIL.run(cfg)
                    elif case == "lock":
                        (fixture["state_dir"] / "pipeline.lock").write_text(
                            "locked", encoding="utf-8"
                        )
                        with self.assertRaises(UTIL.MigrationError):
                            UTIL.run(cfg)
                    else:
                        payload = json.loads(
                            fixture["fbl1n_state"].read_text(encoding="utf-8")
                        )
                        payload["identity_version"] = IDENTITY_VERSION_V2
                        payload["historical_semantic_sha256"] = self.hist_sem.sha256
                        payload["combined_semantic_sha256"] = combined_semantic_sha256(
                            self.hist_sem.sha256, self.fut_sem.sha256
                        )
                        fixture["fbl1n_state"].write_text(
                            json.dumps(payload, indent=2), encoding="utf-8"
                        )
                        before["fbl1n_state"] = _sig(fixture["fbl1n_state"])
                        with self.assertRaises(UTIL.MigrationError) as raised:
                            UTIL.run(cfg)
                        self.assertIn("ya está migrado", str(raised.exception).lower())
                    self.assertFalse(fixture["backup_dir"].exists())
                    for name, signature in before.items():
                        self.assertEqual(_sig(fixture[name]), signature)

    def test_state_changes_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            original = fixture["fbl1n_state"].read_bytes()
            calls = {"n": 0}
            original_read = UTIL.read_live_sha

            def hijack(path: Path) -> str | None:
                if path.name == "last_fbl1n_state.json":
                    calls["n"] += 1
                    if calls["n"] == 2:
                        path.write_text('{"third_party": true}', encoding="utf-8")
                        return UTIL.sha256_file(path)
                return original_read(path)

            with patch.object(UTIL, "read_live_sha", side_effect=hijack):
                with self.assertRaises(UTIL.MigrationError) as raised:
                    UTIL.run(self._cfg(fixture, apply=True))
            self.assertIn("terceros", str(raised.exception).lower())
            self.assertEqual(
                fixture["fbl1n_state"].read_text(encoding="utf-8"),
                '{"third_party": true}',
            )
            self.assertNotEqual(fixture["fbl1n_state"].read_bytes(), original)
            self.assertFalse(
                (fixture["state_dir"] / "last_fbl1n_state.json.tmp").exists()
            )
            manifest = self._manifest(fixture)
            self.assertEqual(manifest["status"], "prepared")

    def test_state_disappears_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            calls = {"n": 0}
            original_read = UTIL.read_live_sha

            def vanish(path: Path) -> str | None:
                if path.name == "last_fbl1n_state.json":
                    calls["n"] += 1
                    if calls["n"] == 2:
                        path.unlink()
                        return None
                return original_read(path)

            with patch.object(UTIL, "read_live_sha", side_effect=vanish):
                with self.assertRaises(UTIL.MigrationError) as raised:
                    UTIL.run(self._cfg(fixture, apply=True))
            self.assertIn("desapareció", str(raised.exception).lower())
            self.assertFalse(fixture["fbl1n_state"].exists())
            self.assertFalse(
                (fixture["state_dir"] / "last_fbl1n_state.json.tmp").exists()
            )
            self.assertEqual(self._manifest(fixture)["status"], "prepared")

    def test_replace_failure_keeps_original_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            before = _sig(fixture["fbl1n_state"])
            publish_before = _sig(fixture["publish_state"])
            mail_before = _sig(fixture["mail_state"])
            real_replace = UTIL.os.replace

            def fail_live(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                if Path(dst).name == "last_fbl1n_state.json":
                    raise OSError("replace failed")
                real_replace(src, dst)

            with patch.object(UTIL.os, "replace", side_effect=fail_live):
                with self.assertRaises(OSError):
                    UTIL.run(self._cfg(fixture, apply=True))
            self.assertEqual(_sig(fixture["fbl1n_state"]), before)
            self.assertEqual(_sig(fixture["publish_state"]), publish_before)
            self.assertEqual(_sig(fixture["mail_state"]), mail_before)
            self.assertFalse(
                (fixture["state_dir"] / "last_fbl1n_state.json.tmp").exists()
            )
            self.assertEqual(self._manifest(fixture)["status"], "prepared")

    def test_failure_after_replace_leaves_prepared_and_live_after(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            before = _sha_file(fixture["fbl1n_state"])
            real_replace = UTIL.os.replace

            def boom_after_live(
                src: str | os.PathLike[str], dst: str | os.PathLike[str]
            ) -> None:
                real_replace(src, dst)
                if Path(dst).name == "last_fbl1n_state.json":
                    raise RuntimeError("fallo después de replace")

            with patch.object(UTIL.os, "replace", side_effect=boom_after_live):
                with self.assertRaises(RuntimeError):
                    UTIL.run(self._cfg(fixture, apply=True))
            manifest = self._manifest(fixture)
            self.assertEqual(manifest["status"], "prepared")
            self.assertEqual(_sha_file(fixture["fbl1n_state"]), manifest["fbl1n_sha256_after"])
            self.assertNotEqual(_sha_file(fixture["fbl1n_state"]), before)
            self.assertIsNone(manifest["applied_at"])

    def test_rollback_from_applied(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            original_sha = _sha_file(fixture["fbl1n_state"])
            publish_before = _sig(fixture["publish_state"])
            mail_before = _sig(fixture["mail_state"])
            UTIL.run(self._cfg(fixture, apply=True))
            self.assertEqual(self._manifest(fixture)["status"], "applied")
            result = UTIL.run(self._cfg(fixture, rollback=True))
            self.assertTrue(result.rolled_back)
            self.assertEqual(_sha_file(fixture["fbl1n_state"]), original_sha)
            self.assertEqual(self._manifest(fixture)["status"], "rolled_back")
            self.assertEqual(_sig(fixture["publish_state"]), publish_before)
            self.assertEqual(_sig(fixture["mail_state"]), mail_before)

    def test_rollback_from_prepared_live_after(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            original_sha = _sha_file(fixture["fbl1n_state"])
            real_replace = UTIL.os.replace

            def boom_after_live(
                src: str | os.PathLike[str], dst: str | os.PathLike[str]
            ) -> None:
                real_replace(src, dst)
                if Path(dst).name == "last_fbl1n_state.json":
                    raise RuntimeError("fallo después de replace")

            with patch.object(UTIL.os, "replace", side_effect=boom_after_live):
                with self.assertRaises(RuntimeError):
                    UTIL.run(self._cfg(fixture, apply=True))
            self.assertEqual(self._manifest(fixture)["status"], "prepared")
            result = UTIL.run(self._cfg(fixture, rollback=True))
            self.assertTrue(result.rolled_back)
            self.assertEqual(_sha_file(fixture["fbl1n_state"]), original_sha)
            self.assertEqual(self._manifest(fixture)["status"], "rolled_back")

    def test_prepared_live_before_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            original = _sig(fixture["fbl1n_state"])
            calls = {"n": 0}
            original_read = UTIL.read_live_sha

            def fail_cas(path: Path) -> str | None:
                if path.name == "last_fbl1n_state.json":
                    calls["n"] += 1
                    if calls["n"] == 2:
                        raise UTIL.MigrationError(
                            "El live state cambió antes del replace; se conserva el state de terceros."
                        )
                return original_read(path)

            with patch.object(UTIL, "read_live_sha", side_effect=fail_cas):
                with self.assertRaises(UTIL.MigrationError):
                    UTIL.run(self._cfg(fixture, apply=True))
            self.assertEqual(self._manifest(fixture)["status"], "prepared")
            self.assertEqual(_sig(fixture["fbl1n_state"]), original)
            result = UTIL.run(self._cfg(fixture, rollback=True))
            self.assertFalse(result.rolled_back)
            self.assertIn("no alcanzó el replace", result.message.lower())
            self.assertEqual(_sig(fixture["fbl1n_state"]), original)
            self.assertEqual(self._manifest(fixture)["status"], "prepared")

    def test_rollback_aborts_on_posterior_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            UTIL.run(self._cfg(fixture, apply=True))
            after_sha = _sha_file(fixture["fbl1n_state"])
            fixture["fbl1n_state"].write_text(
                json.dumps({"posterior": True, "run": "pipeline"}, indent=2),
                encoding="utf-8",
            )
            posterior = _sig(fixture["fbl1n_state"])
            self.assertNotEqual(posterior["sha256"], after_sha)
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(self._cfg(fixture, rollback=True))
            self.assertIn("posterior", str(raised.exception).lower())
            self.assertEqual(_sig(fixture["fbl1n_state"]), posterior)
            self.assertEqual(self._manifest(fixture)["status"], "applied")

    def test_second_rollback_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            original_sha = _sha_file(fixture["fbl1n_state"])
            UTIL.run(self._cfg(fixture, apply=True))
            first = UTIL.run(self._cfg(fixture, rollback=True))
            self.assertTrue(first.rolled_back)
            self.assertEqual(_sha_file(fixture["fbl1n_state"]), original_sha)
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(self._cfg(fixture, rollback=True))
            self.assertIn("consumida", str(raised.exception).lower())
            self.assertEqual(_sha_file(fixture["fbl1n_state"]), original_sha)
            self.assertEqual(self._manifest(fixture)["status"], "rolled_back")

    def test_failed_manifest_update_does_not_overwrite_posterior(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            UTIL.run(self._cfg(fixture, apply=True))
            real_replace = UTIL.os.replace

            def fail_manifest(
                src: str | os.PathLike[str], dst: str | os.PathLike[str]
            ) -> None:
                if Path(dst).name == "manifest.json":
                    raise OSError("manifest rolled_back failed")
                real_replace(src, dst)

            with patch.object(UTIL.os, "replace", side_effect=fail_manifest):
                with self.assertRaises(OSError):
                    UTIL.run(self._cfg(fixture, rollback=True))
            self.assertEqual(self._manifest(fixture)["status"], "applied")
            fixture["fbl1n_state"].write_text(
                json.dumps({"posterior": "corrida"}, indent=2),
                encoding="utf-8",
            )
            posterior = _sig(fixture["fbl1n_state"])
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(self._cfg(fixture, rollback=True))
            self.assertIn("posterior", str(raised.exception).lower())
            self.assertEqual(_sig(fixture["fbl1n_state"]), posterior)

    def test_second_migration_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = self._build_fixture(Path(raw))
            first = UTIL.run(self._cfg(fixture, apply=True))
            self.assertTrue(first.applied)
            after = _sig(fixture["fbl1n_state"])
            publish_after = _sig(fixture["publish_state"])
            mail_after = _sig(fixture["mail_state"])
            second_backup = Path(raw) / "backup2"
            cfg = self._cfg(fixture, apply=True)
            cfg.backup_dir = second_backup
            with self.assertRaises(UTIL.MigrationError) as raised:
                UTIL.run(cfg)
            self.assertIn("ya está migrado", str(raised.exception).lower())
            self.assertEqual(_sig(fixture["fbl1n_state"]), after)
            self.assertEqual(_sig(fixture["publish_state"]), publish_after)
            self.assertEqual(_sig(fixture["mail_state"]), mail_after)
            self.assertFalse(second_backup.exists())


class ProductionUntouchedTests(unittest.TestCase):
    def test_utility_name_has_no_p32_and_no_hardcoded_prod_paths(self) -> None:
        self.assertEqual(UTIL_PATH.name, "migrar_identidad_semantica_fbl1n.py")
        self.assertNotIn("p32", UTIL_PATH.name.lower())
        source = UTIL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("p32", source.lower())
        self.assertNotIn("usuario_ejemplo", source.lower())
        self.assertNotIn("8b9bd507", source.lower())
        self.assertNotIn("c:\\users", source.lower())
        self.assertNotIn("/users/", source.lower())
        self.assertIn("--apply", source)

    def test_prod_states_not_modified_by_this_module(self) -> None:
        before = {
            "fbl1n": _sig(PROD_STATE) if PROD_STATE.is_file() else None,
            "publish": _sig(PROD_PUBLISH) if PROD_PUBLISH.is_file() else None,
            "mail": _sig(PROD_MAIL) if PROD_MAIL.is_file() else None,
        }
        self.assertEqual(
            before["fbl1n"],
            _sig(PROD_STATE) if PROD_STATE.is_file() else None,
        )
        self.assertEqual(
            before["publish"],
            _sig(PROD_PUBLISH) if PROD_PUBLISH.is_file() else None,
        )
        self.assertEqual(
            before["mail"],
            _sig(PROD_MAIL) if PROD_MAIL.is_file() else None,
        )
