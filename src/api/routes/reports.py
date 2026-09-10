from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_output_service
from ..mappers.margin_mapper import map_margin
from ..schemas.models import MarginResponse


router = APIRouter(tags=["reports"])
logger = LoggerManager.get_logger(__name__)


@router.get("/reports/margin", response_model=MarginResponse)
def get_margin_report(
    request: Request,
    output_service: OutputArtifactService = Depends(get_output_service),
) -> MarginResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_margin(output_service)
        response = MarginResponse.model_validate(payload)
        elapsed = time.perf_counter() - started
        logger.info(
            "API GET %s — fin (%.2f s)",
            request.url.path,
            elapsed,
        )
        return response
    except FileNotFoundError as exc:
        elapsed = time.perf_counter() - started
        logger.error(
            "API GET %s — error (%.2f s): %s",
            request.url.path,
            elapsed,
            exc,
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        logger.exception(
            "API GET %s — error (%.2f s)",
            request.url.path,
            elapsed,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
