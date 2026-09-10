from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config.logger import LoggerManager
from ..config.sharepoint_config import SharePointConfig


logger = LoggerManager.get_logger(__name__)


class SharePointService:
    """
    Infraestructura SharePoint (BUSINESS-07).

    Prepara la arquitectura de integración sin conexiones reales.
    Las operaciones de red se implementarán en una fase posterior.
    """

    def __init__(
        self,
        config: SharePointConfig | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        self.config = config or SharePointConfig.from_env()
        self.logger = logger_obj or logger
        self._connected = False

    def connect(self) -> None:
        """Establecer sesión con SharePoint (pendiente de implementación)."""

        raise NotImplementedError(
            "SharePointService.connect() aún no está implementado."
        )

    def upload_file(self, path: Path | str) -> None:
        """Subir un archivo a la carpeta objetivo (pendiente)."""

        raise NotImplementedError(
            "SharePointService.upload_file() aún no está implementado."
        )

    def upload_folder(self, path: Path | str) -> None:
        """Subir el contenido de una carpeta (pendiente)."""

        raise NotImplementedError(
            "SharePointService.upload_folder() aún no está implementado."
        )

    def file_exists(self, filename: str) -> bool:
        """Verificar si un archivo existe en la biblioteca (pendiente)."""

        raise NotImplementedError(
            "SharePointService.file_exists() aún no está implementado."
        )

    def list_files(self) -> list[str]:
        """Listar archivos de la carpeta objetivo (pendiente)."""

        raise NotImplementedError(
            "SharePointService.list_files() aún no está implementado."
        )

    def health_check(self) -> dict[str, Any]:
        """
        Evaluar si la configuración local está completa.

        No realiza llamadas de red.
        """

        missing = self.config.missing_fields()
        configured = len(missing) == 0
        status = {
            "configured": configured,
            "missing": missing,
        }
        self.logger.info(
            "SharePoint health_check: configured=%s missing=%s",
            configured,
            missing,
        )
        return status


__all__ = ("SharePointService",)
