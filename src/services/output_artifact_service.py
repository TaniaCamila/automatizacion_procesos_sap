from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config.config import Config
from ..config.logger import LoggerManager


logger = LoggerManager.get_logger(__name__)


class OutputArtifactService:
    """
    Lectura de artefactos Excel generados por el pipeline.

    No ejecuta el pipeline ni recalcula FBL1N.
    """

    PATTERN = "MATRIZ_FBL1N_*.xlsx"

    def __init__(
        self,
        config_obj: Config | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        self.config = config_obj or Config()
        self.logger = logger_obj or logger
        self._sheet_cache: dict[tuple[str, str, float], pd.DataFrame] = {}

    @property
    def output_dir(self) -> Path:
        return self.config.output_dir

    def list_outputs(self) -> list[Path]:
        """Listar archivos MATRIZ ordenados del más reciente al más antiguo."""

        files = sorted(
            self.output_dir.glob(self.PATTERN),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return files

    def latest(self) -> Path | None:
        """Obtener el archivo MATRIZ más reciente, o None si no existe."""

        files = self.list_outputs()
        if not files:
            self.logger.warning(
                "No se encontraron artefactos en %s",
                self.output_dir,
            )
            return None
        return files[0]

    def latest_or_raise(self) -> Path:
        path = self.latest()
        if path is None:
            raise FileNotFoundError(
                f"No hay archivos {self.PATTERN} en {self.output_dir}"
            )
        return path

    def file_metadata(self, path: Path) -> dict[str, str | float | int]:
        """Metadatos básicos de un artefacto."""

        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        return {
            "name": path.name,
            "path": str(path),
            "size_bytes": stat.st_size,
            "modified_at": modified.isoformat(timespec="seconds"),
            "modified_display": modified.strftime("%d/%m/%Y · %H:%M"),
            "mtime": stat.st_mtime,
        }

    def read_sheet(
        self,
        path: Path,
        sheet_name: str,
        usecols: list[str] | None = None,
        nrows: int | None = None,
    ) -> pd.DataFrame:
        """
        Leer una hoja del Excel con caché por (archivo, hoja, mtime).
        """

        mtime = path.stat().st_mtime
        cache_key = (str(path.resolve()), sheet_name, mtime)

        # Caché completa solo cuando no se piden usecols/nrows especiales
        if usecols is None and nrows is None and cache_key in self._sheet_cache:
            return self._sheet_cache[cache_key].copy()

        self.logger.info(
            "Leyendo hoja '%s' de %s",
            sheet_name,
            path.name,
        )

        kwargs: dict = {"sheet_name": sheet_name}
        if usecols is not None:
            kwargs["usecols"] = usecols
        if nrows is not None:
            kwargs["nrows"] = nrows

        df = pd.read_excel(path, **kwargs)

        if usecols is None and nrows is None:
            self._sheet_cache[cache_key] = df.copy()

        return df

    def sheet_names(self, path: Path) -> list[str]:
        excel = pd.ExcelFile(path)
        names = list(excel.sheet_names)
        excel.close()
        return names


__all__ = ("OutputArtifactService",)
