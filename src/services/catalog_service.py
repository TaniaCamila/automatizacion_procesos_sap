from __future__ import annotations

import logging
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from ..config.logger import LoggerManager
from ..loaders.excel_loader import ExcelLoader
from ..validators.validator import DataValidator


logger = LoggerManager.get_logger(__name__)


class CatalogService(ABC):
    """
    Clase base para todos los catálogos del proyecto.

    Centraliza la lógica común de:

    - Lectura del Excel.
    - Validación del DataFrame.
    - Normalización de columnas.
    - Construcción del diccionario.
    - Consulta del catálogo.

    Las clases hijas solamente deben indicar:

    - file_path
    - REQUIRED_COLUMNS
    """

    REQUIRED_COLUMNS: tuple[str, ...]

    def __init__(
        self,
        loader: ExcelLoader,
        validator: DataValidator,
        logger_obj: logging.Logger | None = None,
    ) -> None:

        self.loader = loader
        self.validator = validator
        self.logger = logger_obj or logger

        self._catalog: dict[str, str] = {}

    @property
    @abstractmethod
    def file_path(self) -> Path:
        """
        Ruta del archivo Excel del catálogo.
        """
        raise NotImplementedError

    @staticmethod
    def normalize_column(name: str) -> str:
        """
        Normalizar nombres de columnas.

        Ejemplo:

            Descripción -> descripcion
            Texto Cab. -> texto_cab
        """

        if name is None:
            return ""

        text = str(name).strip().lower()

        text = unicodedata.normalize(
            "NFKD",
            text,
        )

        text = (
            text.encode("ascii", "ignore")
            .decode("ascii")
        )

        text = text.replace(".", "")
        text = text.replace(" ", "_")

        return text

    def load(self) -> None:
        """
        Cargar completamente el catálogo.
        """

        self.logger.info(
            "Cargando catálogo %s...",
            self.file_path.name,
        )

        df = self.loader.load_excel(
            self.file_path,
        )

        self.validator.validate_dataframe(df)

        self.validator.validate_required_columns(
            df,
            list(self.REQUIRED_COLUMNS),
        )

        renamed = {
            column: self.normalize_column(column)
            for column in df.columns
        }

        df = df.rename(columns=renamed).copy()

        normalized_required = [
            self.normalize_column(column)
            for column in self.REQUIRED_COLUMNS
        ]

        self.validator.validate_required_columns(
            df,
            normalized_required,
        )

        self._build_dictionary(df)

        self.logger.info(
            "Catálogo cargado correctamente (%d registros).",
            self.count(),
        )

    def _build_dictionary(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Construir el diccionario interno.
        """

        code_column = self.normalize_column(
            self.REQUIRED_COLUMNS[0]
        )

        description_column = self.normalize_column(
            self.REQUIRED_COLUMNS[1]
        )

        catalog: dict[str, str] = {}

        for row in df.itertuples(index=False):

            code = getattr(
                row,
                code_column,
                None,
            )

            description = getattr(
                row,
                description_column,
                "",
            )

            if pd.isna(code):
                continue

            code = str(code).strip()

            if not code:
                continue

            catalog[code] = str(description).strip()

        self._catalog = catalog

    def get_name(
        self,
        code: str,
    ) -> str:
        """
        Obtener la descripción de un código.
        """

        return self._catalog.get(code, code)

    def exists(
        self,
        code: str,
    ) -> bool:
        """
        Verificar si un código existe.
        """

        return code in self._catalog

    def count(self) -> int:
        """
        Cantidad de registros cargados.
        """

        return len(self._catalog)

    def get_catalog(self) -> dict[str, str]:
        """
        Obtener una copia del catálogo.
        """

        return self._catalog.copy()


__all__ = ("CatalogService",)
