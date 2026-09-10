from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..config.concept_catalog import CURRENCY_NO_USD, CURRENCY_USD
from ..config.config import CONCEPTOS_ADMIN_PATH, Config
from ..config.logger import LoggerManager


"""
Clasificador reutilizable de conceptos de negocio.

Fuente administrable: data/resources/CONCEPTOS_ADMIN.xlsx
"""


logger = LoggerManager.get_logger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Concepto encontrado",
    "Concepto estándar",
    "Grupo",
    "Tipo",
    "Activo",
)


@dataclass(frozen=True)
class AdminConceptRow:
    encontrado: str
    estandar: str
    grupo: str
    tipo: str
    activo: bool


@dataclass
class AdminCatalog:
    rows: tuple[AdminConceptRow, ...] = ()
    patterns_by_length: tuple[str, ...] = ()
    encontrado_to_row: dict[str, AdminConceptRow] = field(default_factory=dict)
    estandar_to_group: dict[str, str] = field(default_factory=dict)
    estandar_to_tipo: dict[str, str] = field(default_factory=dict)
    groups_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_path: Path | None = None


_catalog: AdminCatalog | None = None


def _is_active(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value).strip().upper()
    return text in {"1", "SI", "SÍ", "TRUE", "YES", "Y", "ACTIVO"}


def _normalize_tipo(value: object) -> str:
    text = "" if value is None else str(value).strip().upper()
    if text in {"COM", "COMBUSTIBLE"}:
        return "COM"
    if text in {"NO_COM", "NOCOM", "NO-COM", "NO COM"}:
        return "NO_COM"
    return text or "NO_COM"


def load(path: Path | None = None) -> AdminCatalog:
    """
    Cargar CONCEPTOS_ADMIN.xlsx al iniciar el proceso.

    Si el archivo no existe, el catálogo queda vacío
    (la capa de negocio dejará No identificado).
    """

    global _catalog

    config = Config()
    source = path or config.conceptos_admin_path
    if source is None:
        source = CONCEPTOS_ADMIN_PATH

    if not Path(source).exists():
        logger.warning(
            "CONCEPTOS_ADMIN no encontrado en %s — catálogo vacío",
            source,
        )
        _catalog = AdminCatalog(source_path=Path(source))
        return _catalog

    frame = pd.read_excel(source, sheet_name=0)
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(
            "CONCEPTOS_ADMIN.xlsx incompleto. Faltan columnas: "
            + ", ".join(missing)
        )

    rows: list[AdminConceptRow] = []
    for _, item in frame.iterrows():
        encontrado = str(item.get("Concepto encontrado", "") or "").strip()
        estandar = str(item.get("Concepto estándar", "") or "").strip()
        grupo = str(item.get("Grupo", "") or "").strip()
        tipo = _normalize_tipo(item.get("Tipo"))
        if not encontrado or not estandar or not _is_active(item.get("Activo")):
            continue
        rows.append(
            AdminConceptRow(
                encontrado=encontrado,
                estandar=estandar,
                grupo=grupo,
                tipo=tipo,
                activo=True,
            )
        )

    encontrado_to_row = {row.encontrado: row for row in rows}
    patterns = tuple(
        sorted(
            encontrado_to_row.keys(),
            key=lambda concept: (-len(concept), concept),
        )
    )
    estandar_to_group = {row.estandar: row.grupo for row in rows if row.grupo}
    estandar_to_tipo = {row.estandar: row.tipo for row in rows}
    groups_map: dict[str, list[str]] = {}
    for row in rows:
        bucket = groups_map.setdefault(row.grupo, [])
        if row.estandar not in bucket:
            bucket.append(row.estandar)

    _catalog = AdminCatalog(
        rows=tuple(rows),
        patterns_by_length=patterns,
        encontrado_to_row=encontrado_to_row,
        estandar_to_group=estandar_to_group,
        estandar_to_tipo=estandar_to_tipo,
        groups_map={key: tuple(values) for key, values in groups_map.items()},
        source_path=Path(source),
    )
    logger.info(
        "CONCEPTOS_ADMIN cargado: %d patrones activos desde %s",
        len(rows),
        Path(source).name,
    )
    return _catalog


def ensure_loaded(path: Path | None = None) -> AdminCatalog:
    """Cargar el catálogo si aún no está en memoria."""

    global _catalog
    if _catalog is None:
        return load(path)
    return _catalog


def reload(path: Path | None = None) -> AdminCatalog:
    """Forzar recarga del Excel admin."""

    global _catalog
    _catalog = None
    return load(path)


def all_standard_concepts() -> tuple[str, ...]:
    catalog = ensure_loaded()
    return tuple(catalog.estandar_to_group.keys())


