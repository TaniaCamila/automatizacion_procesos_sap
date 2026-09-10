from __future__ import annotations

import logging
from pathlib import Path

from ..config.config import Config
from ..config.logger import LoggerManager
from ..loaders.excel_loader import ExcelLoader
from ..validators.validator import DataValidator
from .list_catalog_service import ListCatalogService


config = Config()
logger = LoggerManager.get_logger(__name__)


class MonedaService(ListCatalogService):
    """
    Servicio encargado del catálogo de monedas.

    El archivo MONEDA.xlsx contiene una única columna con los códigos
    de moneda válidos (CLP, USD, EUR, etc.).

    Hereda toda la funcionalidad desde ListCatalogService.
    """

    REQUIRED_COLUMN = "Moneda"

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
        Ruta del archivo de monedas.
        """
        return self.config.moneda_path


__all__ = ("MonedaService",)
