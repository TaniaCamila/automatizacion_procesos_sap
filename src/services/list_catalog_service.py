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


class ListCatalogService(ABC):
    """
    Clase base para catálogos simples de una sola columna.

    Ejemplos:
        - MONEDA.xlsx
        - CONCEPTOS.xlsx

    Internamente mantiene un conjunto (set) con todos los valores
    para permitir búsquedas rápidas.
    """

    REQUIRED_COLUMN: str

    def __init__(
        self,
        loader: ExcelLoader,
        validator: DataValidator,
        logger_obj: logging.Logger | None = None,
    ) -> None:

        self.loader = loader
        self.validator = validator
        self.logger = logger_obj or logger

        self._items: set[str] = set()

    @property
    @abstractmethod
    def file_path(self) -> Path:
        """
        Ruta del archivo Excel.
        """
        raise NotImplementedError

    @staticmethod
    def normalize_column(name: str) -> str:
        """
        Normalizar nombres de columnas.
        """

        if name is None:
            return ""

        text = str(name).strip().lower()

        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")

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

        df = self.loader.load_excel(self.file_path)

        self.validator.validate_dataframe(df)

        self.validator.validate_required_columns(
            df,
            [self.REQUIRED_COLUMN],
        )

        renamed = {
            column: self.normalize_column(column)
            for column in df.columns
        }

        df = df.rename(columns=renamed).copy()

        normalized_column = self.normalize_column(
            self.REQUIRED_COLUMN
        )

        self.validator.validate_required_columns(
            df,
            [normalized_column],
        )

        self._build_set(df)

        self.logger.info(
            "Catálogo cargado correctamente (%d registros).",
            self.count(),
        )

    def _build_set(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Construir el conjunto interno.
        """

        column = self.normalize_column(
            self.REQUIRED_COLUMN
        )

        values: set[str] = set()

        for value in df[column]:

            if pd.isna(value):
                continue

            text = str(value).strip()

            if text:
                values.add(text)

        self._items = values

    def exists(
        self,
        value: str,
    ) -> bool:
        """
        Verificar si un valor existe.
        """

        return value in self._items

    def count(self) -> int:
        """
        Cantidad de elementos cargados.
        """

        return len(self._items)

    def values(self) -> list[str]:
        """
        Obtener los elementos ordenados.
        """

        return sorted(self._items)

    def get_items(self) -> set[str]:
        """
        Obtener una copia del conjunto de elementos.

        Este método será utilizado por MatrizService para realizar
        búsquedas rápidas sobre monedas y conceptos.
        """

        return self._items.copy()


__all__ = ("ListCatalogService",)
