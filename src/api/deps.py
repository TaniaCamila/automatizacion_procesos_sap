from __future__ import annotations

from functools import lru_cache

from ..config.config import Config
from ..config.logger import LoggerManager
from ..services.conceptos_service import ConceptosService
from ..services.moneda_service import MonedaService
from ..services.output_artifact_service import OutputArtifactService
from ..services.sociedades_service import SociedadesService


logger = LoggerManager.get_logger(__name__)


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


@lru_cache(maxsize=1)
def get_output_service() -> OutputArtifactService:
    return OutputArtifactService(config_obj=get_config())


def get_sociedades_service() -> SociedadesService:
    service = SociedadesService(config_obj=get_config())
    service.load()
    return service


def get_moneda_service() -> MonedaService:
    service = MonedaService(config_obj=get_config())
    service.load()
    return service


def get_conceptos_service() -> ConceptosService:
    service = ConceptosService(config_obj=get_config())
    service.load()
    return service
