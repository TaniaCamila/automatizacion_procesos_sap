from __future__ import annotations

import logging
from pathlib import Path

from ..config.config import Config
from ..config.logger import LoggerManager
from ..loaders.excel_loader import ExcelLoader
from ..validators.validator import DataValidator
from .catalog_service import CatalogService


config = Config()
logger = LoggerManager.get_logger(__name__)


class SociedadesService(CatalogService):
    """
    Servicio encargado del catálogo de sociedades.

    Hereda toda la funcionalidad de CatalogService y únicamente
    define la ubicación del archivo y las columnas requeridas.
    """

    REQUIRED_COLUMNS = (
        "Sociedades",
        "Sociedad",
    )

    def __init__(
        self,
        config_obj: Config | None = None,
        logger_obj: logging.Logger | None = None,
        excel_loader: ExcelLoader | None = None,
        validator: DataValidator | None = None,
    ) -> None:

        self.config = config_obj or config

        super().__init__(
            loader=excel_loader or ExcelLoader(
                config_obj=self.config,
                logger_obj=logger_obj or logger,
            ),
            validator=validator or DataValidator(
                config_obj=self.config,
                logger_obj=logger_obj or logger,
            ),
            logger_obj=logger_obj or logger,
        )

    @property
    def file_path(self) -> Path:
        """
        Ruta del catálogo de sociedades.
        """

        return self.config.sociedades_path


__all__ = ("SociedadesService",)