def standard_to_group() -> dict[str, str]:
    catalog = ensure_loaded()
    return dict(catalog.estandar_to_group)


def currency_group(moneda: object) -> str:
    """Clasificar moneda en USD o NO_USD."""

    code = "" if moneda is None else str(moneda).strip().upper()
    return CURRENCY_USD if code == CURRENCY_USD else CURRENCY_NO_USD


def group(concepto: object) -> str | None:
    """Obtener el grupo de un concepto estándar conocido, o None."""

    catalog = ensure_loaded()
    if concepto is None:
        return None
    key = str(concepto).strip()
    if not key:
        return None
    return catalog.estandar_to_group.get(key)


def tipo(concepto: object) -> str | None:
    """Obtener Tipo (COM / NO_COM) del concepto estándar."""

    catalog = ensure_loaded()
    if concepto is None:
        return None
    key = str(concepto).strip()
    if not key:
        return None
    return catalog.estandar_to_tipo.get(key)


# BUSINESS-16 — Detección restringida por concepto.
# El patrón "EDP_" solo se detecta cuando el texto contiene "EDP_[",
# eliminando falsos positivos (EDP, PAGO EDP, EDP COSTO, MI_EDP, EDP-XXX).
# No modifica el catálogo ni el Concepto estándar del clasificador.
_DETECTION_OVERRIDES: dict[str, str] = {
    "EDP_": "EDP_[",
}

# BUSINESS-16B — Nombre persistido del concepto EDP.
# La detección (BUSINESS-16) y el catálogo siguen usando "EDP_".
# Al persistir en la MATRIZ / Concepto de Pago, el valor visible es "EDP_[".
_PERSISTENCE_OVERRIDES: dict[str, str] = {
    "EDP_": "EDP_[",
}


def pattern_matches(pattern: str, text: str) -> bool:
    """
    Verificar si un "Concepto encontrado" aparece en el texto,
    aplicando las reglas de detección restringida (BUSINESS-16).
    """

    token = _DETECTION_OVERRIDES.get(pattern, pattern)
    return token == text or token in text


def search(texto: object) -> str | None:
    """
    Buscar el patrón más específico (Concepto encontrado) en el texto
    y devolver el Concepto estándar asociado.

    Si no hay coincidencia → None (No identificado).
    """

    catalog = ensure_loaded()
    if texto is None:
        return None

    text = str(texto).strip()
    if not text:
        return None

    matches = [
        pattern
        for pattern in catalog.patterns_by_length
        if pattern_matches(pattern, text)
    ]
    if not matches:
        return None

    found = matches[0]
    row = catalog.encontrado_to_row.get(found)
    if row is None:
        return None
    return row.estandar


def to_standard(concepto: object) -> str:
    """
    BUSINESS-12B — Normalizar a Concepto estándar.

    Si `concepto` coincide con un "Concepto encontrado" del ADMIN,
    devolver el "Concepto estándar". Si ya es estándar o es legacy
    (no está en ADMIN), devolver el mismo valor.
    """

    catalog = ensure_loaded()
    if concepto is None:
        return ""

    key = str(concepto).strip()
    if not key:
        return ""

    row = catalog.encontrado_to_row.get(key)
    if row is not None:
        return row.estandar
    return key


def classify(texto: object, moneda: object = None) -> dict[str, Any]:
    """
    Clasificar un registro por texto y moneda.

    Retorna:
        grupo, concepto (estándar), moneda, currency_group, tipo
    """

    concepto = search(texto)
    moneda_norm = "" if moneda is None else str(moneda).strip()

    return {
        "grupo": group(concepto) if concepto else None,
        "concepto": concepto,
        "moneda": moneda_norm.upper() if moneda_norm else "",
        "currency_group": currency_group(moneda),
        "tipo": tipo(concepto) if concepto else None,
    }


def groups() -> tuple[str, ...]:
    """Listar grupos del catálogo admin (orden de aparición)."""

    catalog = ensure_loaded()
    return tuple(catalog.groups_map.keys())


def concepts_for(grupo: str) -> tuple[str, ...]:
    """Listar conceptos estándar de un grupo."""

    catalog = ensure_loaded()
    return catalog.groups_map.get(grupo, ())


__all__ = (
    "AdminCatalog",
    "AdminConceptRow",
    "classify",
    "concepts_for",
    "currency_group",
    "ensure_loaded",
    "group",
    "groups",
    "load",
    "pattern_matches",
    "reload",
    "search",
    "tipo",
    "to_standard",
    "all_standard_concepts",
    "standard_to_group",
)
