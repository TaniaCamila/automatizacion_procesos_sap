"""D7: run_actualizacion(detect_only=True) aislado, modo futuro solo en el proceso."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D1_DIR = ROOT / "temp" / "auditoria_dos_fbl1n_20260827_20260827_173610"
D1_HIST = D1_DIR / "FBL1N_HISTORICO_COPIA.xlsx"
D1_FUT = D1_DIR / "FBL1N_FUTURO_COPIA.xlsx"
ORCH_PATH = ROOT / "src" / "modules" / "actualizacion_automatica" / "module.py"
PROD_STATE = ROOT / "state" / "last_fbl1n_state.json"
PROD_MAIL = ROOT / "state" / "last_mail_state.json"
PROD_PUB = ROOT / "state" / "last_publish_state.json"
PROD_LOCK = ROOT / "state" / "pipeline.lock"
PROD_APP_LOG = ROOT / "logs" / "app.log"
PROD_LOG_DIR = ROOT / "logs"

EXPECTED_HIST = "ae9af1eb744e46a7dc1aa4abcec435efa1c1acb76059fa116411a12906dde28c"
EXPECTED_FUT = "97d71c784ace7f14bad20f1f7f612da2af70d592844f9b0908f9023c1cff1377"
EXPECTED_SEM = "b013acbc4a6f226c870e8704de258a1f5512fc91529f9f616e3579625ad5fca0"
EXPECTED_COMB = "3cd032bf30cc6a26c8d7b37aec52d26b5ed425ad9e5aba1fda222113474aa580"

PAGO_ME_NAME = "EJM_ARCHIVO_PAGO_MONEDA_EXTRANJERA.xlsx"
COM_PROCESS_NEEDLES = (
    "excel.exe",
    "saplogon.exe",
    "sapgui.exe",
    "wscript.exe",
    "cscript.exe",
)
FORBIDDEN_LOG = (
    "Etapa 1 src/main.py",
    "Iniciando Etapa 2",
    "Matriz generada",
    "win32com",
    "Outlook.Application",
    ".Display(",
    ".Send(",
    "Application().run",
    "construir_dinamicas_finales",
)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sig(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha_file(path),
    }


def _orch_log_names() -> list[str]:
    if not PROD_LOG_DIR.is_dir():
        return []
    return sorted(path.name for path in PROD_LOG_DIR.glob("actualizacion_automatica_*.log"))


def _dir_inventory(path: Path) -> list[dict[str, object]]:
    if not path.is_dir():
        return []
    rows: list[dict[str, object]] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        stat = item.stat()
        rows.append(
            {
                "name": str(item.relative_to(path)).replace("\\", "/"),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        )
    return rows


def _sanitize(text: str) -> str:
    text = re.sub(r"(?i)C:\\Users\\[^\\]+", r"C:\\Users\\<user>", text)
    text = re.sub(r"(?i)/Users/[^/]+", "/Users/<user>", text)
    text = re.sub(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        "<redacted-email>",
        text,
        flags=re.I,
    )
    return text


def _list_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    names: list[str] = []
    for item in sorted(root.rglob("*")):
        if item.is_file():
            names.append(str(item.relative_to(root)).replace("\\", "/"))
    return names


def _com_pids() -> set[int]:
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        lower = line.lower()
        if not any(name in lower for name in COM_PROCESS_NEEDLES):
            continue
        parts = [part.strip().strip('"') for part in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            pids.add(int(parts[1]))
        except ValueError:
            continue
    return pids


def _d7_env(work: Path, state_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["RUTA_INPUT"] = str(work / "input")
    env["RUTA_OUTPUT"] = str(work / "output")
    env["RUTA_RECURSOS"] = str(work / "resources")
    env["RUTA_PUBLICACION"] = str(work / "publication")
    env["RUTA_STATE"] = str(state_dir)
    env["RUTA_LOG"] = str(work / "logs")
    env["FBL1N_FUTURE_ENABLED"] = "true"
    env["FBL1N_FUTURE_PATH"] = str(work / "input" / "FBL1N_FUTURO.xlsx")
    env["MAIL_AUTO_SEND"] = "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["FBL1N_STABLE_CHECKS"] = "1"
    env["FBL1N_STABLE_INTERVAL_SEC"] = "0"
    env["PYTHONPATH"] = str(ROOT)
    return env


def _run_child(work: Path, state_dir: Path, result_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(result_path)],
        cwd=str(ROOT),
        env=_d7_env(work, state_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )
    payload: dict[str, object]
    if result_path.is_file():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        payload = {"ok": False, "error": "sin result.json"}
    payload["returncode"] = completed.returncode
    payload["stdout"] = _sanitize(completed.stdout or "")
    payload["stderr"] = _sanitize(completed.stderr or "")
    return payload


def _child_main(result_path: Path) -> int:
    from src.config.config import (
        FBL1N_FUTURE_ENABLED,
        FBL1N_PATH,
        INPUT_DIR,
        LOG_DIR,
        MAIL_AUTO_SEND,
        OUTPUT_DIR,
        PUBLICATION_DIR,
        STATE_DIR,
    )
    from src.modules.actualizacion_automatica.module import run_actualizacion

    try:
        result = run_actualizacion(detect_only=True)
        payload = {
            "ok": True,
            "error": "",
            "status": result.status,
            "skipped": result.skipped,
            "message": result.message,
            "decision": result.decision,
            "source_mode": result.source_mode,
            "sha256": result.sha256,
            "combined_source_sha256": result.combined_source_sha256,
            "future_semantic_sha256": result.future_semantic_sha256,
            "latest_compensation_date": result.latest_compensation_date,
            "future_valid_rows": result.future_valid_rows,
            "future_invalid_rows": result.future_invalid_rows,
            "publish_status": result.publish_status,
            "mail_status": result.mail_status,
            "matriz_path": str(result.matriz_path) if result.matriz_path else "",
            "dinamicas_path": str(result.dinamicas_path) if result.dinamicas_path else "",
            "log_path": result.log_path.name if result.log_path else "",
            "future_enabled": bool(FBL1N_FUTURE_ENABLED),
            "mail_auto_send": bool(MAIL_AUTO_SEND),
            "state_dir": STATE_DIR.name,
            "log_dir": LOG_DIR.name,
            "input_name": FBL1N_PATH.name,
            "state_files": _list_files(STATE_DIR),
            "output_files": _list_files(OUTPUT_DIR),
            "publication_files": _list_files(PUBLICATION_DIR),
            "input_dir_ok": INPUT_DIR.name == "input",
        }
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0 if payload.get("ok") else 1


class D7DetectOnlyStaticTests(unittest.TestCase):
    def test_00_static_review_detect_only(self) -> None:
        source = ORCH_PATH.read_text(encoding="utf-8")
        body = source[source.index("def run_actualizacion") :]
        self.assertNotIn("from src.app import Application", source)
        self.assertNotIn("Application().run", source)
        self.assertNotIn("win32com", source)
        self.assertNotIn(".Display(", source)
        self.assertNotIn(".Send(", source)
        self.assertLess(
            body.index("sin cambios (detect-only)"),
            body.index("publish_state = load_publish_state()"),
        )
        self.assertLess(
            body.index("cambio detectado (detect-only)"),
            body.index("_run_stage("),
        )
        self.assertLess(
            body.index("cambio detectado (detect-only)"),
            body.index("save_state(state_payload)"),
        )
        self.assertIn("resolve_state_dir", source)
        self.assertIn("resolve_log_dir", source)

    def test_01_defaults_remain_productive(self) -> None:
        from src.config.config import (
            FBL1N_FUTURE_ENABLED,
            MAIL_AUTO_SEND,
            resolve_log_dir,
            resolve_state_dir,
        )

        self.assertFalse(FBL1N_FUTURE_ENABLED)
        self.assertFalse(MAIL_AUTO_SEND)
        state_env = os.getenv("RUTA_STATE", "").strip()
        log_env = os.getenv("RUTA_LOG", "").strip()
        if state_env:
            self.assertEqual(resolve_state_dir(), Path(state_env).resolve())
        else:
            self.assertEqual(resolve_state_dir(), (ROOT / "state").resolve())
        if log_env:
            self.assertEqual(resolve_log_dir(), Path(log_env).resolve())
        else:
            self.assertEqual(resolve_log_dir(), (ROOT / "logs").resolve())


class D7DetectOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from src.config.config import (
            CONCEPTOS_ADMIN_PATH,
            CONCEPTOS_PATH,
            CLP_USD_ACREEDOR_CONCEPTO_PATH,
            FBL1N_PATH,
            INPUT_DIR,
            MONEDA_PATH,
            OUTPUT_DIR,
            PUBLICATION_DIR,
            RESOURCES_DIR,
            SOCIEDADES_PATH,
        )
        from src.modules.fbl1n_fuentes.detection import (
            build_combined_state_payload,
            plan_source_detection,
        )
        from src.modules.fbl1n_fuentes.module import (
            combined_source_sha256,
            semantic_fbl1n_fingerprint,
        )
        import pandas as pd

        if not D1_HIST.is_file() or not D1_FUT.is_file():
            raise FileNotFoundError("Faltan copias D1 en temp/auditoria_dos_fbl1n_*")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls.work = ROOT / "temp" / f"d7_detect_only_{stamp}"
        for name in (
            "input",
            "output",
            "resources",
            "publication",
            "state_empty",
            "state_unchanged",
            "logs",
        ):
            (cls.work / name).mkdir(parents=True, exist_ok=True)
        (cls.work / "04_BI").mkdir(parents=True, exist_ok=True)

        catalogs = {
            "SOCIEDADES.xlsx": SOCIEDADES_PATH,
            "MONEDA.xlsx": MONEDA_PATH,
            "CONCEPTOS.xlsx": CONCEPTOS_PATH,
            "CONCEPTOS_ADMIN.xlsx": CONCEPTOS_ADMIN_PATH,
            "CLP_USD_ACREEDOR_CONCEPTO.xlsx": CLP_USD_ACREEDOR_CONCEPTO_PATH,
        }
        for name, source in catalogs.items():
            if not source.is_file():
                alt = RESOURCES_DIR / name
                source = alt
            if not source.is_file():
                raise FileNotFoundError(f"Preflight D7: falta recurso {name}")
            shutil.copy2(source, cls.work / "resources" / name)

        pago_me = INPUT_DIR / PAGO_ME_NAME
        if not pago_me.is_file():
            raise FileNotFoundError(f"Preflight D7: falta {PAGO_ME_NAME}")
        shutil.copy2(pago_me, cls.work / "input" / PAGO_ME_NAME)

        shutil.copy2(D1_HIST, cls.work / "input" / "FBL1N.xlsx")
        shutil.copy2(D1_FUT, cls.work / "input" / "FBL1N_FUTURO.xlsx")
        cls.d7_hist = cls.work / "input" / "FBL1N.xlsx"
        cls.d7_fut = cls.work / "input" / "FBL1N_FUTURO.xlsx"

        cls.hist_sha = _sha_file(cls.d7_hist)
        cls.fut_sha = _sha_file(cls.d7_fut)
        cls.d1_hist_sha = _sha_file(D1_HIST)
        cls.d1_fut_sha = _sha_file(D1_FUT)

        historical_df = pd.read_excel(cls.d7_hist)
        future_df = pd.read_excel(cls.d7_fut)
        semantic = semantic_fbl1n_fingerprint(future_df)
        cls.semantic_sha = semantic.sha256
        cls.combined_sha = combined_source_sha256(cls.hist_sha, semantic.sha256)
        hist_stat = cls.d7_hist.stat()
        hist_fp = {
            "path": str(cls.d7_hist.resolve()),
            "size": int(hist_stat.st_size),
            "mtime": datetime.fromtimestamp(hist_stat.st_mtime).isoformat(
                timespec="seconds"
            ),
            "mtime_ns": int(hist_stat.st_mtime_ns),
            "sha256": cls.hist_sha,
        }
        decision = plan_source_detection(
            future_enabled=True,
            historical_fp=hist_fp,
            last=None,
            historical_df=historical_df,
            future_df=future_df,
            future_file_sha256=cls.fut_sha,
            compensation_cutoff=date(2026, 12, 31),
        )
        fixture = build_combined_state_payload(
            historical_fp=hist_fp,
            decision=decision,
            started_at="2026-08-28T00:00:00",
            last_success_at="2026-08-28T00:00:01",
            fbl1n_rows=94238,
            matrix_rows=94238,
            months=["2026-09"],
            matriz="D7_FIXTURE_MATRIZ.xlsx",
            dinamicas="D7_FIXTURE_DINAMICAS.xlsx",
            actual="D7_FIXTURE_ACTUAL.xlsx",
            log="d7_fixture.log",
        )
        cls.unchanged_state = cls.work / "state_unchanged" / "last_fbl1n_state.json"
        cls.unchanged_state.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        cls.fixture_schema = fixture.get("schema_version")
        cls.fixture_mode = fixture.get("source_mode")
        cls.unchanged_before = _sig(cls.unchanged_state)

        prod_input = FBL1N_PATH if FBL1N_PATH.is_file() else INPUT_DIR / "FBL1N.xlsx"
        cls.prod_before = {
            "d1_hist": _sig(D1_HIST),
            "d1_fut": _sig(D1_FUT),
            "prod_fbl1n": _sig(prod_input),
            "prod_state": _sig(PROD_STATE),
            "prod_mail": _sig(PROD_MAIL),
            "prod_pub": _sig(PROD_PUB),
            "prod_lock": _sig(PROD_LOCK),
            "prod_app_log": _sig(PROD_APP_LOG),
            "orch_logs": _orch_log_names(),
            "output_inv": _dir_inventory(OUTPUT_DIR),
            "publication_inv": _dir_inventory(PUBLICATION_DIR),
        }
        cls.prod_input_path = prod_input
        cls.prod_output_dir = OUTPUT_DIR
        cls.prod_publication_dir = PUBLICATION_DIR
        cls.com_before = _com_pids()

        cls.empty_result = _run_child(
            cls.work,
            cls.work / "state_empty",
            cls.work / "logs" / "d7_empty_result.json",
        )
        cls.unchanged_result = _run_child(
            cls.work,
            cls.work / "state_unchanged",
            cls.work / "logs" / "d7_unchanged_result.json",
        )
        cls.com_after = _com_pids()
        cls.prod_after = {
            "d1_hist": _sig(D1_HIST),
            "d1_fut": _sig(D1_FUT),
            "prod_fbl1n": _sig(prod_input),
            "prod_state": _sig(PROD_STATE),
            "prod_mail": _sig(PROD_MAIL),
            "prod_pub": _sig(PROD_PUB),
            "prod_lock": _sig(PROD_LOCK),
            "prod_app_log": _sig(PROD_APP_LOG),
            "orch_logs": _orch_log_names(),
            "output_inv": _dir_inventory(OUTPUT_DIR),
            "publication_inv": _dir_inventory(PUBLICATION_DIR),
        }
        cls.unchanged_after = _sig(cls.unchanged_state)
        cls._write_summary()

    @classmethod
    def _write_summary(cls) -> None:
        empty_logs = _read_run_logs(cls.work / "logs")
        summary = {
            "stage": "D7",
            "work_dir": cls.work.name,
            "d6_mail_note": (
                "D6 Correo=1 fue payload/etapa simulada; "
                ".Display=0, .Send=0, Outlook COM=0."
            ),
            "detect_only_review": (
                "detect_only retorna tras preflight, estabilidad y detección; "
                "no llama _run_stage, save_state, publicación ni correo."
            ),
            "first_decision": cls.empty_result.get("decision"),
            "second_decision": cls.unchanged_result.get("decision"),
            "historical_sha256": cls.hist_sha,
            "future_file_sha256": cls.fut_sha,
            "future_semantic_sha256": cls.semantic_sha,
            "combined_source_sha256": cls.combined_sha,
            "future_valid_rows": cls.empty_result.get("future_valid_rows"),
            "future_invalid_rows": cls.empty_result.get("future_invalid_rows"),
            "latest_compensation_date": cls.empty_result.get(
                "latest_compensation_date"
            ),
            "files": _list_files(cls.work),
            "empty": {
                "decision": cls.empty_result.get("decision"),
                "message": cls.empty_result.get("message"),
                "state_files": cls.empty_result.get("state_files"),
                "output_files": cls.empty_result.get("output_files"),
                "publication_files": cls.empty_result.get("publication_files"),
            },
            "unchanged": {
                "decision": cls.unchanged_result.get("decision"),
                "message": cls.unchanged_result.get("message"),
                "state_files": cls.unchanged_result.get("state_files"),
                "output_files": cls.unchanged_result.get("output_files"),
                "publication_files": cls.unchanged_result.get("publication_files"),
            },
            "log_needles": {
                needle: (needle in empty_logs)
                for needle in FORBIDDEN_LOG
            },
            "productive_unchanged": cls.prod_before == cls.prod_after,
            "new_com_pids": sorted(cls.com_after - cls.com_before),
        }
        path = cls.work / "d7_summary.json"
        path.write_text(
            _sanitize(json.dumps(summary, indent=2, ensure_ascii=False)),
            encoding="utf-8",
        )

    def test_02_d7_copies_match_d1_hashes(self) -> None:
        self.assertEqual(self.d7_hist.name, "FBL1N.xlsx")
        self.assertEqual(self.d7_fut.name, "FBL1N_FUTURO.xlsx")
        self.assertNotEqual(self.d7_hist.name, "FBL1N..XLSX")
        self.assertEqual(self.hist_sha, self.d1_hist_sha)
        self.assertEqual(self.fut_sha, self.d1_fut_sha)
        self.assertEqual(self.hist_sha, EXPECTED_HIST)
        self.assertEqual(self.fut_sha, EXPECTED_FUT)
        self.assertEqual(self.semantic_sha, EXPECTED_SEM)
        self.assertEqual(self.combined_sha, EXPECTED_COMB)

    def test_03_fixture_is_official_v2(self) -> None:
        payload = json.loads(self.unchanged_state.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "2")
        self.assertEqual(payload["source_mode"], "historical_plus_future")
        self.assertEqual(payload["latest_compensation_date"], "2026-09-02")
        self.assertEqual(payload["historical_file_sha256"], EXPECTED_HIST)
        self.assertEqual(payload["future_file_sha256"], EXPECTED_FUT)
        self.assertEqual(payload["future_semantic_sha256"], EXPECTED_SEM)
        self.assertEqual(payload["combined_source_sha256"], EXPECTED_COMB)
        self.assertEqual(self.fixture_schema, "2")
        self.assertEqual(self.fixture_mode, "historical_plus_future")

    def test_04_empty_state_is_changed(self) -> None:
        result = self.empty_result
        self.assertTrue(result.get("ok"), result.get("error") or result.get("stderr"))
        self.assertEqual(result.get("returncode"), 0)
        self.assertEqual(result.get("decision"), "Changed")
        self.assertEqual(result.get("message"), "cambio detectado (detect-only)")
        self.assertFalse(result.get("skipped"))
        self.assertEqual(result.get("sha256"), EXPECTED_HIST)
        self.assertEqual(result.get("combined_source_sha256"), EXPECTED_COMB)
        self.assertEqual(result.get("future_semantic_sha256"), EXPECTED_SEM)
        self.assertEqual(result.get("future_valid_rows"), 3203)
        self.assertEqual(result.get("future_invalid_rows"), 1)
        self.assertEqual(result.get("latest_compensation_date"), "2026-09-02")
        self.assertEqual(result.get("publish_status"), "")
        self.assertEqual(result.get("mail_status"), "")
        self.assertTrue(result.get("future_enabled"))
        self.assertFalse(result.get("mail_auto_send"))
        self.assertEqual(result.get("input_name"), "FBL1N.xlsx")
        state_files = list(result.get("state_files") or [])
        self.assertNotIn("last_fbl1n_state.json", state_files)
        self.assertEqual(list(result.get("output_files") or []), [])
        self.assertEqual(list(result.get("publication_files") or []), [])

    def test_05_combined_state_is_unchanged(self) -> None:
        result = self.unchanged_result
        self.assertTrue(result.get("ok"), result.get("error") or result.get("stderr"))
        self.assertEqual(result.get("returncode"), 0)
        self.assertEqual(result.get("decision"), "Unchanged")
        self.assertEqual(result.get("message"), "sin cambios (detect-only)")
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("publish_status"), "")
        self.assertEqual(result.get("mail_status"), "")
        self.assertEqual(list(result.get("output_files") or []), [])
        self.assertEqual(list(result.get("publication_files") or []), [])
        self.assertEqual(self.unchanged_before, self.unchanged_after)

    def test_06_no_productive_stages_or_com(self) -> None:
        logs = _read_run_logs(self.work / "logs")
        for needle in FORBIDDEN_LOG:
            self.assertNotIn(needle, logs)
        self.assertNotIn("MATRIZ_FBL1N_", logs)
        self.assertNotIn("DINAMICAS_FINALES_", "".join(_list_files(self.work / "output")))
        self.assertEqual(self.com_after - self.com_before, set())
        self.assertEqual(self.prod_before, self.prod_after)

    def test_07_d7_tree_exists(self) -> None:
        for name in (
            "input",
            "output",
            "resources",
            "publication",
            "state_empty",
            "state_unchanged",
            "logs",
        ):
            self.assertTrue((self.work / name).is_dir(), name)
        self.assertTrue((self.work / "d7_summary.json").is_file())
        self.assertTrue((self.work / "logs" / "d7_empty_result.json").is_file())
        self.assertTrue((self.work / "logs" / "d7_unchanged_result.json").is_file())


def _read_run_logs(log_dir: Path) -> str:
    chunks: list[str] = []
    if not log_dir.is_dir():
        return ""
    for path in sorted(log_dir.glob("*")):
        if path.suffix.lower() not in {".log", ".json", ".txt"}:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--child":
        raise SystemExit(_child_main(Path(sys.argv[2])))
    unittest.main()
