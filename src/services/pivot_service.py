from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config.logger import LoggerManager


logger = LoggerManager.get_logger(__name__)


class PivotService:
    """
    Servicio genérico para construir vistas analíticas (tablas cruzadas)
    a partir de la matriz.

    Responsabilidades:
        - Aplicar filtros parametrizables.
        - Construir tablas cruzadas reutilizables.
        - Retornar DataFrames listos para exportación.

    No contiene reglas de negocio.
    Todas las decisiones del negocio se entregan mediante parámetros.
    """

    def __init__(self, logger_obj: logging.Logger | None = None) -> None:
        self.logger = logger_obj or logger

    def _apply_filters(
        self,
        df: pd.DataFrame,
        filters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """
        Aplica filtros al DataFrame.

        Args:
            df:
                DataFrame origen.

            filters:
                Diccionario del tipo:

                {
                    "columna": valor,
                    "otra_columna": [valor1, valor2]
                }

        Returns:
            DataFrame filtrado.
        """

        if not filters:
            return df.copy()

        filtered_df = df.copy()

        self.logger.info("Aplicando filtros: %s", filters)

        for column, value in filters.items():

            if column not in filtered_df.columns:
                self.logger.warning(
                    "La columna '%s' no existe. Se ignora el filtro.",
                    column,
                )
                continue

            if isinstance(value, list):
                filtered_df = filtered_df[
                    filtered_df[column].isin(value)
                ]
            else:
                filtered_df = filtered_df[
                    filtered_df[column] == value
                ]

        self.logger.info(
            "Registros después de filtrar: %d",
            len(filtered_df),
        )

        return filtered_df

    def create_pivot(
        self,
        df: pd.DataFrame,
        index: str | list[str],
        columns: str | list[str],
        values: str,
        aggfunc: str | callable = "sum",
        filters: dict[str, Any] | None = None,
        margins: bool = False,
        fill_value: Any = None,
    ) -> pd.DataFrame:
        """
        Construye una tabla cruzada.

        Parameters
        ----------
        df:
            DataFrame origen.

        index:
            Campo(s) para filas.

        columns:
            Campo(s) para columnas.

        values:
            Campo numérico.

        aggfunc:
            Función de agregación.

        filters:
            Filtros opcionales.

        margins:
            Agregar totales.

        fill_value:
            Valor para celdas vacías.
        """

        self.logger.info("Construyendo Pivot Table...")

        required_columns = []

        if isinstance(index, str):
            required_columns.append(index)
        else:
            required_columns.extend(index)

        if isinstance(columns, str):
            required_columns.append(columns)
        else:
            required_columns.extend(columns)

        required_columns.append(values)

        missing = [
            c
            for c in required_columns
            if c not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Faltan columnas requeridas: {missing}"
            )

        filtered_df = self._apply_filters(df, filters)

        if filtered_df.empty:

            self.logger.warning(
                "No existen datos para construir la vista."
            )

            return pd.DataFrame()

        pivot = pd.pivot_table(
            filtered_df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            margins=margins,
            fill_value=fill_value,
        )

        self.logger.info(
            "Pivot generado correctamente (%s).",
            pivot.shape,
        )

        return pivot


__all__ = ("PivotService",)
