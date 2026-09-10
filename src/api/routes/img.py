from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_output_service
from ..mappers.img_mapper import map_img
from ..schemas.models import (
    DataGridColumn,
    FilterField,
    InfoPanelItem,
    MarginDistributionItem,
    MarginMetric,
)


router = APIRouter(tags=["img"])
logger = LoggerManager.get_logger(__name__)


class ImgHeader(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lastExecution: str
    status: str


class ImgKpi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    value: str
    hint: str
    icon: str


class ImgTable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class ImgExecutive(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: list[MarginMetric]
    topConcepts: list[MarginMetric]
    distribution: list[MarginDistributionItem]
    alerts: list[InfoPanelItem]
    lastUpdate: str


class ImgResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    header: ImgHeader
    kpis: list[ImgKpi]
    filters: list[FilterField]
    table: ImgTable
    executive: ImgExecutive


@router.get("/img", response_model=ImgResponse)
def get_img(
    request: Request,
    output_service: OutputArtifactService = Depends(get_output_service),
) -> ImgResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_img(output_service)
        response = ImgResponse.model_validate(payload)
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
