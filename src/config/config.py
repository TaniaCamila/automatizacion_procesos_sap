from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Iterable

PROJECT_NAME: str = "Automatizacion_FBL1N"
VERSION: str = "1.0.0"
AUTHOR: str = "Tania Herrera"

ROOT_DIR: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT_DIR / "data"
_DEFAULT_LOG_DIR: Path = ROOT_DIR / "logs"
LOG_DIR: Path = _DEFAULT_LOG_DIR
TEMP_DIR: Path = ROOT_DIR / "temp"
_DEFAULT_STATE_DIR: Path = ROOT_DIR / "state"
_ENV_FILE: Path = ROOT_DIR / ".env"


def _parse_dotenv_line(line: str) -> tuple[str, str]:
    """Parsear una línea de archivo .env en clave y valor."""
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    return key, value


def _load_dotenv(file_path: Path) -> None:
    """Cargar variables de entorno desde un archivo .env si existe."""
    if not file_path.is_file():
        return

    with file_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = _parse_dotenv_line(stripped)
            if key not in os.environ:
                os.environ[key] = value


def _env_str(name: str, default: str = "") -> str:
    """Leer variable de entorno como texto recortado."""

    return os.getenv(name, default).strip().strip('"').strip("'")


def _env_bool_strict(name: str, *, default: bool = False) -> bool:
    """
    Booleano estricto. Solo true/1/yes/on (cualquier capitalización) → True.

    Ausencia, vacío o cualquier otro valor → default (False).
    Nunca interpreta ausencia como True.
    """

    raw = _env_str(name).lower()
    if not raw:
        return default
    if raw in {"true", "1", "yes", "on"}:
        return True
    return False


_ISO_DATE_ENV_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _env_iso_date_optional(name: str) -> date | None:
    """YYYY-MM-DD opcional. Vacío → None. Valor inválido → ValueError (fail-closed)."""

    raw = _env_str(name)
    if not raw:
        return None
    match = _ISO_DATE_ENV_RE.fullmatch(raw)
    if match is None:
        raise ValueError(
            f"{name} inválido ({raw!r}); se exige YYYY-MM-DD."
        )
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError(
            f"{name} inválido ({raw!r}); no es una fecha calendario."
        ) from exc


def _resolve_dir(env_name: str, fallback: Path) -> Path:
    """
    Resolver directorio desde variable de entorno.

    - Absoluta → se usa directamente.
    - Relativa → respecto de ROOT_DIR.
    - Vacía / ausente → fallback del proyecto.
    """
    raw = os.getenv(env_name, "").strip().strip('"').strip("'")
    if not raw:
        return fallback.resolve()
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def resolve_log_dir() -> Path:
    """Directorio de logs: `RUTA_LOG` o `ROOT_DIR/logs`. Se evalúa en cada llamada."""

    return _resolve_dir("RUTA_LOG", _DEFAULT_LOG_DIR)


def resolve_state_dir() -> Path:
    """Directorio de state: `RUTA_STATE` o `ROOT_DIR/state`. Se evalúa en cada llamada."""

    return _resolve_dir("RUTA_STATE", _DEFAULT_STATE_DIR)


def _create_directories(paths: Iterable[Path]) -> None:
    """Crear directorios del proyecto si no existen."""
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


# Cargar .env antes de construir rutas operativas.
_load_dotenv(_ENV_FILE)

INPUT_DIR: Path = _resolve_dir("RUTA_INPUT", DATA_DIR / "input")
MASTER_DIR: Path = _resolve_dir("RUTA_MASTER", DATA_DIR / "master")
OUTPUT_DIR: Path = _resolve_dir("RUTA_OUTPUT", DATA_DIR / "output")
RESOURCES_DIR: Path = _resolve_dir("RUTA_RECURSOS", DATA_DIR / "resources")
PUBLICATION_DIR: Path = _resolve_dir(
    "RUTA_PUBLICACION",
    INPUT_DIR.parent / "REPORTE QUERY MENSUAL",
)
# Vacío / ausente → rutas productivas del repo. Solo tests/aislamiento las redirigen.
LOG_DIR = _resolve_dir("RUTA_LOG", _DEFAULT_LOG_DIR)
STATE_DIR = _resolve_dir("RUTA_STATE", _DEFAULT_STATE_DIR)

MAIL_SENDER_ACCOUNT: str = _env_str("MAIL_SENDER_ACCOUNT")
MAIL_TO: str = _env_str("MAIL_TO")
MAIL_CC: str = _env_str("MAIL_CC")
MAIL_BCC: str = _env_str("MAIL_BCC")
MAIL_AUTO_SEND: bool = _env_bool_strict("MAIL_AUTO_SEND", default=False)
MAIL_SHAREPOINT_LINK: str = _env_str("MAIL_SHAREPOINT_LINK")
MAIL_POWERBI_LINK: str = _env_str("MAIL_POWERBI_LINK")

FBL1N_FILE: str = "FBL1N.xlsx"
FBL1N_FUTURE_FILE: str = "FBL1N_FUTURO.xlsx"
FBL1N_FUTURE_ENABLED: bool = _env_bool_strict("FBL1N_FUTURE_ENABLED", default=False)
# Corte de cierre (modo futuro). Ausente → None; el orquestador futuro lo exige.
FBL1N_COMPENSATION_CUTOFF: date | None = _env_iso_date_optional(
    "FBL1N_COMPENSATION_CUTOFF"
)
SOCIEDADES_FILE: str = "SOCIEDADES.xlsx"
MONEDA_FILE: str = "MONEDA.xlsx"
CONCEPTOS_FILE: str = "CONCEPTOS.xlsx"
CONCEPTOS_ADMIN_FILE: str = "CONCEPTOS_ADMIN.xlsx"
CLP_USD_ACREEDOR_CONCEPTO_FILE: str = "CLP_USD_ACREEDOR_CONCEPTO.xlsx"

