from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_config, get_output_service
from ..mappers.dashboard_mapper import map_dashboard
from ..schemas.models import DataGridColumn, InfoPanelItem


router = APIRouter(tags=["dashboard"])
logger = LoggerManager.get_logger(__name__)


class DashboardHeader(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lastExecution: str
    status: str


class DashboardKpi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    value: str
    hint: str
    icon: str


class DashboardModuleDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    moduleId: str
    lastExecution: str
    availability: str
    owner: str
    version: str


class DashboardTable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class DashboardAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    tag: str
    title: str
    detail: str
    time: str


class DashboardResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    header: DashboardHeader
    kpis: list[DashboardKpi]
    moduleDetails: list[DashboardModuleDetail]
    activity: DashboardTable
    alerts: list[DashboardAlert]
    information: list[InfoPanelItem]


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    request: Request,
    config: Config = Depends(get_config),
    output_service: OutputArtifactService = Depends(get_output_service),
) -> DashboardResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_dashboard(output_service, config)
        response = DashboardResponse.model_validate(payload)
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
