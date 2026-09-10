"""D9: aislamiento unificado de STATE_DIR (RUTA_STATE) y logs (RUTA_LOG)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROD_STATE = ROOT / "state" / "last_fbl1n_state.json"
PROD_PUB = ROOT / "state" / "last_publish_state.json"
PROD_MAIL = ROOT / "state" / "last_mail_state.json"
PROD_APP_LOG = ROOT / "logs" / "app.log"
SRC_DIR = ROOT / "src"

if not os.getenv("RUTA_LOG", "").strip():
    _focused = ROOT / "temp" / "d9_focused_logs"
    _focused.mkdir(parents=True, exist_ok=True)
    os.environ["RUTA_LOG"] = str(_focused)


class _EnvGuard:
    def __init__(self, **updates: str | None) -> None:
        self.updates = updates
        self.saved: dict[str, str | None] = {}

    def __enter__(self) -> _EnvGuard:
        for key, value in self.updates.items():
            self.saved[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *args: object) -> None:
        for key, old in self.saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sig(path: Path) -> tuple[int, int, str] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return (int(stat.st_size), int(stat.st_mtime_ns), _sha_file(path))


def _quiet_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.INFO)
    return logger


def _prod_snapshot() -> dict[str, tuple[int, int, str] | None]:
    return {
        "fbl1n": _sig(PROD_STATE),
        "publish": _sig(PROD_PUB),
        "mail": _sig(PROD_MAIL),
        "app_log": _sig(PROD_APP_LOG),
    }


class D9StateLogIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = _prod_snapshot()

    def tearDown(self) -> None:
        self.assertEqual(_prod_snapshot(), self.baseline)

    def test_01_publish_pending_writes_only_temp(self) -> None:
        from src.modules.publicacion_final.module import (
            PUBLISH_PENDING,
            load_publish_state,
            save_publish_state,
        )

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                save_publish_state(
                    {
                        "source_fbl1n_sha256": "sha-fake-pending",
                        "publish_status": PUBLISH_PENDING,
                        "publish_at": "2026-08-28T00:00:00",
                        "published_files": [],
                        "publish_error": None,
                    }
                )
                loaded = load_publish_state()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["publish_status"], PUBLISH_PENDING)
            self.assertTrue((state_dir / "last_publish_state.json").is_file())
            self.assertFalse(
                str(PROD_PUB.resolve())
                == str((state_dir / "last_publish_state.json").resolve())
            )

    def test_02_publish_succeeded_and_failed_temp_only(self) -> None:
        from src.modules.publicacion_final.module import (
            PUBLISH_FAILED,
            PUBLISH_SUCCEEDED,
            load_publish_state,
            save_publish_state,
        )

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                save_publish_state(
                    {
                        "source_fbl1n_sha256": "sha-fake-ok",
                        "publish_status": PUBLISH_SUCCEEDED,
                        "published_files": [],
                        "publish_error": None,
                    }
                )
                self.assertEqual(load_publish_state()["publish_status"], PUBLISH_SUCCEEDED)
                save_publish_state(
                    {
                        "source_fbl1n_sha256": "sha-fake-fail",
                        "publish_status": PUBLISH_FAILED,
                        "published_files": [],
                        "publish_error": "simulated",
                    }
                )
                self.assertEqual(load_publish_state()["publish_status"], PUBLISH_FAILED)
            self.assertTrue((state_dir / "last_publish_state.json").is_file())

    def test_03_mail_pending_writes_only_temp(self) -> None:
        from src.modules.actualizacion_automatica.mail import (
            MAIL_PENDING,
            load_mail_state,
            write_mail_state,
        )

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                write_mail_state(
                    sha256="mail-sha-pending",
                    status=MAIL_PENDING,
                    subject="Asunto ficticio D9",
                    logger=_quiet_logger("d9_mail_pending"),
                )
                loaded = load_mail_state()
            self.assertEqual(loaded["mail_status"], MAIL_PENDING)
            self.assertEqual(loaded["source_fbl1n_sha256"], "mail-sha-pending")
            self.assertTrue((state_dir / "last_mail_state.json").is_file())

    def test_04_mail_succeeded_and_failed_temp_only(self) -> None:
        from src.modules.actualizacion_automatica.mail import (
            MAIL_FAILED,
            MAIL_SUCCEEDED,
            load_mail_state,
            write_mail_state,
        )

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            logger = _quiet_logger("d9_mail_status")
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                write_mail_state(
                    sha256="mail-sha-ok",
                    status=MAIL_SUCCEEDED,
                    subject="Asunto ficticio D9 ok",
                    sender="remitente@example.test",
                    logger=logger,
                )
                self.assertEqual(load_mail_state()["mail_status"], MAIL_SUCCEEDED)
                write_mail_state(
                    sha256="mail-sha-fail",
                    status=MAIL_FAILED,
                    subject="Asunto ficticio D9 fail",
                    error="simulated-fail",
                    logger=logger,
                )
                self.assertEqual(load_mail_state()["mail_status"], MAIL_FAILED)

    def test_05_months_from_pipeline_state_reads_temp(self) -> None:
        from src.modules.actualizacion_automatica.mail import months_from_pipeline_state

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "last_fbl1n_state.json").write_text(
                json.dumps({"months": ["2099-12", "2099-11"]}),
                encoding="utf-8",
            )
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                months = months_from_pipeline_state()
        self.assertEqual(months, ["2099-12", "2099-11"])

    def test_06_pipeline_allows_mail_reads_temp(self) -> None:
        from src.modules.actualizacion_automatica.mail import pipeline_allows_mail

        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "last_fbl1n_state.json").write_text(
                json.dumps(
                    {
                        "sha256": "hist-fake",
                        "combined_source_sha256": "comb-fake",
                        "source_fbl1n_sha256": "comb-fake",
                        "last_success_at": "2026-08-28T00:00:00",
                    }
                ),
                encoding="utf-8",
            )
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                pipeline_allows_mail("comb-fake", future_enabled=True)

    def test_07_and_08_decoy_productive_not_read_or_written(self) -> None:
        from src.modules.actualizacion_automatica.mail import months_from_pipeline_state
        from src.modules.publicacion_final.module import save_publish_state

        before = _prod_snapshot()
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "last_fbl1n_state.json").write_text(
                json.dumps({"months": ["2099-01"]}),
                encoding="utf-8",
            )
            with _EnvGuard(RUTA_STATE=str(state_dir)):
                self.assertEqual(months_from_pipeline_state(), ["2099-01"])
                save_publish_state(
                    {
                        "source_fbl1n_sha256": "decoy-should-not-touch-prod",
                        "publish_status": "Pending",
                        "published_files": [],
                        "publish_error": None,
                    }
                )
        self.assertEqual(_prod_snapshot(), before)

    def test_09_absent_ruta_state_keeps_default(self) -> None:
        from src.config.config import ROOT_DIR, resolve_state_dir

        with _EnvGuard(RUTA_STATE=None):
            self.assertEqual(resolve_state_dir(), (ROOT_DIR / "state").resolve())

    def test_10_ruta_log_redirects_app_log(self) -> None:
        script = (
            "from src.config.logger import LoggerManager, LOG_FILE\n"
            "from src.config.config import resolve_log_dir\n"
            "logger = LoggerManager.get_logger('d9_ruta_log')\n"
            "logger.info('d9-isolated-log-line')\n"
            "path = resolve_log_dir() / LOG_FILE\n"
            "print(path.resolve())\n"
            "print(path.is_file())\n"
        )
        with tempfile.TemporaryDirectory() as raw:
            log_dir = Path(raw) / "logs"
            env = os.environ.copy()
            env["RUTA_LOG"] = str(log_dir)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = str(ROOT)
            env["MAIL_AUTO_SEND"] = "false"
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            self.assertTrue(lines)
            self.assertEqual(Path(lines[0]), (log_dir / "app.log").resolve())
            self.assertEqual(lines[1], "True")
            self.assertTrue((log_dir / "app.log").is_file())

    def test_11_focused_logger_does_not_touch_prod_log(self) -> None:
        before = _sig(PROD_APP_LOG)
        self.test_10_ruta_log_redirects_app_log()
        self.assertEqual(_sig(PROD_APP_LOG), before)

    def test_12_outlook_not_instantiated(self) -> None:
        from src.modules.actualizacion_automatica.mail import (
            MAIL_PENDING,
            write_mail_state,
        )

        self.assertNotIn("win32com.client", sys.modules)
        with tempfile.TemporaryDirectory() as raw:
            with _EnvGuard(RUTA_STATE=str(Path(raw) / "state")):
                write_mail_state(
                    sha256="no-outlook",
                    status=MAIL_PENDING,
                    subject="sin outlook",
                    logger=_quiet_logger("d9_no_outlook"),
                )
        self.assertNotIn("win32com.client", sys.modules)

    def test_13_publish_state_does_not_copy_excel(self) -> None:
        from src.modules.publicacion_final.module import save_publish_state

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with _EnvGuard(RUTA_STATE=str(root / "state")):
                save_publish_state(
                    {
                        "source_fbl1n_sha256": "no-copy",
                        "publish_status": "Pending",
                        "published_files": [],
                        "publish_error": None,
                    }
                )
            xlsx = list(root.rglob("*.xlsx"))
            self.assertEqual(xlsx, [])

    def test_14_paths_resolve_after_env_before_import(self) -> None:
        script = (
            "from src.config.config import resolve_log_dir, resolve_state_dir\n"
            "from src.modules.publicacion_final.module import publish_state_path\n"
            "from src.modules.actualizacion_automatica.mail import _mail_state_path, _pipeline_state_path\n"
            "print(resolve_state_dir())\n"
            "print(resolve_log_dir())\n"
            "print(publish_state_path())\n"
            "print(_mail_state_path())\n"
            "print(_pipeline_state_path())\n"
        )
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            log_dir = Path(raw) / "logs"
            env = os.environ.copy()
            env["RUTA_STATE"] = str(state_dir)
            env["RUTA_LOG"] = str(log_dir)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = str(ROOT)
            env["MAIL_AUTO_SEND"] = "false"
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            lines = [Path(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
            self.assertEqual(lines[0], state_dir.resolve())
            self.assertEqual(lines[1], log_dir.resolve())
            self.assertEqual(lines[2], (state_dir / "last_publish_state.json").resolve())
            self.assertEqual(lines[3], (state_dir / "last_mail_state.json").resolve())
            self.assertEqual(lines[4], (state_dir / "last_fbl1n_state.json").resolve())

    def test_15_no_other_hardcoded_state_writes(self) -> None:
        needle = 'ROOT_DIR / "state"'
        offenders: list[str] = []
        for path in SRC_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if needle not in text:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if rel == "src/config/config.py" and "_DEFAULT_STATE_DIR" in text:
                continue
            offenders.append(rel)
        self.assertEqual(offenders, [])


class D9IsolatedWriteTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = _prod_snapshot()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls.work = ROOT / "temp" / f"d9_state_isolation_{stamp}"
        state_dir = cls.work / "state"
        log_dir = cls.work / "logs"
        state_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        cls.env_guard = _EnvGuard(RUTA_STATE=str(state_dir), RUTA_LOG=str(log_dir))
        cls.env_guard.__enter__()
        from src.modules.actualizacion_automatica.mail import (
            MAIL_PENDING,
            write_mail_state,
        )
        from src.modules.actualizacion_automatica.module import save_state
        from src.modules.publicacion_final.module import (
            PUBLISH_PENDING,
            save_publish_state,
        )

        save_state(
            {
                "schema_version": "2",
                "source_mode": "historical_plus_future",
                "sha256": "d9-hist-fake",
                "months": ["2026-09"],
                "latest_compensation_date": "2026-09-02",
            }
        )
        save_publish_state(
            {
                "source_fbl1n_sha256": "d9-pub-fake",
                "publish_status": PUBLISH_PENDING,
                "published_files": [],
                "publish_error": None,
            }
        )
        write_mail_state(
            sha256="d9-mail-fake",
            status=MAIL_PENDING,
            subject="D9 isolation",
            logger=_quiet_logger("d9_trial_mail"),
        )
        app_log = log_dir / "app.log"
        trial_logger = logging.getLogger("d9_isolation_trial_file")
        trial_logger.handlers.clear()
        trial_logger.propagate = False
        handler = logging.FileHandler(app_log, encoding="utf-8")
        trial_logger.addHandler(handler)
        trial_logger.setLevel(logging.INFO)
        trial_logger.info("d9 isolation trial")
        handler.close()
        trial_logger.removeHandler(handler)
        cls.files = {
            "fbl1n": state_dir / "last_fbl1n_state.json",
            "publish": state_dir / "last_publish_state.json",
            "mail": state_dir / "last_mail_state.json",
            "app_log": app_log,
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.env_guard.__exit__(None, None, None)

    def test_trial_files_inside_d9(self) -> None:
        for path in self.files.values():
            self.assertTrue(path.is_file(), path)
            self.assertTrue(str(path.resolve()).startswith(str(self.work.resolve())))

    def test_trial_did_not_touch_productive(self) -> None:
        self.assertEqual(_prod_snapshot(), self.baseline)
