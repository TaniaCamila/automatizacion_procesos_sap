from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DataGridColumn(ApiModel):
    key: str
    header: str
    align: Literal["left", "right"] | None = None


class FilterOption(ApiModel):
    label: str
    value: str


class FilterField(ApiModel):
    id: str
    label: str
    type: Literal["select", "date", "text"] | None = None
    placeholder: str | None = None
    options: list[FilterOption] | None = None
    defaultValue: str | None = None


class InfoPanelItem(ApiModel):
    id: str
    title: str
    description: str
    type: Literal[
        "info",
        "alert",
        "change",
        "roadmap",
        "sprint",
        "news",
        "admin",
    ]
    date: str | None = None


class MarginKpi(ApiModel):
    id: str
    label: str
    value: str
    hint: str
    icon: Literal["income", "margin", "average", "records"]


class MarginMetric(ApiModel):
    id: str
    label: str
    value: str
    detail: str | None = None


class MarginDistributionItem(ApiModel):
    id: str
    label: str
    value: float
    displayValue: str


class MarginTable(ApiModel):
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class MarginHeader(ApiModel):
    lastExecution: str
    status: str


class MarginExecutive(ApiModel):
    summary: list[MarginMetric]
    topConcepts: list[MarginMetric]
    alerts: list[InfoPanelItem]
    distribution: list[MarginDistributionItem]
    lastUpdate: str


class MarginResponse(ApiModel):
    header: MarginHeader
    kpis: list[MarginKpi]
    filters: list[FilterField]
    transactions: MarginTable
    executive: MarginExecutive
    activity: MarginTable
    exports: MarginTable


class ServiceStatus(ApiModel):
    id: str
    name: str
    health: Literal["operational", "degraded", "offline", "not_configured"]
    detail: str


class HistoryKpi(ApiModel):
    id: str
    label: str
    value: str
    hint: str
    icon: Literal[
        "executions",
        "lastRun",
        "avgTime",
        "errors",
        "success",
        "records",
    ]


class HistoryTable(ApiModel):
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class HistoryActivityItem(ApiModel):
    id: str
    title: str
    detail: str
    time: str


class HistoryPlatformMetric(ApiModel):
    id: str
    label: str
    value: str


class HistoryHeader(ApiModel):
    lastExecution: str
    status: str


class HistoryResponse(ApiModel):
    header: HistoryHeader
    kpis: list[HistoryKpi]
    filters: list[FilterField]
    executions: HistoryTable
    recentActivity: list[HistoryActivityItem]
    platform: list[HistoryPlatformMetric]
    information: list[InfoPanelItem]


class ConfigHeader(ApiModel):
    catalogVersion: str
    lastSync: str
    status: str


class ConfigSection(ApiModel):
    header: ConfigHeader
    filters: list[FilterField]
    information: list[InfoPanelItem]


class CatalogTable(ApiModel):
    columns: list[DataGridColumn]
    rows: list[dict[str, str]]


class ConceptsCatalog(ApiModel):
    table: CatalogTable
    total: str
    status: str
    updatedAt: str


class CatalogStatus(ApiModel):
    id: str
    name: str
    status: str
    variant: Literal["success", "warning", "neutral", "info"]
    lastSync: str
    records: str


class CatalogsData(ApiModel):
    companies: CatalogTable
    currencies: CatalogTable
    concepts: ConceptsCatalog
    status: list[CatalogStatus]


class ParameterItem(ApiModel):
    id: str
    label: str
    value: str
    description: str
    kind: Literal["path", "format", "language", "timezone", "user"]


class ConfigurationResponse(ApiModel):
    config: ConfigSection
    catalogs: CatalogsData
    parameters: list[ParameterItem]


# Alias útiles para typing interno
JsonDict = dict[str, Any]
