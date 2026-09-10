from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_config, get_output_service
from ..mappers.system_mapper import map_system_status
from ..schemas.models import ServiceStatus


router = APIRouter(tags=["system"])
logger = LoggerManager.get_logger(__name__)


@router.get("/system/status", response_model=list[ServiceStatus])
def get_system_status(
    request: Request,
    config: Config = Depends(get_config),
    output_service: OutputArtifactService = Depends(get_output_service),
) -> list[ServiceStatus]:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_system_status(output_service, config)
        response = [ServiceStatus.model_validate(item) for item in payload]
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
