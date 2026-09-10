from __future__ import annotations

from .config.logger import LoggerManager
from .modules.margen.module import InformeMargenModule
from .services.concept_classifier import load as load_conceptos_admin
from .services.conceptos_sync_service import sync_conceptos_from_admin


logger = LoggerManager.get_logger(__name__)


class Application:
    """
    Orquestador principal de la aplicación.

    Responsabilidades:

        1. Instanciar y ejecutar módulos de informe.
    """

    def __init__(self) -> None:

        self.logger = logger

        # Módulo del Informe Margen
        self.informe_margen = InformeMargenModule()

    def run(self) -> None:
        """
        Ejecutar el flujo completo de la aplicación.
        """

        self.logger.info("=" * 60)
        self.logger.info("Inicio de la aplicación")
        self.logger.info("=" * 60)

        # BUSINESS-12A: negocio administra ADMIN; CONCEPTOS se sincroniza solo.
        sync_conceptos_from_admin()
        load_conceptos_admin()

        # Ejecutar el Informe Margen
        self.informe_margen.run()

        self.logger.info("=" * 60)
        self.logger.info("Aplicación finalizada correctamente")
        self.logger.info("=" * 60)


__all__ = ("Application",)
