from __future__ import annotations

import time

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from .resumen_metrics import load_resumen_metrics


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def map_dashboard(
    output_service: OutputArtifactService,
    config: Config | None = None,
) -> dict:
    """
    DashboardMockData ejecutivo desde RESUMEN_CONCEPTOS + metadatos.

    No lee MATRIZ_FBL1N completa. No modifica el mapper de Margen.
    """

    _ = config  # compatibilidad con firma existente de la ruta
    started = time.perf_counter()

    latest = output_service.latest()
    if latest is None:
        logger.warning("Dashboard sin artefactos en output")
        return _empty_dashboard()

    meta = output_service.file_metadata(latest)
    last_execution = str(meta["modified_display"])
    metrics = load_resumen_metrics(output_service, latest)

    logger.info(
        "Dashboard métricas: total=%d clasificados=%d cobertura=%.1f%% (%.2f s)",
        metrics.total_rows,
        metrics.classified,
        metrics.coverage_pct,
        time.perf_counter() - started,
    )

    status = "Disponible" if metrics.total_rows > 0 else "Sin datos"
    top5 = metrics.top5

    activity_rows = [
        {
            "concept": item.concept,
            "records": _fmt_int(item.count),
            "share": _fmt_pct(item.percentage),
        }
        for item in metrics.concepts
    ]

    alerts: list[dict] = [
        {
            "id": "latest-ok",
            "tag": "change",
            "title": "Última ejecución disponible",
            "detail": str(meta["name"]),
            "time": last_execution,
        }
    ]
    if metrics.unclassified > 0:
        alerts.append(
            {
                "id": "unclassified",
                "tag": "warning",
                "title": "Registros sin clasificar",
                "detail": (
                    f"{_fmt_int(metrics.unclassified)} registros "
                    f"({_fmt_pct(round((metrics.unclassified / max(metrics.total_rows, 1)) * 100, 1))})."
                ),
                "time": last_execution,
            }
        )

    return {
        "header": {
            "lastExecution": last_execution,
            "status": status,
        },
        "kpis": [
            {
                "id": "records-total",
                "label": "Total de registros",
                "value": _fmt_int(metrics.total_rows),
                "hint": "MATRIZ_FBL1N (metadata)",
                "icon": "reports",
            },
            {
                "id": "records-classified",
                "label": "Registros clasificados",
                "value": _fmt_int(metrics.classified),
                "hint": "Desde RESUMEN_CONCEPTOS",
                "icon": "processes",
            },
            {
                "id": "coverage",
                "label": "Cobertura",
                "value": _fmt_pct(metrics.coverage_pct),
                "hint": f"Sin clasificar: {_fmt_int(metrics.unclassified)}",
                "icon": "availability",
            },
            {
                "id": "concepts",
                "label": "Conceptos activos",
                "value": str(len(metrics.concepts)),
                "hint": "Catálogo detectado en el artefacto",
                "icon": "modules",
            },
            {
                "id": "unclassified",
                "label": "Sin clasificar",
                "value": _fmt_int(metrics.unclassified),
                "hint": "Fila SIN CLASIFICAR",
                "icon": "errors",
            },
            {
                "id": "process-status",
                "label": "Estado del proceso",
                "value": status,
                "hint": last_execution,
                "icon": "avgTime",
            },
        ],
        "moduleDetails": [
            {
                "moduleId": "margen",
                "lastExecution": last_execution,
                "availability": _fmt_pct(metrics.coverage_pct),
                "owner": "Operaciones CBO",
                "version": "pipeline",
            },
            {
                "moduleId": "dashboard",
                "lastExecution": last_execution,
                "availability": "100%",
                "owner": "Operaciones CBO",
                "version": "api",
            },
        ],
        "activity": {
            "columns": [
                {"key": "concept", "header": "Concepto"},
                {"key": "records", "header": "Registros", "align": "right"},
                {"key": "share", "header": "Participación", "align": "right"},
            ],
            # Distribución completa por concepto (RESUMEN).
            "rows": activity_rows,
        },
        "alerts": alerts,
        "information": [
            {
                "id": "top-concepts",
                "title": "Top 5 conceptos",
                "description": (
                    ", ".join(
                        f"{item.concept} ({_fmt_int(item.count)})"
                        for item in top5
                    )
                    if top5
                    else ND
                ),
                "type": "info",
                "date": last_execution.split(" · ")[0],
            },
            {
                "id": "distribution",
                "title": "Distribución (top 5)",
                "description": (
                    ", ".join(
                        f"{item.concept} {_fmt_pct(item.percentage)}"
                        for item in top5
                    )
                    if top5
                    else ND
                ),
                "type": "info",
            },
            {
                "id": "source",
                "title": "Fuente de datos",
                "description": (
                    "Dashboard lee RESUMEN_CONCEPTOS y metadatos del artefacto; "
                    "no recorre MATRIZ_FBL1N completa."
                ),
                "type": "change",
            },
        ],
    }


def _empty_dashboard() -> dict:
    return {
        "header": {
            "lastExecution": ND,
            "status": "Sin datos",
        },
        "kpis": [
            {
                "id": "records-total",
                "label": "Total de registros",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "reports",
            },
            {
                "id": "records-classified",
                "label": "Registros clasificados",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "processes",
            },
            {
                "id": "coverage",
                "label": "Cobertura",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "availability",
            },
            {
                "id": "concepts",
                "label": "Conceptos activos",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "modules",
            },
            {
                "id": "unclassified",
                "label": "Sin clasificar",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "errors",
            },
            {
                "id": "process-status",
                "label": "Estado del proceso",
                "value": "Sin datos",
                "hint": ND,
                "icon": "avgTime",
            },
        ],
        "moduleDetails": [],
        "activity": {
            "columns": [
                {"key": "concept", "header": "Concepto"},
                {"key": "records", "header": "Registros", "align": "right"},
                {"key": "share", "header": "Participación", "align": "right"},
            ],
            "rows": [],
        },
        "alerts": [
            {
                "id": "no-artifacts",
                "tag": "warning",
                "title": "Sin artefactos",
                "detail": "No hay archivos MATRIZ_FBL1N en data/output.",
                "time": ND,
            }
        ],
        "information": [
            {
                "id": "source",
                "title": "Fuente de datos",
                "description": "Ejecute el pipeline para generar un artefacto.",
                "type": "alert",
            }
        ],
    }


__all__ = ("map_dashboard",)
