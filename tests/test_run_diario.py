"""Tests del wrapper diario Operador (mocks/temp; sin SAP/Outlook/Excel/PBI)."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.modules.fbl1n_fuentes.module import EXPECTED_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_diario.py"
PS1 = ROOT / "scripts" / "instalar_tarea_diaria.ps1"


def _load_mod():
    spec = importlib.util.spec_from_file_location("run_diario", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


MOD = _load_mod()


def _write_valid_fbl1n(path: Path, *, ref: str = "R1") -> None:
    row = {col: None for col in EXPECTED_COLUMNS}
    row["Sociedad"] = "CL44"
    row["Referencia"] = ref
    row["Fecha compensación"] = datetime(2026, 8, 31)
    row["Importe en moneda doc."] = 10
    frame = pd.DataFrame([row], columns=list(EXPECTED_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(path, index=False, engine="openpyxl")


def _write_fbl1n_with_dates(
    path: Path,
    dates: list[datetime],
    *,
    include_footer: bool = False,
) -> None:
    rows: list[dict] = []
    for i, dt in enumerate(dates):
        row = {col: None for col in EXPECTED_COLUMNS}
        row["Sociedad"] = "CL44"
        row["Referencia"] = f"R{i}"
        row["Fecha compensación"] = dt
        row["Importe en moneda doc."] = 10 + i
        rows.append(row)
    if include_footer:
        foot = {col: None for col in EXPECTED_COLUMNS}
        foot["Referencia"] = "* Total"
        foot["Importe en moneda doc."] = 999
        # Sin Sociedad ni Fecha compensación → pie SAP
        rows.append(foot)
    frame = pd.DataFrame(rows, columns=list(EXPECTED_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(path, index=False, engine="openpyxl")


def _write_invalid_fbl1n(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"a": 1}]).to_excel(path, index=False, engine="openpyxl")


def _write_dotenv(path: Path, **values: str) -> None:
    lines = [f"{k}={v}" for k, v in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@contextmanager
def _run_daily_harness(
    tmp: Path,
    future: Path,
    office_pids: dict | None = None,
    *,
    cutoff_mode: str | None = None,
):
    """Evita load_project_config real; fija globals de prueba.

    office_pids: dict con clave 'current' (set[int]) mutables para simular
    aparición de EXCEL/saplogon nuevos tras el VBS.
    """

    state = tmp / "state"
    state.mkdir(exist_ok=True)
    pids_box = office_pids if office_pids is not None else {"current": set()}

    def _fake_load() -> None:
        MOD.FBL1N_FUTURE_ENABLED = True
        MOD.FBL1N_FUTURE_PATH = future
        MOD.FBL1N_COMPENSATION_CUTOFF = date(2026, 8, 31)
        MOD.EXPECTED_COLUMNS = tuple(EXPECTED_COLUMNS)
        MOD.FECHA_COMP_COL = "Fecha compensación"
        MOD.resolve_state_dir = lambda: state  # type: ignore[assignment]
        MOD.resolve_log_dir = lambda: tmp / "logs"  # type: ignore[assignment]

    dotenv = tmp / ".env"
    env_vals = {
        "MAIL_SEND_WEEKDAY": "4",
        "MAIL_AUTO_SEND": "true",
        "FBL1N_FUTURE_ENABLED": "true",
        "FBL1N_COMPENSATION_CUTOFF": "2026-08-31",
    }
    if cutoff_mode is not None:
        env_vals["FBL1N_COMPENSATION_CUTOFF_MODE"] = cutoff_mode
    _write_dotenv(dotenv, **env_vals)
    with (
        patch.object(MOD, "ROOT", tmp),
        patch.object(MOD, "DOTENV_PATH", dotenv),
        patch.object(MOD, "load_project_config", _fake_load),
        patch.object(MOD, "precheck_config", return_value=SCRIPT),
        patch.object(MOD, "setup_logging", return_value=(logging.getLogger("h"), tmp / "x.log")),
        patch.object(MOD, "VENV_PYTHON", SCRIPT),
        patch.object(MOD, "PIPELINE_SCRIPT", SCRIPT),
        patch.object(
            MOD,
            "list_pids_for_images",
            side_effect=lambda *a, **k: set(pids_box["current"]),
        ),
    ):
        yield state


class TestRunDiario(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_diario")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())
        self._interval_patch = patch.object(MOD, "STABLE_INTERVAL_SEC", 0.01)
        self._interval_patch.start()
        self.addCleanup(self._interval_patch.stop)
        os.environ["MAIL_SEND_WEEKDAY"] = "4"

    def test_active_lock_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            lock = state / MOD.LOCK_FILENAME
            lock.write_text(json.dumps({"pid": 111}), encoding="utf-8")
            with (
                patch.object(MOD, "resolve_state_dir", return_value=state),
                patch.object(MOD, "_pid_running", side_effect=lambda p: p == 111),
            ):
                dl = MOD.DiarioLock(lock)
                dl.pid = 222
                with self.assertRaises(MOD.DiarioAborted) as ctx:
                    dl.acquire(self.logger)
                self.assertEqual(ctx.exception.exit_code, MOD.EXIT_LOCK)
            self.assertTrue(lock.is_file())

    def test_orphan_lock_blocks_without_delete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            lock = state / MOD.LOCK_FILENAME
            lock.write_text(json.dumps({"pid": 424242}), encoding="utf-8")
            with (
                patch.object(MOD, "resolve_state_dir", return_value=state),
                patch.object(MOD, "_pid_running", return_value=False),
            ):
                dl = MOD.DiarioLock(lock)
                with self.assertRaises(MOD.DiarioAborted) as ctx:
                    dl.acquire(self.logger)
                self.assertEqual(ctx.exception.exit_code, MOD.EXIT_LOCK)
                self.assertIn("huérfano", str(ctx.exception).lower())
            self.assertTrue(lock.is_file(), "lock huérfano no debe borrarse")

    def test_backup_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N..XLSX"
            _write_valid_fbl1n(future, ref="OLD")
            with patch.object(MOD, "ROOT", tmp):
                info = MOD.backup_future_file(future, self.logger)
            self.assertIsNotNone(info)
            assert info is not None
            self.assertTrue(info.backup.is_file())
            self.assertTrue(future.is_file())
            MOD.restore_future_atomic(info, self.logger)
            self.assertTrue(info.backup.is_file())

    def test_vbs_fail_restores_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "out" / "FBL1N..XLSX"
            _write_valid_fbl1n(future, ref="PREV")
            prev_sha = MOD._sha256_file(future)
            terminated: list[int] = []

            def fake_cscript(_vbs, _logger):
                future.unlink()
                future.write_bytes(b"not-a-zip")
                return MOD.ChildProc(pid=555)

            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    simulate_vbs=False,
                    vbs_timeout_sec=1.0,
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(pid=0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertNotEqual(code, 0)
            self.assertEqual(MOD._sha256_file(future), prev_sha)
            self.assertIn(555, terminated)
            backups = list((tmp / "temp" / MOD.BACKUP_DIRNAME).glob("*.xlsx"))
            self.assertTrue(backups)

    def test_invalid_file_skips_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            pipeline_calls: list[int] = []

            def fake_cscript(_vbs, _logger):
                _write_invalid_fbl1n(future)
                return MOD.ChildProc(pid=777)

            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    vbs_timeout_sec=5.0,
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: pipeline_calls.append(1) or (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_INVALID)
            self.assertEqual(pipeline_calls, [])

    def test_valid_stable_runs_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="OLD")
            ran: list[int] = []

            def fake_cscript(_vbs, _logger):
                _write_valid_fbl1n(future, ref="NEW")
                return MOD.ChildProc(pid=888)

            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    vbs_timeout_sec=10.0,
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: ran.append(1) or (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertEqual(ran, [1])

    def test_terminates_only_started_child_pid(self) -> None:
        terminated: list[int] = []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)

            def fake_cscript(_vbs, _logger):
                _write_valid_fbl1n(future, ref="NEW")
                return MOD.ChildProc(pid=12345)

            with _run_daily_harness(tmp, future):
                MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(pid=0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(terminated[0], 12345)
            self.assertTrue(all(p == 12345 for p in terminated))
            self.assertNotIn(99999, terminated)

    def test_msgbox_child_killed_after_validate(self) -> None:
        order: list[str] = []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)

            def fake_cscript(_vbs, _logger):
                order.append("start")
                _write_valid_fbl1n(future, ref="NEW")
                return MOD.ChildProc(pid=999)

            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: order.append(f"term:{pid}") or True,
                    run_pipeline_fn=lambda _lg: order.append("pipeline") or (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertEqual(order[:3], ["start", "term:999", "pipeline"])
            self.assertIn("term:999", order)

    def test_pipeline_unchanged_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)

    def test_pipeline_error_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)
            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (7, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_PIPELINE)
            self.assertEqual(MOD._sha256_file(future), prev_sha)

    def test_lock_released_on_success_and_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            with _run_daily_harness(tmp, future) as state:
                lock = state / MOD.LOCK_FILENAME
                MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
                self.assertFalse(lock.is_file())
                MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (9, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
                self.assertFalse(lock.is_file())

    def test_task_definition_in_ps1(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertIn("Automatizacion_FBL1N_Diaria", text)
        self.assertIn("Monday", text)
        self.assertIn("Friday", text)
        self.assertIn("09:00", text)
        self.assertIn("Interactive", text)
        self.assertIn("Limited", text)
        self.assertIn("IgnoreNew", text)
        self.assertIn("StartWhenAvailable", text)
        self.assertIn("Hours 3", text)
        self.assertIn("Disable-ScheduledTask", text)
        self.assertIn("Invoke-Prechecks", text)
        self.assertIn("-Enable", text)
        self.assertIn("-Replace", text)
        self.assertNotIn("PBIDesktop", text)
        self.assertNotIn("powerbi", text.lower())

    def test_enable_validates_before_enable(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        idx_pre = text.find("Invoke-Prechecks -Root $root")
        idx_en = text.find("Enable-ScheduledTask -TaskName $taskName")
        self.assertGreater(idx_pre, 0)
        self.assertGreater(idx_en, idx_pre)

    def test_installer_still_mon_fri_0900(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertIn(
            "New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 09:00",
            text,
        )

    def test_no_powerbi_in_wrapper(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("PBIDesktop", text)
        self.assertNotIn("powerbi.com", text.lower())

    def test_no_hardcoded_recipients_or_secrets(self) -> None:
        for path in (SCRIPT, PS1):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("@empresa.example", text.lower())
            self.assertNotIn("password", text.lower())
            self.assertNotIn("CL_EJEMPLO", text)
            self.assertNotIn("MAIL_TO=", text)

    def test_monday_mail_auto_send_true_effective_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_AUTO_SEND", None)
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 7, 9, 0, 0),
                simulate_vbs=False,
                dotenv_path=dotenv,
            )
            self.assertTrue(policy.mail_configured)
            self.assertFalse(policy.mail_effective)
            self.assertEqual(policy.weekday, 0)

    def test_thursday_mail_auto_send_true_effective_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_AUTO_SEND", None)
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 10, 9, 0, 0),
                simulate_vbs=False,
                dotenv_path=dotenv,
            )
            self.assertFalse(policy.mail_effective)
            self.assertEqual(policy.weekday, 3)

    def test_friday_mail_auto_send_true_effective_true(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_AUTO_SEND", None)
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 11, 9, 0, 0),
                simulate_vbs=False,
                dotenv_path=dotenv,
            )
            self.assertTrue(policy.mail_effective)
            self.assertEqual(policy.weekday, 4)

    def test_friday_mail_auto_send_false_effective_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="false")
            os.environ.pop("MAIL_AUTO_SEND", None)
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 11, 9, 0, 0),
                simulate_vbs=False,
                dotenv_path=dotenv,
            )
            self.assertFalse(policy.mail_configured)
            self.assertFalse(policy.mail_effective)

    def test_simulate_vbs_friday_forces_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_AUTO_SEND", None)
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 11, 9, 0, 0),
                simulate_vbs=True,
                dotenv_path=dotenv,
            )
            self.assertFalse(policy.mail_effective)
            self.assertIn("simulate-vbs", policy.motivo)

    def test_mail_send_weekday_missing_aborts_before_vbs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            dotenv = tmp / ".env"
            _write_dotenv(dotenv, MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_SEND_WEEKDAY", None)
            started: list[str] = []
            with (
                patch.object(MOD, "ROOT", tmp),
                patch.object(MOD, "DOTENV_PATH", dotenv),
                patch.object(MOD, "load_project_config"),
                patch.object(MOD, "setup_logging", return_value=(self.logger, tmp / "x.log")),
            ):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 11, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: started.append("vbs") or MOD.ChildProc(0),
                    run_pipeline_fn=lambda _lg: started.append("pipe") or (0, MOD.ChildProc(0)),
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_CONFIG)
            self.assertEqual(started, [])

    def test_mail_send_weekday_invalid_aborts_before_vbs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            dotenv = tmp / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="9", MAIL_AUTO_SEND="true")
            os.environ.pop("MAIL_SEND_WEEKDAY", None)
            started: list[str] = []
            with (
                patch.object(MOD, "ROOT", tmp),
                patch.object(MOD, "DOTENV_PATH", dotenv),
                patch.object(MOD, "load_project_config"),
                patch.object(MOD, "setup_logging", return_value=(self.logger, tmp / "x.log")),
            ):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 11, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: started.append("vbs") or MOD.ChildProc(0),
                    run_pipeline_fn=lambda _lg: started.append("pipe") or (0, MOD.ChildProc(0)),
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_CONFIG)
            self.assertEqual(started, [])

    def test_friday_pending_triggers_retry_flow(self) -> None:
        calls: list[str] = []

        def fake_retry(_logger):
            calls.append("retry")
            return "retried:Succeeded"

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)
            with _run_daily_harness(tmp, future):
                os.environ.pop("MAIL_AUTO_SEND", None)
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 11, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=fake_retry,
                )
            self.assertEqual(code, 0)
            self.assertEqual(calls, ["retry"])

    def test_simulate_does_not_modify_future_sha_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="SIM")
            before = (
                MOD._sha256_file(future),
                future.stat().st_size,
                future.stat().st_mtime_ns,
                future.read_bytes(),
            )
            vbs_calls: list[int] = []
            pipe_calls: list[int] = []
            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    simulate_vbs=True,
                    logger=self.logger,
                    now=datetime(2026, 9, 11, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: vbs_calls.append(1) or MOD.ChildProc(1),
                    run_pipeline_fn=lambda _lg: pipe_calls.append(1) or (0, MOD.ChildProc(0)),
                    mail_retry_fn=lambda _lg: (_ for _ in ()).throw(AssertionError("mail")),
                )
            self.assertEqual(code, 0)
            self.assertEqual(vbs_calls, [])
            self.assertEqual(pipe_calls, [])
            after = (
                MOD._sha256_file(future),
                future.stat().st_size,
                future.stat().st_mtime_ns,
                future.read_bytes(),
            )
            self.assertEqual(after, before)

    def test_simulate_always_mail_effective_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            _write_dotenv(dotenv, MAIL_SEND_WEEKDAY="4", MAIL_AUTO_SEND="true")
            policy = MOD.resolve_mail_day_policy(
                now=datetime(2026, 9, 11, 9, 0, 0),
                simulate_vbs=True,
                dotenv_path=dotenv,
            )
            self.assertFalse(policy.mail_effective)

    def test_simulate_fixture_not_copied_to_future(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            fixture = tmp / "fixture.xlsx"
            _write_valid_fbl1n(future, ref="PROD")
            _write_valid_fbl1n(fixture, ref="FIX")
            prod_sha = MOD._sha256_file(future)
            fix_sha = MOD._sha256_file(fixture)
            self.assertNotEqual(prod_sha, fix_sha)
            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    simulate_vbs=True,
                    simulate_fixture=fixture,
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("vbs")),
                    run_pipeline_fn=lambda _lg: (_ for _ in ()).throw(AssertionError("pipe")),
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertEqual(MOD._sha256_file(future), prod_sha)
            self.assertEqual(MOD._sha256_file(fixture), fix_sha)

    def test_keyboard_interrupt_restores_sha(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)
            terminated: list[int] = []

            def boom(_lg):
                return (_ for _ in ()).throw(KeyboardInterrupt())

            with _run_daily_harness(tmp, future) as state:
                lock = state / MOD.LOCK_FILENAME
                with self.assertRaises(KeyboardInterrupt):
                    MOD.run_daily(
                        logger=self.logger,
                        now=datetime(2026, 9, 7, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (
                            _write_valid_fbl1n(future, ref="NEW") or MOD.ChildProc(pid=4242)
                        ),
                        terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                        run_pipeline_fn=boom,
                        sleep_fn=lambda _s: None,
                        mail_retry_fn=lambda _lg: "skip",
                    )
                self.assertFalse(lock.is_file())
            self.assertEqual(MOD._sha256_file(future), prev_sha)
            self.assertIn(4242, terminated)
            evidence = list((tmp / "temp" / "fbl1n_future_failed").glob("*.xlsx"))
            self.assertTrue(evidence)

    def test_system_exit_restores_sha(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)

            def boom(_lg):
                raise SystemExit(99)

            with _run_daily_harness(tmp, future):
                with self.assertRaises(SystemExit):
                    MOD.run_daily(
                        logger=self.logger,
                        now=datetime(2026, 9, 7, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (
                            _write_valid_fbl1n(future, ref="NEW") or MOD.ChildProc(pid=7)
                        ),
                        terminate_fn=lambda *_a, **_k: True,
                        run_pipeline_fn=boom,
                        sleep_fn=lambda _s: None,
                        mail_retry_fn=lambda _lg: "skip",
                    )
            self.assertEqual(MOD._sha256_file(future), prev_sha)

    def test_main_keyboard_interrupt_nonzero(self) -> None:
        with patch.object(MOD, "run_daily", side_effect=KeyboardInterrupt):
            code = MOD.main([])
        self.assertEqual(code, MOD.EXIT_INTERRUPTED)
        self.assertNotEqual(code, 0)

    def test_real_success_keeps_new_future(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="OLD")
            new_sha_holder: list[str] = []

            def fake_cscript(_vbs, _logger):
                _write_valid_fbl1n(future, ref="NEW")
                new_sha_holder.append(MOD._sha256_file(future))
                return MOD.ChildProc(pid=11)

            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(pid=22)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertEqual(MOD._sha256_file(future), new_sha_holder[0])

    def test_interrupt_terminates_only_registered_child(self) -> None:
        terminated: list[int] = []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)

            def boom(_lg):
                raise KeyboardInterrupt()

            with _run_daily_harness(tmp, future):
                with self.assertRaises(KeyboardInterrupt):
                    MOD.run_daily(
                        logger=self.logger,
                        now=datetime(2026, 9, 7, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (
                            _write_valid_fbl1n(future, ref="N") or MOD.ChildProc(pid=7777)
                        ),
                        terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                        run_pipeline_fn=boom,
                        sleep_fn=lambda _s: None,
                        mail_retry_fn=lambda _lg: "skip",
                    )
            self.assertTrue(terminated)
            self.assertTrue(all(p == 7777 for p in terminated))

    def test_release_pipeline_lock_only_if_child(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            lock = state / MOD.PIPELINE_LOCK_FILENAME
            lock.write_text(json.dumps({"pid": 555}), encoding="utf-8")
            with patch.object(MOD, "resolve_state_dir", return_value=state):
                MOD.release_pipeline_lock_if_child({555}, self.logger)
                self.assertFalse(lock.is_file())
                lock.write_text(json.dumps({"pid": 999}), encoding="utf-8")
                MOD.release_pipeline_lock_if_child({555}, self.logger)
                self.assertTrue(lock.is_file())

    def test_permission_error_is_retried_then_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="NEW")
            opens = {"n": 0}
            real_open = Path.open

            def flaky_open(self, *a, **k):  # noqa: ANN001
                if self.resolve() == future.resolve():
                    opens["n"] += 1
                    if opens["n"] <= 2:
                        raise PermissionError("locked by Excel")
                return real_open(self, *a, **k)

            with patch.object(Path, "open", flaky_open):
                MOD.wait_until_file_readable(
                    future,
                    timeout_sec=5.0,
                    logger=self.logger,
                    sleep_fn=lambda _s: None,
                )
                meta = MOD.validate_fbl1n_business_retrying(
                    future,
                    self.logger,
                    timeout_sec=5.0,
                    sleep_fn=lambda _s: None,
                )
            self.assertGreaterEqual(opens["n"], 3)
            self.assertGreaterEqual(meta["rows"], 1)

            # Tras liberar el archivo, el flujo real valida y continúa al pipeline.
            ran: list[int] = []
            with _run_daily_harness(tmp, future):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=lambda *_a, **_k: (
                        _write_valid_fbl1n(future, ref="N2") or MOD.ChildProc(pid=1)
                    ),
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: ran.append(1) or (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertEqual(ran, [1])

    def test_new_excel_terminated_preexisting_spared(self) -> None:
        terminated: list[int] = []
        office = {"current": {100, 200}}  # preexisting Excel/saplogon
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)

            def fake_cscript(_vbs, _logger):
                _write_valid_fbl1n(future, ref="NEW")
                office["current"] = {100, 200, 300}  # new Excel
                return MOD.ChildProc(pid=50)

            with _run_daily_harness(tmp, future, office_pids=office):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertIn(50, terminated)
            self.assertIn(300, terminated)
            self.assertNotIn(100, terminated)
            self.assertNotIn(200, terminated)

    def test_new_saplogon_cleaned_preexisting_not(self) -> None:
        terminated: list[int] = []
        office = {"current": {10}}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future)

            def fake_cscript(_vbs, _logger):
                _write_valid_fbl1n(future, ref="NEW")
                office["current"] = {10, 99}
                return MOD.ChildProc(pid=8)

            with _run_daily_harness(tmp, future, office_pids=office):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, 0)
            self.assertIn(99, terminated)
            self.assertNotIn(10, terminated)
            self.assertIn(8, terminated)

    def test_failure_releases_new_pids_then_restores(self) -> None:
        terminated: list[int] = []
        office = {"current": {5}}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)

            def fake_cscript(_vbs, _logger):
                _write_invalid_fbl1n(future)
                office["current"] = {5, 77}
                return MOD.ChildProc(pid=66)

            with _run_daily_harness(tmp, future, office_pids=office):
                code = MOD.run_daily(
                    vbs_timeout_sec=5.0,
                    logger=self.logger,
                    now=datetime(2026, 9, 7, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                    run_pipeline_fn=lambda _lg: (0, MOD.ChildProc(0)),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_INVALID)
            self.assertEqual(MOD._sha256_file(future), prev_sha)
            self.assertIn(66, terminated)
            self.assertIn(77, terminated)
            self.assertNotIn(5, terminated)

    def test_keyboard_interrupt_restores_after_office_release(self) -> None:
        terminated: list[int] = []
        office = {"current": set()}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)

            def boom(_lg):
                office["current"] = {888}
                raise KeyboardInterrupt()

            with _run_daily_harness(tmp, future, office_pids=office) as state:
                lock = state / MOD.LOCK_FILENAME
                with self.assertRaises(KeyboardInterrupt):
                    MOD.run_daily(
                        logger=self.logger,
                        now=datetime(2026, 9, 7, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (
                            _write_valid_fbl1n(future, ref="NEW")
                            or office["current"].update({888})
                            or MOD.ChildProc(pid=44)
                        ),
                        terminate_fn=lambda pid, _lg: terminated.append(pid) or True,
                        run_pipeline_fn=boom,
                        sleep_fn=lambda _s: None,
                        mail_retry_fn=lambda _lg: "skip",
                    )
                self.assertFalse(lock.is_file())
            self.assertEqual(MOD._sha256_file(future), prev_sha)
            self.assertIn(44, terminated)
            self.assertIn(888, terminated)

    def test_is_transient_lock_error_helpers(self) -> None:
        self.assertTrue(MOD.is_transient_lock_error(PermissionError("x")))
        err = OSError("denied")
        err.winerror = 32  # type: ignore[attr-defined]
        self.assertTrue(MOD.is_transient_lock_error(err))
        self.assertFalse(MOD.is_transient_lock_error(ValueError("no")))

    def test_max_source_cutoff_local_08_source_10(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_fbl1n_with_dates(
                future,
                [
                    datetime(2026, 9, 8),
                    datetime(2026, 9, 10),
                    datetime(2026, 9, 9),
                ],
                include_footer=True,
            )
            MOD.EXPECTED_COLUMNS = tuple(EXPECTED_COLUMNS)
            MOD.FECHA_COMP_COL = "Fecha compensación"
            info = MOD.compute_source_cutoff_info(
                future,
                local_date=date(2026, 9, 8),
                logger=self.logger,
            )
            self.assertEqual(info.effective_compensation_cutoff, "2026-09-10")
            self.assertEqual(info.source_latest_compensation_date, "2026-09-10")
            self.assertEqual(info.rows_with_date_after_local_date, 2)
            self.assertEqual(info.valid_business_rows, 3)
            self.assertIn("Fecha de pago al 10/09/2026", info.mail_subject_preview)

            from src.modules.fbl1n_fuentes.module import semantic_fbl1n_fingerprint
            import pandas as pd

            frame = pd.read_excel(future, engine="calamine")
            sem = semantic_fbl1n_fingerprint(
                frame, compensation_cutoff=info.effective_compensation_cutoff
            )
            self.assertEqual(sem.valid_rows, 3)
            self.assertEqual(sem.cutoff_excluded_rows, 0)
            self.assertEqual(sem.latest_compensation_date, "2026-09-10")

    def test_sap_footer_does_not_affect_max_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            future = Path(td) / "FBL1N.xlsx"
            _write_fbl1n_with_dates(
                future,
                [datetime(2026, 9, 1)],
                include_footer=True,
            )
            MOD.EXPECTED_COLUMNS = tuple(EXPECTED_COLUMNS)
            MOD.FECHA_COMP_COL = "Fecha compensación"
            info = MOD.compute_source_cutoff_info(
                future,
                local_date=date(2026, 9, 8),
                logger=self.logger,
            )
            self.assertEqual(info.effective_compensation_cutoff, "2026-09-01")
            self.assertEqual(info.valid_business_rows, 1)

    def test_pipeline_receives_max_cutoff_env(self) -> None:
        seen: list[str] = []
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_fbl1n_with_dates(
                future,
                [datetime(2026, 9, 8), datetime(2026, 9, 10)],
            )
            prev = os.environ.get("FBL1N_COMPENSATION_CUTOFF")

            def pipe(_lg):
                seen.append(os.environ.get("FBL1N_COMPENSATION_CUTOFF", ""))
                return (0, MOD.ChildProc(0))

            try:
                with _run_daily_harness(
                    tmp, future, cutoff_mode=MOD.CUTOFF_MODE_MAX_SOURCE
                ):
                    code = MOD.run_daily(
                        logger=self.logger,
                        now=datetime(2026, 9, 8, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (
                            _write_fbl1n_with_dates(
                                future,
                                [datetime(2026, 9, 8), datetime(2026, 9, 10)],
                            )
                            or MOD.ChildProc(pid=1)
                        ),
                        terminate_fn=lambda *_a, **_k: True,
                        run_pipeline_fn=pipe,
                        sleep_fn=lambda _s: None,
                        mail_retry_fn=lambda _lg: "skip",
                    )
                self.assertEqual(code, 0)
                self.assertEqual(seen, ["2026-09-10"])
            finally:
                if prev is None:
                    os.environ.pop("FBL1N_COMPENSATION_CUTOFF", None)
                else:
                    os.environ["FBL1N_COMPENSATION_CUTOFF"] = prev

    def test_no_valid_business_dates_aborts_and_restores(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_valid_fbl1n(future, ref="ORIG")
            prev_sha = MOD._sha256_file(future)

            def fake_cscript(_vbs, _logger):
                # Pie SAP + fila con fecha pero sin Sociedad → no filas de negocio.
                row = {col: None for col in EXPECTED_COLUMNS}
                row["Referencia"] = "* Total"
                row2 = {col: None for col in EXPECTED_COLUMNS}
                row2["Fecha compensación"] = datetime(2026, 9, 10)
                pd.DataFrame([row, row2], columns=list(EXPECTED_COLUMNS)).to_excel(
                    future, index=False, engine="openpyxl"
                )
                return MOD.ChildProc(pid=3)

            with _run_daily_harness(
                tmp, future, cutoff_mode=MOD.CUTOFF_MODE_MAX_SOURCE
            ):
                code = MOD.run_daily(
                    logger=self.logger,
                    now=datetime(2026, 9, 8, 9, 0, 0),
                    start_cscript_fn=fake_cscript,
                    terminate_fn=lambda *_a, **_k: True,
                    run_pipeline_fn=lambda _lg: (_ for _ in ()).throw(
                        AssertionError("no pipeline")
                    ),
                    sleep_fn=lambda _s: None,
                    mail_retry_fn=lambda _lg: "skip",
                )
            self.assertEqual(code, MOD.EXIT_INVALID)
            self.assertEqual(MOD._sha256_file(future), prev_sha)

    def test_simulate_shows_max_cutoff_without_env_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            future = tmp / "FBL1N.xlsx"
            _write_fbl1n_with_dates(
                future,
                [datetime(2026, 9, 8), datetime(2026, 9, 10)],
            )
            prev = os.environ.get("FBL1N_COMPENSATION_CUTOFF")
            os.environ["FBL1N_COMPENSATION_CUTOFF"] = "2026-08-31"
            try:
                with _run_daily_harness(
                    tmp, future, cutoff_mode=MOD.CUTOFF_MODE_MAX_SOURCE
                ):
                    code = MOD.run_daily(
                        simulate_vbs=True,
                        logger=self.logger,
                        now=datetime(2026, 9, 8, 9, 0, 0),
                        start_cscript_fn=lambda *_a, **_k: (_ for _ in ()).throw(
                            AssertionError("vbs")
                        ),
                        run_pipeline_fn=lambda _lg: (_ for _ in ()).throw(
                            AssertionError("pipe")
                        ),
                        mail_retry_fn=lambda _lg: (_ for _ in ()).throw(
                            AssertionError("mail")
                        ),
                    )
                self.assertEqual(code, 0)
                self.assertEqual(
                    os.environ.get("FBL1N_COMPENSATION_CUTOFF"), "2026-08-31"
                )
            finally:
                if prev is None:
                    os.environ.pop("FBL1N_COMPENSATION_CUTOFF", None)
                else:
                    os.environ["FBL1N_COMPENSATION_CUTOFF"] = prev

    def test_unchanged_without_pending_does_not_send(self) -> None:
        with patch.dict(os.environ, {"MAIL_AUTO_SEND": "true"}):
            import src.config.config as cfg

            cfg.MAIL_AUTO_SEND = True
            with (
                patch(
                    "src.modules.actualizacion_automatica.module.load_state",
                    return_value={
                        "source_fbl1n_sha256": "abc",
                        "months": ["2026-08"],
                        "latest_compensation_date": "2026-08-31",
                    },
                ),
                patch(
                    "src.modules.publicacion_final.module.load_publish_state",
                    return_value={
                        "publish_status": "Succeeded",
                        "source_fbl1n_sha256": "abc",
                    },
                ),
                patch(
                    "src.modules.actualizacion_automatica.mail.load_mail_state",
                    return_value={
                        "mail_status": "Succeeded",
                        "source_fbl1n_sha256": "abc",
                    },
                ),
                patch(
                    "src.modules.actualizacion_automatica.mail.run_mail_stage",
                    side_effect=AssertionError("no debe enviar"),
                ) as rms,
            ):
                status = MOD.maybe_retry_pending_mail(self.logger)
            self.assertEqual(status, "skipped_no_pending")
            rms.assert_not_called()

    def test_pending_mail_calls_run_mail_stage(self) -> None:
        with patch.dict(os.environ, {"MAIL_AUTO_SEND": "true"}):
            import src.config.config as cfg

            cfg.MAIL_AUTO_SEND = True
            staged = MagicMock(status="Succeeded", executed=True, message="ok")
            with (
                patch(
                    "src.modules.actualizacion_automatica.module.load_state",
                    return_value={
                        "source_fbl1n_sha256": "abc",
                        "months": ["2026-08"],
                        "latest_compensation_date": "2026-08-31",
                    },
                ),
                patch(
                    "src.modules.publicacion_final.module.load_publish_state",
                    return_value={
                        "publish_status": "Succeeded",
                        "source_fbl1n_sha256": "abc",
                    },
                ),
                patch(
                    "src.modules.actualizacion_automatica.mail.load_mail_state",
                    return_value={
                        "mail_status": "Pending",
                        "source_fbl1n_sha256": "abc",
                    },
                ),
                patch(
                    "src.modules.actualizacion_automatica.mail.run_mail_stage",
                    return_value=staged,
                ) as rms,
            ):
                status = MOD.maybe_retry_pending_mail(self.logger)
            self.assertEqual(status, "retried:Succeeded")
            rms.assert_called_once()
            kwargs = rms.call_args.kwargs
            self.assertEqual(kwargs.get("decision"), "Changed")
            self.assertTrue(kwargs.get("publish_ok"))


if __name__ == "__main__":
    unittest.main()
