"""Migración genérica de identidad semántica FBL1N (schema 2 → v2).

Por defecto solo valida (dry-run). --apply escribe únicamente
last_fbl1n_state.json. last_publish_state.json y last_mail_state.json
no se tocan. No es una corrida de pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.fbl1n_fuentes.detection import (  # noqa: E402
    has_v2_identity,
    is_combined_state,
)
from src.modules.fbl1n_fuentes.module import (  # noqa: E402
    EXPECTED_COLUMNS,
    FECHA_COMP_COL,
    IDENTITY_VERSION_V2,
    combined_semantic_sha256,
    combined_source_sha256_v1,
    semantic_fbl1n_fingerprint,
)

FBL1N_STATE_NAME = "last_fbl1n_state.json"
PUBLISH_STATE_NAME = "last_publish_state.json"
MAIL_STATE_NAME = "last_mail_state.json"
LOCK_NAME = "pipeline.lock"
MANIFEST_NAME = "manifest.json"
FBL1N_STATE_TMP_NAME = "last_fbl1n_state.json.tmp"
FBL1N_ROLLBACK_TMP_NAME = "last_fbl1n_state.json.rollback.tmp"
MANIFEST_TMP_NAME = "manifest.json.tmp"
KNOWN_TMP_NAMES = frozenset(
    {
        FBL1N_STATE_TMP_NAME,
        FBL1N_ROLLBACK_TMP_NAME,
        MANIFEST_TMP_NAME,
    }
)
PUBLISH_SUCCEEDED = "Succeeded"
MAIL_PENDING = "Pending"
MIGRATION_KIND = "semantic_identity_v2"
STATUS_PREPARED = "prepared"
STATUS_APPLIED = "applied"
STATUS_ROLLED_BACK = "rolled_back"
VALID_STATUSES = frozenset(
    {STATUS_PREPARED, STATUS_APPLIED, STATUS_ROLLED_BACK}
)


class MigrationError(Exception):
    """Precheck o contrato inválido; no se escribe state."""


@dataclass
class MigrationConfig:
    historical: Path
    future: Path
    matriz: Path
    output_actual: Path
    published_actual: Path
    state_dir: Path
    backup_dir: Path | None
    expected_historical_semantic_sha256: str
    expected_future_file_sha256: str
    expected_future_semantic_sha256: str
    expected_legacy_historical_file_sha256: str
    expected_legacy_combined_source_sha256: str
    matriz_expected_rows: int
    future_compensation_date: str | None = None
    apply: bool = False
    rollback: bool = False


@dataclass
class MigrationResult:
    ok: bool
    applied: bool = False
    rolled_back: bool = False
    message: str = ""
    written: list[str] = field(default_factory=list)
    payload: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_meta(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def encode_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def unlink_known_tmp(path: Path) -> None:
    if path.name not in KNOWN_TMP_NAMES:
        raise MigrationError(f"Temporal no reconocido: {path.name}")
    if path.name in {FBL1N_STATE_NAME, PUBLISH_STATE_NAME, MAIL_STATE_NAME}:
        raise MigrationError("No se borra un state live.")
    if path.is_file():
        path.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if tmp.name not in KNOWN_TMP_NAMES:
        raise MigrationError(f"Temporal no reconocido: {tmp.name}")
    try:
        tmp.write_bytes(encode_json(payload))
        loaded = json.loads(tmp.read_text(encoding="utf-8"))
        if loaded != payload:
            raise MigrationError("El JSON temporal no coincide con el payload.")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            unlink_known_tmp(tmp)
        raise


def worksheet_xml_shas(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with zipfile.ZipFile(path) as handle:
        for name in handle.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                out[name] = hashlib.sha256(handle.read(name)).hexdigest()
    return out


def assert_ooxml(path: Path, label: str) -> None:
    if not path.is_file():
        raise MigrationError(f"{label} inexistente: {path.name}")
    if not zipfile.is_zipfile(path):
        raise MigrationError(f"{label} no es OOXML válido: {path.name}")
    with zipfile.ZipFile(path) as handle:
        bad = handle.testzip()
        if bad:
            raise MigrationError(f"{label} ZIP corrupto ({bad}): {path.name}")


def assert_mail_auto_send_false() -> None:
    raw = str(os.environ.get("MAIL_AUTO_SEND", "")).strip().lower()
    if raw != "false":
        raise MigrationError(
            "MAIL_AUTO_SEND debe ser false en el entorno; no se migra."
        )


def assert_no_lock(state_dir: Path) -> None:
    lock = state_dir / LOCK_NAME
    if lock.exists():
        raise MigrationError(f"Existe {LOCK_NAME}; no se migra.")


def create_exclusive_backup_dir(backup_dir: Path) -> None:
    if backup_dir.exists():
        raise MigrationError(
            "--backup-dir ya existe; no se reutiliza ni se sobrescribe."
        )
    try:
        backup_dir.mkdir(parents=True)
    except FileExistsError as exc:
        raise MigrationError(
            "--backup-dir ya existe; no se reutiliza ni se sobrescribe."
        ) from exc


def _fingerprint_excel(path: Path) -> Any:
    frame = pd.read_excel(path)
    return semantic_fbl1n_fingerprint(frame)


def _matriz_historical_semantic(
    matriz_path: Path,
    *,
    expected_rows: int,
    future_compensation_date: str | None,
) -> Any:
    frame = pd.read_excel(matriz_path, sheet_name="MATRIZ_FBL1N")
    if len(frame) != expected_rows:
        raise MigrationError(
            f"MATRIZ filas={len(frame)}; se esperaban {expected_rows}."
        )
    hist21 = frame.iloc[:, :21].copy()
    hist21.columns = list(EXPECTED_COLUMNS)
    if future_compensation_date:
        from src.modules.fbl1n_fuentes.module import _canonical_date

        mask = hist21[FECHA_COMP_COL].map(_canonical_date) == future_compensation_date
        hist21 = hist21.loc[~mask].copy()
    return semantic_fbl1n_fingerprint(hist21)


def validate_sources(cfg: MigrationConfig) -> dict[str, Any]:
    assert_ooxml(cfg.historical, "Histórico")
    assert_ooxml(cfg.future, "Futuro")
    assert_ooxml(cfg.matriz, "MATRIZ")
    assert_ooxml(cfg.output_actual, "ACTUAL output")
    assert_ooxml(cfg.published_actual, "ACTUAL publicado")

    hist_sem = _fingerprint_excel(cfg.historical)
    fut_sem = _fingerprint_excel(cfg.future)
    fut_file = sha256_file(cfg.future)
    if hist_sem.sha256 != cfg.expected_historical_semantic_sha256:
        raise MigrationError("Semántica histórica actual no coincide con la esperada.")
    if fut_file != cfg.expected_future_file_sha256:
        raise MigrationError("SHA físico del futuro no coincide con el esperado.")
    if fut_sem.sha256 != cfg.expected_future_semantic_sha256:
        raise MigrationError("Semántica futura actual no coincide con la esperada.")

    matriz_sem = _matriz_historical_semantic(
        cfg.matriz,
        expected_rows=cfg.matriz_expected_rows,
        future_compensation_date=cfg.future_compensation_date,
    )
    if matriz_sem.sha256 != hist_sem.sha256:
        raise MigrationError(
            "Las filas históricas de MATRIZ no coinciden con el FBL1N actual."
        )

    out_sheets = worksheet_xml_shas(cfg.output_actual)
    pub_sheets = worksheet_xml_shas(cfg.published_actual)
    if out_sheets != pub_sheets:
        raise MigrationError(
            "ACTUAL output y publicado no tienen worksheets equivalentes."
        )
    if len(out_sheets) != 16:
        raise MigrationError(
            f"ACTUAL no tiene 16 worksheets; tiene {len(out_sheets)}."
        )
    return {
        "historical_semantic": hist_sem,
        "future_semantic": fut_sem,
        "historical_meta": file_meta(cfg.historical),
        "future_file_sha256": fut_file,
    }


def validate_states(cfg: MigrationConfig) -> dict[str, Any]:
    fbl1n_path = cfg.state_dir / FBL1N_STATE_NAME
    publish_path = cfg.state_dir / PUBLISH_STATE_NAME
    mail_path = cfg.state_dir / MAIL_STATE_NAME
    for path, label in (
        (fbl1n_path, FBL1N_STATE_NAME),
        (publish_path, PUBLISH_STATE_NAME),
        (mail_path, MAIL_STATE_NAME),
    ):
        if not path.is_file():
            raise MigrationError(f"Falta {label}.")
    last = load_json(fbl1n_path)
    publish = load_json(publish_path)
    mail = load_json(mail_path)
    if has_v2_identity(last):
        raise MigrationError("El state ya está migrado (identity_version v2).")
    if not is_combined_state(last):
        raise MigrationError("El state no es combinado schema 2; no se migra.")
    legacy_hist = str(last.get("historical_file_sha256") or "")
    legacy_combined = str(last.get("combined_source_sha256") or "")
    if legacy_hist != cfg.expected_legacy_historical_file_sha256:
        raise MigrationError("historical_file_sha256 legado no coincide.")
    if legacy_combined != cfg.expected_legacy_combined_source_sha256:
        raise MigrationError("combined_source_sha256 legado no coincide.")
    recomputed_v1 = combined_source_sha256_v1(
        legacy_hist, cfg.expected_future_semantic_sha256
    )
    if recomputed_v1 != legacy_combined:
        raise MigrationError("La identidad v1 de P3.2 no se recompone.")
    if str(last.get("future_semantic_sha256") or "") != cfg.expected_future_semantic_sha256:
        raise MigrationError("future_semantic_sha256 del state no coincide.")
    if int(last.get("matrix_rows") or 0) != cfg.matriz_expected_rows:
        raise MigrationError("matrix_rows del state no coincide.")
    if str(publish.get("source_fbl1n_sha256") or "") != legacy_combined:
        raise MigrationError("last_publish_state no corresponde a la identidad legado.")
    if str(publish.get("publish_status") or "") != PUBLISH_SUCCEEDED:
        raise MigrationError("last_publish_state no está Succeeded.")
    if str(mail.get("source_fbl1n_sha256") or "") != legacy_combined:
        raise MigrationError("last_mail_state no corresponde a la identidad legado.")
    if str(mail.get("mail_status") or "") != MAIL_PENDING:
        raise MigrationError("last_mail_state no está Pending.")
    return {
        "last": last,
        "publish": publish,
        "mail": mail,
        "fbl1n_path": fbl1n_path,
        "publish_path": publish_path,
        "mail_path": mail_path,
        "fbl1n_sha256_before": sha256_file(fbl1n_path),
        "publish_meta": file_meta(publish_path),
        "mail_meta": file_meta(mail_path),
    }


def build_migrated_payload(
    last: dict[str, Any],
    *,
    historical_meta: dict[str, Any],
    historical_semantic_sha256: str,
    future_semantic_sha256: str,
    future_file_sha256: str,
) -> dict[str, Any]:
    combined_sem = combined_semantic_sha256(
        historical_semantic_sha256, future_semantic_sha256
    )
    payload = dict(last)
    payload["schema_version"] = str(last.get("schema_version") or "2")
    payload["identity_version"] = IDENTITY_VERSION_V2
    payload["sha256"] = historical_meta["sha256"]
    payload["size"] = historical_meta["size"]
    payload["mtime"] = historical_meta["mtime"]
    payload["mtime_ns"] = historical_meta["mtime_ns"]
    payload["historical_file_sha256"] = historical_meta["sha256"]
    payload["historical_semantic_sha256"] = historical_semantic_sha256
    payload["future_file_sha256"] = future_file_sha256
    payload["future_semantic_sha256"] = future_semantic_sha256
    payload["combined_semantic_sha256"] = combined_sem
    payload["combined_source_sha256"] = last["combined_source_sha256"]
    payload["source_fbl1n_sha256"] = last.get(
        "source_fbl1n_sha256", last["combined_source_sha256"]
    )
    payload["legacy_historical_file_sha256"] = last.get("historical_file_sha256")
    payload["legacy_combined_source_sha256"] = last["combined_source_sha256"]
    payload["identity_migration"] = {
        "kind": MIGRATION_KIND,
        "at": datetime.now().isoformat(timespec="seconds"),
        "note": "migración de identidad; no es una corrida de pipeline",
    }
    return payload


def _validate_payload(payload: dict[str, Any], last: dict[str, Any]) -> None:
    json.dumps(payload)
    if not has_v2_identity(payload):
        raise MigrationError("El JSON temporal no tiene identidad v2.")
    frozen = (
        "last_success_at",
        "started_at",
        "matriz",
        "dinamicas",
        "actual",
        "log",
        "fbl1n_rows",
        "matrix_rows",
        "combined_source_sha256",
        "source_fbl1n_sha256",
    )
    for key in frozen:
        if payload.get(key) != last.get(key) and key in last:
            raise MigrationError(f"El temporal alteró el campo congelado {key}.")
    if payload.get("months") != last.get("months"):
        raise MigrationError("El temporal alteró months.")


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = (
        "migration_id",
        "kind",
        "status",
        "fbl1n_sha256_before",
        "fbl1n_sha256_after",
        "backup_hashes",
        "publish_sha256_expected",
        "mail_sha256_expected",
        "paths",
        "prepared_at",
        "applied_at",
        "rolled_back_at",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise MigrationError(f"Manifest incompleto: {missing}.")
    try:
        uuid.UUID(str(manifest["migration_id"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MigrationError("migration_id del manifest no es un UUID.") from exc
    if str(manifest.get("kind") or "") != MIGRATION_KIND:
        raise MigrationError("kind del manifest inválido.")
    status = str(manifest.get("status") or "")
    if status not in VALID_STATUSES:
        raise MigrationError(f"status del manifest inválido: {status}.")
    backups = manifest.get("backup_hashes")
    if not isinstance(backups, dict):
        raise MigrationError("backup_hashes del manifest inválido.")
    for name in (FBL1N_STATE_NAME, PUBLISH_STATE_NAME, MAIL_STATE_NAME):
        digest = str(backups.get(name) or "")
        if len(digest) != 64:
            raise MigrationError(f"Hash de backup ausente o inválido: {name}.")
    if not isinstance(manifest.get("paths"), dict):
        raise MigrationError("paths del manifest inválido.")
    before = str(manifest.get("fbl1n_sha256_before") or "")
    after = str(manifest.get("fbl1n_sha256_after") or "")
    if len(before) != 64 or len(after) != 64:
        raise MigrationError("SHA before/after del manifest inválidos.")
    if status == STATUS_PREPARED:
        if manifest.get("applied_at") is not None or manifest.get("rolled_back_at") is not None:
            raise MigrationError("Manifest prepared no debe tener applied_at/rolled_back_at.")
    if status == STATUS_APPLIED and not manifest.get("applied_at"):
        raise MigrationError("Manifest applied sin applied_at.")
    if status == STATUS_ROLLED_BACK and not manifest.get("rolled_back_at"):
        raise MigrationError("Manifest rolled_back sin rolled_back_at.")


def load_valid_manifest(backup_dir: Path) -> dict[str, Any]:
    path = backup_dir / MANIFEST_NAME
    if not path.is_file():
        raise MigrationError("Manifest ausente; no se restaura.")
    manifest = load_json(path)
    validate_manifest(manifest)
    return manifest


def cli_paths(cfg: MigrationConfig) -> dict[str, str]:
    return {
        "historical": str(cfg.historical) if cfg.historical else "",
        "future": str(cfg.future) if cfg.future else "",
        "matriz": str(cfg.matriz) if cfg.matriz else "",
        "output_actual": str(cfg.output_actual) if cfg.output_actual else "",
        "published_actual": str(cfg.published_actual) if cfg.published_actual else "",
        "state_dir": str(cfg.state_dir),
        "backup_dir": str(cfg.backup_dir) if cfg.backup_dir else "",
    }


def copy_backup_verified(source: Path, dest: Path) -> str:
    shutil.copy2(source, dest)
    digest = sha256_file(dest)
    if digest != sha256_file(source):
        raise MigrationError(f"Backup corrupto: {dest.name}")
    return digest


def read_live_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_file(path)


def assert_publish_mail_intact(
    publish_path: Path,
    mail_path: Path,
    publish_meta_before: dict[str, Any],
    mail_meta_before: dict[str, Any],
) -> None:
    publish_after = file_meta(publish_path)
    mail_after = file_meta(mail_path)
    if publish_after["sha256"] != publish_meta_before["sha256"]:
        raise MigrationError("last_publish_state.json cambió de SHA.")
    if mail_after["sha256"] != mail_meta_before["sha256"]:
        raise MigrationError("last_mail_state.json cambió de SHA.")
    if publish_after["mtime_ns"] != publish_meta_before["mtime_ns"]:
        raise MigrationError("last_publish_state.json cambió de mtime.")
    if mail_after["mtime_ns"] != mail_meta_before["mtime_ns"]:
        raise MigrationError("last_mail_state.json cambió de mtime.")
    if sha256_bytes(publish_path.read_bytes()) != publish_meta_before["sha256"]:
        raise MigrationError("last_publish_state.json cambió de bytes.")
    if sha256_bytes(mail_path.read_bytes()) != mail_meta_before["sha256"]:
        raise MigrationError("last_mail_state.json cambió de bytes.")


def apply_migration(
    cfg: MigrationConfig,
    *,
    last: dict[str, Any],
    payload: dict[str, Any],
    fbl1n_path: Path,
    publish_path: Path,
    mail_path: Path,
    fbl1n_sha256_before: str,
    publish_meta_before: dict[str, Any],
    mail_meta_before: dict[str, Any],
) -> None:
    if cfg.backup_dir is None:
        raise MigrationError("--backup-dir es obligatorio con --apply.")
    backup_dir = cfg.backup_dir
    live_now = read_live_sha(fbl1n_path)
    if live_now is None:
        raise MigrationError("El live state desapareció antes de crear el backup.")
    if live_now != fbl1n_sha256_before:
        raise MigrationError(
            "El live state cambió antes de crear el backup; se conserva el state de terceros."
        )

    create_exclusive_backup_dir(backup_dir)
    backup_hashes = {
        FBL1N_STATE_NAME: copy_backup_verified(
            fbl1n_path, backup_dir / FBL1N_STATE_NAME
        ),
        PUBLISH_STATE_NAME: copy_backup_verified(
            publish_path, backup_dir / PUBLISH_STATE_NAME
        ),
        MAIL_STATE_NAME: copy_backup_verified(
            mail_path, backup_dir / MAIL_STATE_NAME
        ),
    }
    if backup_hashes[FBL1N_STATE_NAME] != fbl1n_sha256_before:
        raise MigrationError("El backup del live state no coincide con SHA before.")

    tmp = fbl1n_path.with_name(FBL1N_STATE_TMP_NAME)
    replaced = False
    raw = encode_json(payload)
    fbl1n_sha256_after = sha256_bytes(raw)
    try:
        tmp.write_bytes(raw)
        loaded = json.loads(tmp.read_text(encoding="utf-8"))
        _validate_payload(loaded, last)
        if sha256_file(tmp) != fbl1n_sha256_after:
            raise MigrationError("El temporal no tiene el SHA after esperado.")

        manifest = {
            "migration_id": str(uuid.uuid4()),
            "kind": MIGRATION_KIND,
            "status": STATUS_PREPARED,
            "note": "migración de identidad; no es una corrida de pipeline",
            "fbl1n_sha256_before": fbl1n_sha256_before,
            "fbl1n_sha256_after": fbl1n_sha256_after,
            "backup_hashes": backup_hashes,
            "publish_sha256_expected": publish_meta_before["sha256"],
            "mail_sha256_expected": mail_meta_before["sha256"],
            "paths": cli_paths(cfg),
            "prepared_at": datetime.now().isoformat(timespec="seconds"),
            "applied_at": None,
            "rolled_back_at": None,
        }
        validate_manifest(manifest)
        write_json_atomic(backup_dir / MANIFEST_NAME, manifest)
        validate_manifest(load_json(backup_dir / MANIFEST_NAME))

        cas = read_live_sha(fbl1n_path)
        if cas is None:
            raise MigrationError(
                "El live state desapareció antes del replace; no se aplica."
            )
        if cas != fbl1n_sha256_before:
            raise MigrationError(
                "El live state cambió antes del replace; se conserva el state de terceros."
            )
        os.replace(tmp, fbl1n_path)
        replaced = True
    except Exception:
        if not replaced and tmp.exists():
            unlink_known_tmp(tmp)
        raise

    live_after = read_live_sha(fbl1n_path)
    if live_after != fbl1n_sha256_after:
        raise MigrationError(
            "Tras os.replace el live state no tiene el SHA after esperado."
        )
    assert_publish_mail_intact(
        publish_path,
        mail_path,
        publish_meta_before,
        mail_meta_before,
    )
    applied = load_json(backup_dir / MANIFEST_NAME)
    applied["status"] = STATUS_APPLIED
    applied["applied_at"] = datetime.now().isoformat(timespec="seconds")
    validate_manifest(applied)
    write_json_atomic(backup_dir / MANIFEST_NAME, applied)
    validate_manifest(load_json(backup_dir / MANIFEST_NAME))


def _restore_from_backup(
    *,
    dest: Path,
    backup: Path,
    expected_live_sha: str,
    expected_restored_sha: str,
) -> None:
    if not backup.is_file():
        raise MigrationError(f"Backup ausente: {FBL1N_STATE_NAME}")
    if sha256_file(backup) != expected_restored_sha:
        raise MigrationError("El backup no coincide con fbl1n_sha256_before.")
    tmp = dest.with_name(FBL1N_ROLLBACK_TMP_NAME)
    try:
        shutil.copy2(backup, tmp)
        if sha256_file(tmp) != expected_restored_sha:
            raise MigrationError("El temporal de rollback no coincide con SHA before.")
        cas = read_live_sha(dest)
        if cas is None:
            raise MigrationError(
                "El live state desapareció durante el rollback; no se restaura a ciegas."
            )
        if cas != expected_live_sha:
            raise MigrationError(
                "El live state cambió durante el rollback; se conserva el state de terceros."
            )
        os.replace(tmp, dest)
    except Exception:
        if tmp.exists():
            unlink_known_tmp(tmp)
        raise
    restored = read_live_sha(dest)
    if restored != expected_restored_sha:
        raise MigrationError("Tras rollback el live state no tiene SHA before.")


def rollback_fbl1n_state(state_dir: Path, backup_dir: Path) -> MigrationResult:
    manifest = load_valid_manifest(backup_dir)
    dest = state_dir / FBL1N_STATE_NAME
    backup = backup_dir / FBL1N_STATE_NAME
    publish_backup = backup_dir / PUBLISH_STATE_NAME
    mail_backup = backup_dir / MAIL_STATE_NAME
    publish_live = state_dir / PUBLISH_STATE_NAME
    mail_live = state_dir / MAIL_STATE_NAME
    publish_meta = file_meta(publish_live) if publish_live.is_file() else None
    mail_meta = file_meta(mail_live) if mail_live.is_file() else None

    status = str(manifest["status"])
    before = str(manifest["fbl1n_sha256_before"])
    after = str(manifest["fbl1n_sha256_after"])
    if status == STATUS_ROLLED_BACK:
        raise MigrationError("La migración ya fue revertida (consumida).")

    live_sha = read_live_sha(dest)
    if live_sha is None:
        raise MigrationError("El live state no existe; no se restaura a ciegas.")

    if live_sha != before and live_sha != after:
        raise MigrationError(
            "El state live no corresponde a esta migración; "
            "existe state posterior o de terceros."
        )

    if live_sha == before:
        message = (
            "Apply no alcanzó el replace; live intacto (SHA before)."
            if status == STATUS_PREPARED
            else "Live ya restaurado (SHA before); no se sobrescribe."
        )
        return MigrationResult(
            ok=True,
            rolled_back=False,
            message=message,
        )

    if live_sha == after and status in {STATUS_APPLIED, STATUS_PREPARED}:
        if publish_meta is None or mail_meta is None:
            raise MigrationError("Faltan publish/mail live durante el rollback.")
        _restore_from_backup(
            dest=dest,
            backup=backup,
            expected_live_sha=after,
            expected_restored_sha=before,
        )
        assert_publish_mail_intact(
            publish_live,
            mail_live,
            publish_meta,
            mail_meta,
        )
        if sha256_file(publish_backup) != str(
            manifest["backup_hashes"][PUBLISH_STATE_NAME]
        ):
            raise MigrationError("Backup de publish alterado; no se toca el live publish.")
        if sha256_file(mail_backup) != str(manifest["backup_hashes"][MAIL_STATE_NAME]):
            raise MigrationError("Backup de mail alterado; no se toca el live mail.")
        updated = load_json(backup_dir / MANIFEST_NAME)
        updated["status"] = STATUS_ROLLED_BACK
        updated["rolled_back_at"] = datetime.now().isoformat(timespec="seconds")
        validate_manifest(updated)
        write_json_atomic(backup_dir / MANIFEST_NAME, updated)
        validate_manifest(load_json(backup_dir / MANIFEST_NAME))
        return MigrationResult(
            ok=True,
            rolled_back=True,
            message="Rollback de last_fbl1n_state.json aplicado.",
            written=[FBL1N_STATE_NAME],
        )

    raise MigrationError("Combinación de manifest y live state no restaurable.")


def run(cfg: MigrationConfig) -> MigrationResult:
    if cfg.apply and cfg.rollback:
        raise MigrationError("--apply y --rollback son mutuamente excluyentes.")
    if cfg.rollback:
        if cfg.backup_dir is None:
            raise MigrationError("--backup-dir es obligatorio con --rollback.")
        return rollback_fbl1n_state(cfg.state_dir, cfg.backup_dir)

    assert_mail_auto_send_false()
    assert_no_lock(cfg.state_dir)
    sources = validate_sources(cfg)
    states = validate_states(cfg)
    payload = build_migrated_payload(
        states["last"],
        historical_meta=sources["historical_meta"],
        historical_semantic_sha256=sources["historical_semantic"].sha256,
        future_semantic_sha256=sources["future_semantic"].sha256,
        future_file_sha256=sources["future_file_sha256"],
    )
    _validate_payload(payload, states["last"])
    sha_after = sha256_bytes(encode_json(payload))
    if not cfg.apply:
        return MigrationResult(
            ok=True,
            applied=False,
            message="Dry-run OK; no se escribió nada.",
            payload=payload,
        )
    apply_migration(
        cfg,
        last=states["last"],
        payload=payload,
        fbl1n_path=states["fbl1n_path"],
        publish_path=states["publish_path"],
        mail_path=states["mail_path"],
        fbl1n_sha256_before=states["fbl1n_sha256_before"],
        publish_meta_before=states["publish_meta"],
        mail_meta_before=states["mail_meta"],
    )
    live_sha = sha256_file(states["fbl1n_path"])
    if live_sha != sha_after:
        raise MigrationError("El live state no tiene el SHA after calculado.")
    return MigrationResult(
        ok=True,
        applied=True,
        message="Migración aplicada; solo last_fbl1n_state.json fue reemplazado.",
        written=[FBL1N_STATE_NAME],
        payload=payload,
    )


def parse_args(argv: list[str] | None = None) -> MigrationConfig:
    parser = argparse.ArgumentParser(
        description="Migrar last_fbl1n_state.json a identidad semántica v2."
    )
    parser.add_argument("--historical", type=Path)
    parser.add_argument("--future", type=Path)
    parser.add_argument("--matriz", type=Path)
    parser.add_argument("--output-actual", type=Path)
    parser.add_argument("--published-actual", type=Path)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--expected-historical-semantic-sha256")
    parser.add_argument("--expected-future-file-sha256")
    parser.add_argument("--expected-future-semantic-sha256")
    parser.add_argument("--expected-legacy-historical-file-sha256")
    parser.add_argument("--expected-legacy-combined-source-sha256")
    parser.add_argument("--matriz-expected-rows", type=int)
    parser.add_argument("--future-compensation-date")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    raw = parser.parse_args(argv)
    if raw.rollback:
        return MigrationConfig(
            historical=Path(),
            future=Path(),
            matriz=Path(),
            output_actual=Path(),
            published_actual=Path(),
            state_dir=raw.state_dir,
            backup_dir=raw.backup_dir,
            expected_historical_semantic_sha256="",
            expected_future_file_sha256="",
            expected_future_semantic_sha256="",
            expected_legacy_historical_file_sha256="",
            expected_legacy_combined_source_sha256="",
            matriz_expected_rows=0,
            rollback=True,
        )
    required = [
        raw.historical,
        raw.future,
        raw.matriz,
        raw.output_actual,
        raw.published_actual,
        raw.expected_historical_semantic_sha256,
        raw.expected_future_file_sha256,
        raw.expected_future_semantic_sha256,
        raw.expected_legacy_historical_file_sha256,
        raw.expected_legacy_combined_source_sha256,
        raw.matriz_expected_rows,
    ]
    if any(item in (None, "") for item in required):
        raise MigrationError("Faltan argumentos obligatorios para validar/aplicar.")
    return MigrationConfig(
        historical=raw.historical,
        future=raw.future,
        matriz=raw.matriz,
        output_actual=raw.output_actual,
        published_actual=raw.published_actual,
        state_dir=raw.state_dir,
        backup_dir=raw.backup_dir,
        expected_historical_semantic_sha256=str(
            raw.expected_historical_semantic_sha256
        ).lower(),
        expected_future_file_sha256=str(raw.expected_future_file_sha256).lower(),
        expected_future_semantic_sha256=str(
            raw.expected_future_semantic_sha256
        ).lower(),
        expected_legacy_historical_file_sha256=str(
            raw.expected_legacy_historical_file_sha256
        ).lower(),
        expected_legacy_combined_source_sha256=str(
            raw.expected_legacy_combined_source_sha256
        ).lower(),
        matriz_expected_rows=int(raw.matriz_expected_rows),
        future_compensation_date=raw.future_compensation_date,
        apply=bool(raw.apply),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        cfg = parse_args(argv)
        result = run(cfg)
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
