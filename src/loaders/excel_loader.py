from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..config.config import Config
from ..config.logger import LoggerManager


config = Config()
logger = LoggerManager.get_logger(__name__)


class ExcelLoader:
    """
    Cargador centralizado de archivos Excel del proyecto.

    Responsabilidades:
        - Verificar que el archivo exista.
        - Leer archivos Excel.
        - Registrar eventos mediante LoggerManager.
    """

    def __init__(
        self,
        config_obj: Config | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:

        self.config = config_obj or config
        self.logger = logger_obj or logger

    def _read_excel(
        self,
        path: Path,
    ) -> pd.DataFrame:
        """
        Leer un archivo Excel.

        Args:
            path: Ruta del archivo.

        Returns:
            DataFrame con la información del Excel.

        Raises:
            FileNotFoundError: Si el archivo no existe.
        """

        path = Path(path)

        if not path.exists():
            self.logger.error(
                "Archivo no encontrado: %s",
                path.name,
            )
            raise FileNotFoundError(path.name)

        try:

            dataframe = pd.read_excel(path)

            return dataframe

        except Exception:

            self.logger.exception(
                "Error leyendo el archivo %s",
                path.name,
            )

            raise

    def load_excel(
        self,
        path: Path,
    ) -> pd.DataFrame:
        """
        Cargar cualquier archivo Excel.

        Este método es utilizado por CatalogService para evitar
        duplicar lógica de lectura.

        Args:
            path: Ruta del archivo Excel.

        Returns:
            DataFrame cargado.
        """

        path = Path(path)

        self.logger.info(
            "Cargando archivo %s",
            path.name,
        )

        dataframe = self._read_excel(path)

        self.logger.info(
            "Archivo %s cargado correctamente (%d registros).",
            path.name,
            len(dataframe),
        )

        return dataframe

    def is_locked(self, path: Path) -> bool:
        """True si el archivo no puede abrirse para lectura (en uso o inaccesible)."""

        path = Path(path)
        if not path.exists():
            return False
        try:
            with path.open("rb"):
                return False
        except OSError:
            return True

    def load_fbl1n(self, path: Path | None = None) -> pd.DataFrame:
        """
        Cargar un archivo FBL1N.

        Sin argumento usa la ruta histórica de configuración.
        Las llamadas existentes `load_fbl1n()` permanecen intactas.
        """

        target = Path(path) if path is not None else self.config.fbl1n_path
        return self.load_excel(target)

    def load_sociedades(self) -> pd.DataFrame:
        """
        Cargar el catálogo de sociedades.
        """

        return self.load_excel(
            self.config.sociedades_path,
        )

    def load_monedas(self) -> pd.DataFrame:
        """
        Cargar el catálogo de monedas.
        """

        return self.load_excel(
            self.config.moneda_path,
        )

    def load_conceptos(self) -> pd.DataFrame:
        """
        Cargar el catálogo de conceptos.
        """

        return self.load_excel(
            self.config.conceptos_path,
        )


__all__ = ("ExcelLoader",)
