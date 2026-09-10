from __future__ import annotations

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from .history_mapper import map_history


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def map_home(output_service: OutputArtifactService) -> dict:
    """HomeMockData derivado de artefactos (sin inventar métricas)."""

    history = map_history(output_service)
    files = output_service.list_outputs()
    latest = output_service.latest()
    meta = output_service.file_metadata(latest) if latest else None
    last_update = (
        str(meta["modified_display"]) if meta else ND
    )

    executions_rows: list[dict[str, str]] = []
    for row in history["executions"]["rows"][:10]:
        executions_rows.append(
            {
                "report": row.get("process", "Informe Margen"),
                "date": row.get("date", ND),
                "time": row.get("time", ND),
                "status": row.get("status", ND),
                "duration": row.get("duration", ND),
                "user": row.get("user", ND),
            }
        )

    activity_rows: list[dict[str, str]] = []
    for row in history["executions"]["rows"][:10]:
        activity_rows.append(
            {
                "date": row.get("date", ND),
                "user": row.get("user", ND),
                "process": row.get("process", ND),
                "result": row.get("result", ND),
                "duration": row.get("duration", ND),
            }
        )

    return {
        "welcome": {
            "title": "CBO Operations Analytics",
            "subtitle": "Corporate Operations Reporting Platform",
            "description": (
                "Centraliza la generación, análisis y distribución de los "
                "informes operacionales del área CBO."
            ),
            "lastUpdate": last_update,
        },
        "kpis": [
            {
                "id": "reports",
                "label": "Informes generados",
                "value": str(len(files)),
                "hint": "Archivos en data/output",
                "icon": "reports",
            },
            {
                "id": "last-run",
                "label": "Última ejecución",
                "value": (
                    history["header"]["lastExecution"].split(" · ")[0]
                    if history["header"]["lastExecution"] != ND
                    else ND
                ),
                "hint": (
                    history["header"]["lastExecution"]
                    if history["header"]["lastExecution"] != ND
                    else ND
                ),
                "icon": "clock",
            },
            {
                "id": "avg-time",
                "label": "Tiempo promedio",
                "value": ND,
                "hint": "No registrado en artefactos",
                "icon": "timer",
            },
            {
                "id": "health",
                "label": "Estado general",
                "value": "Operativo" if files else "Sin datos",
                "hint": "API de lectura activa",
                "icon": "status",
            },
        ],
        "activity": {
            "columns": [
                {"key": "date", "header": "Fecha"},
                {"key": "user", "header": "Usuario"},
                {"key": "process", "header": "Proceso"},
                {"key": "result", "header": "Resultado"},
                {"key": "duration", "header": "Duración", "align": "right"},
            ],
            "rows": activity_rows,
        },
        "executions": {
            "columns": [
                {"key": "report", "header": "Nombre del informe"},
                {"key": "date", "header": "Fecha"},
                {"key": "time", "header": "Hora"},
                {"key": "status", "header": "Estado"},
                {"key": "duration", "header": "Tiempo", "align": "right"},
                {"key": "user", "header": "Usuario"},
            ],
            "rows": executions_rows,
        },
        "information": [
            {
                "id": "source",
                "title": "Fuente de datos",
                "description": (
                    "Inicio consume artefactos MATRIZ_FBL1N vía API FastAPI."
                ),
                "type": "info",
            },
            {
                "id": "integration",
                "title": "Integración",
                "description": "DATA_SOURCE=api · endpoints /api/*",
                "type": "change",
            },
        ],
    }
