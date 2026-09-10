from __future__ import annotations

import logging
import unicodedata
from datetime import datetime

import pandas as pd

from ..config.logger import LoggerManager
from ..validators.validator import DataValidator


logger = LoggerManager.get_logger(__name__)


class FBL1NProcessor:
    """
    Procesador principal del archivo SAP FBL1N.

    Responsabilidades:
        - Validar el DataFrame.
        - Normalizar nombres de columnas.
        - Limpiar valores de texto.
        - Convertir registros en objetos RegistroFBL1N.
    """

    def __init__(
        self,
        validator: DataValidator | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:

        self.validator = validator or DataValidator()
        self.logger = logger_obj or logger

    @staticmethod
    def _normalize_column(name: str) -> str:
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

    def normalize_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Añadir aliases internos sin modificar los nombres SAP originales.
        """

        normalized_df = df.copy()

        for column in list(normalized_df.columns):
            normalized_name = self._normalize_column(column)

            if not normalized_name:
                continue

            if normalized_name == column:
                continue

            if normalized_name not in normalized_df.columns:
                normalized_df[normalized_name] = normalized_df[column]

        return normalized_df

    def clean_strings(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Limpiar espacios en columnas tipo texto.
        """

        cleaned_df = df.copy()

        for column in cleaned_df.select_dtypes(include=["object", "string"]):

            cleaned_df[column] = (
                cleaned_df[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        return cleaned_df

    def normalize_types(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Convertir columnas de importe a numérico cuando sea posible.
        """

        normalized_df = df.copy()

        for column in [
            "Importe en moneda doc.",
            "importe_en_moneda_doc",
        ]:
            if column in normalized_df.columns:
                normalized_df[column] = normalized_df[column].apply(
                    self._to_float
                )

        return normalized_df

    def process(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Procesar el DataFrame FBL1N.
        """

        self.logger.info("Iniciando procesamiento de FBL1N.")

        self.validator.validate_dataframe(df)

        df = self.normalize_columns(df)

        df = self.clean_strings(df)
        df = self.normalize_types(df)

        self.logger.info(
            "Procesamiento finalizado (%d registros).",
            len(df),
        )

        return df

    @staticmethod
    def _to_datetime(value) -> datetime | None:
        """
        Convertir distintos formatos de fecha a datetime.
        """

        if pd.isna(value):
            return None

        if isinstance(value, datetime):
            return value

        try:
            return pd.to_datetime(
                value,
                dayfirst=True,
                errors="coerce",
            ).to_pydatetime()
        except Exception:
            return None

    @staticmethod
    def _to_float(value) -> float:
        """
        Convertir importes SAP a float.
        """

        if pd.isna(value):
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()

        text = text.replace(".", "")
        text = text.replace(",", ".")

        try:
            return float(text)
        except ValueError:
            return 0.0



__all__ = ("FBL1NProcessor",)
