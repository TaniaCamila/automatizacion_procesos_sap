from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService
from ..deps import get_output_service
from ..mappers.sen_mapper import map_sen
from ..schemas.models import (
    DataGridColumn,
    FilterField,
    InfoPanelItem,
    MarginDistributionItem,
    MarginMetric,
)


router = APIRouter(tags=["sen"])
logger = LoggerManager.get_logger(__name__)


class SenHeader(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lastExecution: str
    status: str


class SenKpi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    value: str
    hint: str
    icon: str


class SenTable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class SenExecutive(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: list[MarginMetric]
    topConcepts: list[MarginMetric]
    distribution: list[MarginDistributionItem]
    alerts: list[InfoPanelItem]
    lastUpdate: str


class SenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    header: SenHeader
    kpis: list[SenKpi]
    filters: list[FilterField]
    table: SenTable
    executive: SenExecutive


@router.get("/sen", response_model=SenResponse)
def get_sen(
    request: Request,
    output_service: OutputArtifactService = Depends(get_output_service),
) -> SenResponse:
    started = time.perf_counter()
    logger.info("API GET %s — inicio", request.url.path)
    try:
        payload = map_sen(output_service)
        response = SenResponse.model_validate(payload)
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