FBL1N_PATH: Path = INPUT_DIR / FBL1N_FILE
FBL1N_FUTURE_PATH: Path = _resolve_dir(
    "FBL1N_FUTURE_PATH",
    INPUT_DIR / FBL1N_FUTURE_FILE,
)
SOCIEDADES_PATH: Path = RESOURCES_DIR / SOCIEDADES_FILE
MONEDA_PATH: Path = RESOURCES_DIR / MONEDA_FILE
CONCEPTOS_PATH: Path = RESOURCES_DIR / CONCEPTOS_FILE
CONCEPTOS_ADMIN_PATH: Path = RESOURCES_DIR / CONCEPTOS_ADMIN_FILE
CLP_USD_ACREEDOR_CONCEPTO_PATH: Path = (
    RESOURCES_DIR / CLP_USD_ACREEDOR_CONCEPTO_FILE
)

_DIRECTORIES: tuple[Path, ...] = (
    DATA_DIR,
    INPUT_DIR,
    MASTER_DIR,
    OUTPUT_DIR,
    RESOURCES_DIR,
    LOG_DIR,
    STATE_DIR,
    TEMP_DIR,
)

_create_directories(_DIRECTORIES)


class Config:
    """Configuración centralizada y de solo lectura del proyecto."""

    __slots__: tuple[str, ...] = ()

    @property
    def root_dir(self) -> Path:
        return ROOT_DIR

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    @property
    def input_dir(self) -> Path:
        return INPUT_DIR

    @property
    def master_dir(self) -> Path:
        return MASTER_DIR

    @property
    def output_dir(self) -> Path:
        return OUTPUT_DIR

    @property
    def resources_dir(self) -> Path:
        return RESOURCES_DIR

    @property
    def publication_dir(self) -> Path:
        return PUBLICATION_DIR

    @property
    def log_dir(self) -> Path:
        return resolve_log_dir()

    @property
    def state_dir(self) -> Path:
        return resolve_state_dir()

    @property
    def temp_dir(self) -> Path:
        return TEMP_DIR

    def get_env(self, name: str, default: str = "") -> str:
        """Obtiene una variable de entorno."""
        return os.getenv(name, default)

    @property
    def fbl1n_path(self) -> Path:
        return FBL1N_PATH

    @property
    def fbl1n_future_enabled(self) -> bool:
        return FBL1N_FUTURE_ENABLED

    @property
    def fbl1n_future_path(self) -> Path:
        return FBL1N_FUTURE_PATH

    @property
    def fbl1n_compensation_cutoff(self) -> date | None:
        return FBL1N_COMPENSATION_CUTOFF

    @property
    def sociedades_path(self) -> Path:
        return SOCIEDADES_PATH

    @property
    def moneda_path(self) -> Path:
        return MONEDA_PATH

    @property
    def conceptos_path(self) -> Path:
        return CONCEPTOS_PATH

    @property
    def conceptos_admin_path(self) -> Path:
        return CONCEPTOS_ADMIN_PATH

    @property
    def clp_usd_acreedor_concepto_path(self) -> Path:
        return CLP_USD_ACREEDOR_CONCEPTO_PATH

    @property
    def mail_sender_account(self) -> str:
        return MAIL_SENDER_ACCOUNT

    @property
    def mail_to(self) -> str:
        return MAIL_TO

    @property
    def mail_cc(self) -> str:
        return MAIL_CC

    @property
    def mail_bcc(self) -> str:
        return MAIL_BCC

    @property
    def mail_auto_send(self) -> bool:
        return MAIL_AUTO_SEND

    @property
    def mail_sharepoint_link(self) -> str:
        return MAIL_SHAREPOINT_LINK

    @property
    def mail_powerbi_link(self) -> str:
        return MAIL_POWERBI_LINK


__all__: tuple[str, ...] = (
    "AUTHOR",
    "Config",
    "CLP_USD_ACREEDOR_CONCEPTO_FILE",
    "CLP_USD_ACREEDOR_CONCEPTO_PATH",
    "CONCEPTOS_ADMIN_FILE",
    "CONCEPTOS_ADMIN_PATH",
    "CONCEPTOS_FILE",
    "CONCEPTOS_PATH",
    "DATA_DIR",
    "FBL1N_COMPENSATION_CUTOFF",
    "FBL1N_FILE",
    "FBL1N_FUTURE_ENABLED",
    "FBL1N_FUTURE_FILE",
    "FBL1N_FUTURE_PATH",
    "FBL1N_PATH",
    "INPUT_DIR",
    "LOG_DIR",
    "MAIL_AUTO_SEND",
    "MAIL_BCC",
    "MAIL_CC",
    "MAIL_POWERBI_LINK",
    "MAIL_SENDER_ACCOUNT",
    "MAIL_SHAREPOINT_LINK",
    "MAIL_TO",
    "MASTER_DIR",
    "MONEDA_FILE",
    "MONEDA_PATH",
    "OUTPUT_DIR",
    "PROJECT_NAME",
    "PUBLICATION_DIR",
    "resolve_log_dir",
    "resolve_state_dir",
    "RESOURCES_DIR",
    "ROOT_DIR",
    "SOCIEDADES_FILE",
    "SOCIEDADES_PATH",
    "STATE_DIR",
    "TEMP_DIR",
    "VERSION",
)
