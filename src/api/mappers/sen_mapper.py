from __future__ import annotations

import time

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from .resumen_metrics import load_resumen_metrics


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def map_sen(output_service: OutputArtifactService) -> dict:
    """
    SEN: métricas desde RESUMEN_CONCEPTOS + metadatos.

    No lee MATRIZ_FBL1N completa. Reutiliza resumen_metrics.
    """

    started = time.perf_counter()
    latest = output_service.latest()
    if latest is None:
        logger.warning("SEN sin artefactos en output")
        return _empty_sen()

    meta = output_service.file_metadata(latest)
    last_execution = str(meta["modified_display"])
    metrics = load_resumen_metrics(output_service, latest)
    status = "Disponible" if metrics.total_rows > 0 else "Sin datos"
    top5 = metrics.top5

    logger.info(
        "SEN métricas: total=%d clasificados=%d cobertura=%.1f%% (%.2f s)",
        metrics.total_rows,
        metrics.classified,
        metrics.coverage_pct,
        time.perf_counter() - started,
    )

    table_rows = [
        {
            "concept": item.concept,
            "records": _fmt_int(item.count),
            "share": _fmt_pct(item.percentage),
            "status": "Clasificado",
        }
        for item in metrics.concepts
    ]

    return {
        "header": {
            "lastExecution": last_execution,
            "status": status,
        },
        "kpis": [
            {
                "id": "records",
                "label": "Registros SEN",
                "value": _fmt_int(metrics.total_rows),
                "hint": "Total matriz (metadata)",
                "icon": "records",
            },
            {
                "id": "classified",
                "label": "Conceptos clasificados",
                "value": _fmt_int(metrics.classified),
                "hint": "RESUMEN_CONCEPTOS",
                "icon": "classified",
            },
            {
                "id": "coverage",
                "label": "Cobertura",
                "value": _fmt_pct(metrics.coverage_pct),
                "hint": f"Sin clasificar: {_fmt_int(metrics.unclassified)}",
                "icon": "coverage",
            },
            {
                "id": "concepts",
                "label": "Conceptos SEN",
                "value": str(len(metrics.concepts)),
                "hint": "Conceptos detectados",
                "icon": "concepts",
            },
        ],
        "filters": [
            {
                "id": "concept",
                "label": "Concepto",
                "type": "select",
                "placeholder": "Todos los conceptos",
                "options": [
                    {"label": item.concept, "value": item.concept}
                    for item in metrics.concepts
                ],
            }
        ],
        "table": {
            "columns": [
                {"key": "concept", "header": "Concepto"},
                {"key": "records", "header": "Registros", "align": "right"},
                {"key": "share", "header": "Participación", "align": "right"},
                {"key": "status", "header": "Estado"},
            ],
            "rows": table_rows,
        },
        "executive": {
            "summary": [
                {
                    "id": "coverage",
                    "label": "Cobertura SEN",
                    "value": _fmt_pct(metrics.coverage_pct),
                    "detail": (
                        f"{_fmt_int(metrics.classified)} / "
                        f"{_fmt_int(metrics.total_rows)}"
                    ),
                },
                {
                    "id": "artifact",
                    "label": "Artefacto",
                    "value": str(meta["name"]),
                    "detail": last_execution,
                },
                {
                    "id": "pending",
                    "label": "Pendientes",
                    "value": _fmt_int(metrics.unclassified),
                    "detail": "Sin concepto detectado",
                },
            ],
            "topConcepts": [
                {
                    "id": f"top-{index}",
                    "label": item.concept,
                    "value": _fmt_int(item.count),
                    "detail": _fmt_pct(item.percentage),
                }
                for index, item in enumerate(top5)
            ],
            "distribution": [
                {
                    "id": f"dist-{index}",
                    "label": item.concept,
                    "value": float(item.percentage),
                    "displayValue": _fmt_pct(item.percentage),
                }
                for index, item in enumerate(top5)
            ],
            "alerts": (
                [
                    {
                        "id": "unclassified",
                        "title": "Registros sin clasificar",
                        "description": (
                            f"{_fmt_int(metrics.unclassified)} registros "
                            "requieren revisión de catálogo."
                        ),
                        "type": "alert",
                        "date": last_execution.split(" · ")[0],
                    }
                ]
                if metrics.unclassified > 0
                else []
            ),
            "lastUpdate": last_execution,
        },
    }


def _empty_sen() -> dict:
    return {
        "header": {"lastExecution": ND, "status": "Sin datos"},
        "kpis": [
            {
                "id": "records",
                "label": "Registros SEN",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "records",
            },
            {
                "id": "classified",
                "label": "Conceptos clasificados",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "classified",
            },
            {
                "id": "coverage",
                "label": "Cobertura",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "coverage",
            },
            {
                "id": "concepts",
                "label": "Conceptos SEN",
                "value": ND,
                "hint": "Sin artefacto",
                "icon": "concepts",
            },
        ],
        "filters": [],
        "table": {
            "columns": [
                {"key": "concept", "header": "Concepto"},
                {"key": "records", "header": "Registros", "align": "right"},
                {"key": "share", "header": "Participación", "align": "right"},
                {"key": "status", "header": "Estado"},
            ],
            "rows": [],
        },
        "executive": {
            "summary": [],
            "topConcepts": [],
            "distribution": [],
            "alerts": [
                {
                    "id": "no-artifacts",
                    "title": "Sin artefactos",
                    "description": "Ejecute el pipeline para generar MATRIZ_FBL1N.",
                    "type": "alert",
                }
            ],
            "lastUpdate": ND,
        },
    }


__all__ = ("map_sen",)
