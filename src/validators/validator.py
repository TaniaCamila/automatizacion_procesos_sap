from __future__ import annotations

import logging

import pandas as pd

from ..config.config import Config
from ..config.logger import LoggerManager

config = Config()
logger = LoggerManager.get_logger(__name__)


class DataValidator:
    """
    Validador central de estructuras de datos.

    Su responsabilidad es comprobar que los DataFrame cumplan las
    condiciones mínimas antes de iniciar cualquier procesamiento.

    No realiza:

    - Reglas de negocio.
    - Limpieza de datos.
    - Transformaciones.
    - Cruces entre archivos.
    """

    def __init__(
        self,
        config_obj: Config | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        """
        Inicializar el validador.

        Args:
            config_obj:
                Configuración personalizada.

            logger_obj:
                Logger personalizado.
        """
        self.config = config_obj or config
        self.logger = logger_obj or logger

    def _raise_validation_error(self, message: str) -> None:
        """
        Registrar y lanzar un error de validación.

        Args:
            message:
                Mensaje descriptivo del error.

        Raises:
            ValueError:
                Siempre que se detecte una validación inválida.
        """
        self.logger.error(message)
        raise ValueError(message)

    def validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Validar la estructura básica de un DataFrame.

        Comprueba:

        - Que no sea None.
        - Que sea un DataFrame.
        - Que no esté vacío.
        - Que tenga columnas.
        - Que no existan columnas duplicadas.
        - Que no existan nombres de columnas vacíos.

        Args:
            df:
                DataFrame a validar.
        """

        self.logger.info("Iniciando validación estructural del DataFrame.")

        if df is None:
            self._raise_validation_error("El DataFrame es None.")

        if not isinstance(df, pd.DataFrame):
            self._raise_validation_error(
                "El objeto proporcionado no es un pandas.DataFrame."
            )

        if df.empty:
            self._raise_validation_error(
                "El DataFrame está vacío."
            )

        if len(df.columns) == 0:
            self._raise_validation_error(
                "El DataFrame no contiene columnas."
            )

        # Detectar columnas duplicadas
        duplicated_columns = (
            df.columns[df.columns.duplicated()]
            .tolist()
        )

        if duplicated_columns:
            self._raise_validation_error(
                f"Se encontraron columnas duplicadas: {duplicated_columns}"
            )

        # Detectar nombres de columnas vacíos o nulos
        invalid_columns = [
            column
            for column in df.columns
            if column is None or str(column).strip() == ""
        ]

        if invalid_columns:
            self._raise_validation_error(
                "Existen columnas con nombres vacíos o nulos."
            )

        self.logger.info(
            "Validación estructural completada correctamente."
        )

    def validate_required_columns(
        self,
        df: pd.DataFrame,
        required_columns: list[str],
    ) -> None:
        """
        Verificar que todas las columnas requeridas existan.

        Args:
            df:
                DataFrame a validar.

            required_columns:
                Lista de columnas obligatorias.

        Raises:
            ValueError:
                Si falta alguna columna.
        """

        self.logger.info(
            "Validando columnas obligatorias."
        )

        if required_columns is None:
            self._raise_validation_error(
                "La lista de columnas requeridas es None."
            )

        if len(required_columns) == 0:
            self._raise_validation_error(
                "La lista de columnas requeridas está vacía."
            )

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            self._raise_validation_error(
                f"Faltan las siguientes columnas obligatorias: "
                f"{missing_columns}"
            )

        self.logger.info(
            "Todas las columnas obligatorias están presentes."
        )


__all__ = ("DataValidator",)
