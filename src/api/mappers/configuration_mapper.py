from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.conceptos_service import ConceptosService
from ...services.moneda_service import MonedaService
from ...services.output_artifact_service import OutputArtifactService
from ...services.sociedades_service import SociedadesService


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def _mtime_display(path: Path) -> str:
    if not path.exists():
        return ND
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y · %H:%M")


def _date_only(path: Path) -> str:
    if not path.exists():
        return ND
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y")


def map_configuration(
    sociedades: SociedadesService,
    monedas: MonedaService,
    conceptos: ConceptosService,
    config: Config,
    output_service: OutputArtifactService,
) -> dict:
    """ConfigurationData desde catálogos existentes + Config."""

    sync_candidates = [
        config.sociedades_path,
        config.moneda_path,
        config.conceptos_path,
    ]
    existing = [p for p in sync_candidates if p.exists()]
    last_sync = max(existing, key=lambda p: p.stat().st_mtime) if existing else None
    last_sync_display = (
        _mtime_display(last_sync) if last_sync is not None else ND
    )
    catalog_version = (
        f"v{datetime.fromtimestamp(last_sync.stat().st_mtime).strftime('%Y.%m')}"
        if last_sync is not None
        else ND
    )

    soc_catalog = sociedades.get_catalog()
    mon_values = monedas.values()
    con_values = conceptos.values()

    companies_rows = [
        {
            "code": code,
            "name": name,
            "status": "Activa",
            "updatedAt": _date_only(config.sociedades_path),
            "actions": "Solo lectura",
        }
        for code, name in sorted(soc_catalog.items())
    ]

    currencies_rows = [
        {
            "code": code,
            "description": code,
            "status": "Activa",
            "records": ND,
        }
        for code in mon_values
    ]

    concepts_rows = [
        {
            "code": concept,
            "name": concept,
            "status": "Activo",
            "updatedAt": _date_only(config.conceptos_path),
        }
        for concept in con_values
    ]

    latest = output_service.latest()
    latest_name = latest.name if latest else ND

    return {
        "config": {
            "header": {
                "catalogVersion": catalog_version,
                "lastSync": last_sync_display,
                "status": "Sincronizado" if existing else "Sin catálogos",
            },
            "filters": [
                {
                    "id": "search",
                    "label": "Buscar",
                    "type": "text",
                    "placeholder": "Código, nombre o descripción",
                },
                {
                    "id": "type",
                    "label": "Tipo",
                    "type": "select",
                    "placeholder": "Todos los catálogos",
                    "options": [
                        {"label": "Sociedades", "value": "companies"},
                        {"label": "Monedas", "value": "currencies"},
                        {"label": "Conceptos", "value": "concepts"},
                    ],
                },
            ],
            "information": [
                {
                    "id": "version",
                    "title": "Versión del catálogo",
                    "description": f"Catálogos locales · {catalog_version}",
                    "type": "info",
                    "date": last_sync_display.split(" · ")[0]
                    if last_sync_display != ND
                    else ND,
                },
                {
                    "id": "output",
                    "title": "Último artefacto",
                    "description": f"Archivo de salida: {latest_name}",
                    "type": "info",
                },
            ],
        },
        "catalogs": {
            "companies": {
                "columns": [
                    {"key": "code", "header": "Código"},
                    {"key": "name", "header": "Nombre"},
                    {"key": "status", "header": "Estado"},
                    {"key": "updatedAt", "header": "Última actualización"},
                    {"key": "actions", "header": "Acciones"},
                ],
                "rows": companies_rows,
            },
            "currencies": {
                "columns": [
                    {"key": "code", "header": "Código"},
                    {"key": "description", "header": "Descripción"},
                    {"key": "status", "header": "Estado"},
                    {
                        "key": "records",
                        "header": "Cantidad de registros",
                        "align": "right",
                    },
                ],
                "rows": currencies_rows,
            },
            "concepts": {
                "table": {
                    "columns": [
                        {"key": "code", "header": "Código"},
                        {"key": "name", "header": "Nombre"},
                        {"key": "status", "header": "Estado"},
                        {"key": "updatedAt", "header": "Última actualización"},
                    ],
                    "rows": concepts_rows,
                },
                "total": f"{len(con_values)} conceptos",
                "status": "Activo",
                "updatedAt": _mtime_display(config.conceptos_path),
            },
            "status": [
                {
                    "id": "sociedades",
                    "name": "Sociedades",
                    "status": "Activo",
                    "variant": "success",
                    "lastSync": _mtime_display(config.sociedades_path),
                    "records": str(len(soc_catalog)),
                },
                {
                    "id": "monedas",
                    "name": "Monedas",
                    "status": "Activo",
                    "variant": "success",
                    "lastSync": _mtime_display(config.moneda_path),
                    "records": str(len(mon_values)),
                },
                {
                    "id": "conceptos",
                    "name": "Conceptos",
                    "status": "Activo",
                    "variant": "success",
                    "lastSync": _mtime_display(config.conceptos_path),
                    "records": str(len(con_values)),
                },
            ],
        },
        "parameters": [
            {
                "id": "fbl1n-path",
                "label": "Ruta FBL1N",
                "value": str(config.fbl1n_path),
                "description": "Archivo de entrada SAP FBL1N",
                "kind": "path",
            },
            {
                "id": "output-path",
                "label": "Ruta de salida",
                "value": str(config.output_dir),
                "description": "Directorio de artefactos MATRIZ_FBL1N",
                "kind": "path",
            },
            {
                "id": "resources-path",
                "label": "Ruta de catálogos",
                "value": str(config.resources_dir),
                "description": "SOCIEDADES, MONEDA y CONCEPTOS",
                "kind": "path",
            },
            {
                "id": "output-format",
                "label": "Formato de salida",
                "value": "xlsx",
                "description": "Formato del informe generado por el pipeline",
                "kind": "format",
            },
        ],
    }
