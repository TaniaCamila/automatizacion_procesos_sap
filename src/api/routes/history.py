from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_output_service
from ..mappers.history_mapper import map_history
from ..schemas.models import HistoryResponse


router = APIRouter(tags=["history"])
logger = LoggerManager.get_logger(__name__)


@router.get("/history", response_model=HistoryResponse)
def get_history(
    request: Request,
    output_service: OutputArtifactService = Depends(get_output_service),
) -> HistoryResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_history(output_service)
        response = HistoryResponse.model_validate(payload)
        elapsed = time.perf_counter() - started
        logger.info(
            "API GET %s — fin (%.2f s)",
            request.url.path,
            elapsed,
        )
        return response
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        logger.exception(
            "API GET %s — error (%.2f s)",
            request.url.path,
            elapsed,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
