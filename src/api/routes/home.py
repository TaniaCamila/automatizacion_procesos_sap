from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_output_service
from ..mappers.home_mapper import map_home
from ..schemas.models import (
    DataGridColumn,
    InfoPanelItem,
)


router = APIRouter(tags=["home"])
logger = LoggerManager.get_logger(__name__)


class HomeWelcome(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    subtitle: str
    description: str
    lastUpdate: str


class HomeKpi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    value: str
    hint: str | None = None
    icon: str


class HomeTable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class HomeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    welcome: HomeWelcome
    kpis: list[HomeKpi]
    activity: HomeTable
    executions: HomeTable
    information: list[InfoPanelItem]


@router.get("/home", response_model=HomeResponse)
def get_home(
    request: Request,
    output_service: OutputArtifactService = Depends(get_output_service),
) -> HomeResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_home(output_service)
        response = HomeResponse.model_validate(payload)
        logger.info(
            "API GET %s — fin (%.2f s)",
            request.url.path,
            time.perf_counter() - started,
        )
        return response
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "API GET %s — error (%.2f s)",
            request.url.path,
            time.perf_counter() - started,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
