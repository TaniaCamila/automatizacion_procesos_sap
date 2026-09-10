from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.conceptos_service import ConceptosService
from ...services.moneda_service import MonedaService
from ...services.output_artifact_service import OutputArtifactService
from ...services.sociedades_service import SociedadesService
from ..deps import (
    get_conceptos_service,
    get_config,
    get_moneda_service,
    get_output_service,
    get_sociedades_service,
)
from ..mappers.configuration_mapper import map_configuration
from ..schemas.models import ConfigurationResponse


router = APIRouter(tags=["configuration"])
logger = LoggerManager.get_logger(__name__)


@router.get("/configuration", response_model=ConfigurationResponse)
def get_configuration(
    request: Request,
    config: Config = Depends(get_config),
    output_service: OutputArtifactService = Depends(get_output_service),
    sociedades: SociedadesService = Depends(get_sociedades_service),
    monedas: MonedaService = Depends(get_moneda_service),
    conceptos: ConceptosService = Depends(get_conceptos_service),
) -> ConfigurationResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_configuration(
            sociedades=sociedades,
            monedas=monedas,
            conceptos=conceptos,
            config=config,
            output_service=output_service,
        )
        response = ConfigurationResponse.model_validate(payload)
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
