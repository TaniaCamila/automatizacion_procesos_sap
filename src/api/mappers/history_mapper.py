from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def _parse_timestamp_from_name(name: str) -> datetime | None:
    # MATRIZ_FBL1N_YYYYMMDD_HHMMSS.xlsx
    stem = Path(name).stem
    parts = stem.split("_")
    if len(parts) < 4:
        return None
    stamp = f"{parts[-2]}_{parts[-1]}"
    try:
        return datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _fmt_size(size_bytes: int) -> str:
    mb = size_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.2f} MB"
    kb = size_bytes / 1024
    return f"{kb:.1f} KB"


def map_history(output_service: OutputArtifactService) -> dict:
    """HistoryPageMockData desde archivos en data/output."""

    files = output_service.list_outputs()
    rows: list[dict[str, str]] = []
    activity: list[dict[str, str]] = []

    for index, path in enumerate(files):
        meta = output_service.file_metadata(path)
        parsed = _parse_timestamp_from_name(path.name)
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        when = parsed or modified
        rows.append(
            {
                "date": when.strftime("%d/%m/%Y"),
                "time": when.strftime("%H:%M"),
                "user": ND,
                "process": "Informe Margen",
                "module": "margen",
                "status": "Completado",
                "duration": ND,
                "records": ND,
                "file": path.name,
                "result": "OK",
                "message": f"Artefacto {_fmt_size(int(meta['size_bytes']))}",
            }
        )
        if index < 5:
            activity.append(
                {
                    "id": f"file-{index}",
                    "title": "Informe Margen exportado",
                    "detail": path.name,
                    "time": str(meta["modified_display"]),
                }
            )

    last_execution = rows[0]["date"] + " · " + rows[0]["time"] if rows else ND
    status = "Artefactos disponibles" if rows else "Sin ejecuciones"

    return {
        "header": {
            "lastExecution": last_execution,
            "status": status,
        },
        "kpis": [
            {
                "id": "executions",
                "label": "Procesos ejecutados",
                "value": str(len(files)),
                "hint": "Archivos en data/output",
                "icon": "executions",
            },
            {
                "id": "last-run",
                "label": "Última ejecución",
                "value": rows[0]["time"] if rows else ND,
                "hint": (
                    f"{rows[0]['date']} · Informe Margen" if rows else ND
                ),
                "icon": "lastRun",
            },
            {
                "id": "avg-time",
                "label": "Tiempo promedio",
                "value": ND,
                "hint": "No registrado en artefactos",
                "icon": "avgTime",
            },
            {
                "id": "errors",
                "label": "Errores",
                "value": "0",
                "hint": "Solo se listan exportaciones existentes",
                "icon": "errors",
            },
            {
                "id": "success",
                "label": "Éxitos",
                "value": str(len(files)),
                "hint": "Archivos MATRIZ detectados",
                "icon": "success",
            },
            {
                "id": "records",
                "label": "Registros procesados",
                "value": ND,
                "hint": "Ver endpoint /reports/margin",
                "icon": "records",
            },
        ],
        "filters": [
            {
                "id": "search",
                "label": "Buscar",
                "type": "text",
                "placeholder": "Proceso, archivo o mensaje",
            },
            {
                "id": "module",
                "label": "Módulo",
                "type": "select",
                "placeholder": "Todos los módulos",
                "options": [
                    {"label": "Informe Margen", "value": "margen"},
                ],
            },
        ],
        "executions": {
            "columns": [
                {"key": "date", "header": "Fecha"},
                {"key": "time", "header": "Hora"},
                {"key": "user", "header": "Usuario"},
                {"key": "process", "header": "Proceso"},
                {"key": "module", "header": "Módulo"},
                {"key": "status", "header": "Estado"},
                {"key": "duration", "header": "Duración", "align": "right"},
                {"key": "records", "header": "Registros", "align": "right"},
                {"key": "file", "header": "Archivo"},
                {"key": "result", "header": "Resultado"},
                {"key": "message", "header": "Mensaje"},
            ],
            "rows": rows,
        },
        "recentActivity": activity,
        "platform": [
            {
                "id": "artifacts",
                "label": "Artefactos",
                "value": str(len(files)),
            },
            {
                "id": "output-dir",
                "label": "Directorio",
                "value": str(output_service.output_dir),
            },
        ],
        "information": [
            {
                "id": "source",
                "title": "Fuente de historial",
                "description": (
                    "El historial se construye desde los archivos "
                    "MATRIZ_FBL1N_*.xlsx en data/output."
                ),
                "type": "info",
            },
        ],
    }
