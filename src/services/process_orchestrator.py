from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config.logger import LoggerManager
from ..modules.margen.module import InformeMargenModule
from ..services.concept_audit_service import ConceptAuditService
from ..services.conceptos_sync_service import sync_conceptos_from_admin
from ..services.output_artifact_service import OutputArtifactService
from ..services.pivot_report_service import PivotReportService
from ..services.sharepoint_service import SharePointService
from ..services.concept_classifier import load as load_conceptos_admin


logger = LoggerManager.get_logger(__name__)


@dataclass
class ProcessResult:
    """Resultado consolidado del flujo orquestado (BUSINESS-08)."""

    start_time: datetime
    end_time: datetime
    duration_ms: float
    matrix_file: Path | None = None
    pivot_file: Path | None = None
    audit_file: Path | None = None
    sharepoint_ready: bool = False
    success: bool = False
    errors: list[str] = field(default_factory=list)


class ProcessOrchestrator:
    """
    Orquestador central del proceso completo (BUSINESS-08).

    Prepara el flujo end-to-end sin Microsoft Graph ni Outlook.
    SharePoint solo se consulta vía health_check (sin upload).
    """

    def __init__(
        self,
        margen_module: InformeMargenModule | None = None,
        audit_service: ConceptAuditService | None = None,
        pivot_service: PivotReportService | None = None,
        sharepoint_service: SharePointService | None = None,
        output_service: OutputArtifactService | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        self.logger = logger_obj or logger
        self.margen = margen_module or InformeMargenModule()
        self.audit_service = audit_service or ConceptAuditService()
        self.pivot_service = pivot_service or PivotReportService()
        self.sharepoint_service = sharepoint_service or SharePointService()
        self.output_service = output_service or OutputArtifactService()

    def create_matrix(self) -> Path:
        """Etapa 1: ejecutar pipeline y resolver MATRIZ_FBL1N más reciente."""

        self.logger.info("Etapa 1/4 create_matrix — inicio")
        started = time.perf_counter()
        self.margen.run()
        matrix_file = self.output_service.latest_or_raise()
        self.logger.info(
            "Etapa 1/4 create_matrix — fin (%.2f s) archivo=%s",
            time.perf_counter() - started,
            matrix_file.name,
        )
        return matrix_file

    def generate_concept_audit(self, matrix_file: Path) -> Path:
        """Etapa 2: generar CONCEPT_AUDIT a partir de la matriz."""

        self.logger.info("Etapa 2/4 generate_concept_audit — inicio")
        started = time.perf_counter()
        matrix = pd.read_excel(
            matrix_file,
            sheet_name="MATRIZ_FBL1N",
            usecols=["grupo", "concepto", "currency_group"],
            engine="calamine",
        )
        _, audit_file = self.audit_service.generate(matrix)
        self.logger.info(
            "Etapa 2/4 generate_concept_audit — fin (%.2f s) archivo=%s",
            time.perf_counter() - started,
            audit_file.name,
        )
        return audit_file

    def generate_pivot(self, matrix_file: Path) -> Path:
        """Etapa 3: generar PIVOT_MARGEN a partir de la matriz."""

        self.logger.info("Etapa 3/4 generate_pivot — inicio")
        started = time.perf_counter()
        _, pivot_file = self.pivot_service.generate(path=matrix_file)
        self.logger.info(
            "Etapa 3/4 generate_pivot — fin (%.2f s) archivo=%s",
            time.perf_counter() - started,
            pivot_file.name,
        )
        return pivot_file

    def check_sharepoint(self) -> bool:
        """Etapa 4: health_check de SharePoint (sin upload ni Graph)."""

        self.logger.info("Etapa 4/4 sharepoint_health_check — inicio")
        started = time.perf_counter()
        status = self.sharepoint_service.health_check()
        ready = bool(status.get("configured"))
        self.logger.info(
            "Etapa 4/4 sharepoint_health_check — fin (%.2f s) ready=%s missing=%s",
            time.perf_counter() - started,
            ready,
            status.get("missing", []),
        )
        return ready

    def run(self) -> ProcessResult:
        """
        Ejecutar el flujo completo preparado:

            1. create_matrix
            2. generate_concept_audit
            3. generate_pivot
            4. sharepoint health_check
        """

        start_time = datetime.now()
        wall_started = time.perf_counter()
        errors: list[str] = []
        matrix_file: Path | None = None
        audit_file: Path | None = None
        pivot_file: Path | None = None
        sharepoint_ready = False

        self.logger.info("=" * 70)
        self.logger.info("ProcessOrchestrator — inicio")
        self.logger.info("=" * 70)

        # BUSINESS-12A: sincronizar CONCEPTOS desde ADMIN antes del pipeline.
        try:
            sync_conceptos_from_admin()
            load_conceptos_admin()
        except Exception as exc:  # noqa: BLE001
            message = f"sync_conceptos: {exc}"
            errors.append(message)
            self.logger.exception(message)

        try:
            matrix_file = self.create_matrix()
        except Exception as exc:  # noqa: BLE001
            message = f"create_matrix: {exc}"
            errors.append(message)
            self.logger.exception(message)

        if matrix_file is not None:
            try:
                audit_file = self.generate_concept_audit(matrix_file)
            except Exception as exc:  # noqa: BLE001
                message = f"generate_concept_audit: {exc}"
                errors.append(message)
                self.logger.exception(message)

            try:
                pivot_file = self.generate_pivot(matrix_file)
            except Exception as exc:  # noqa: BLE001
                message = f"generate_pivot: {exc}"
                errors.append(message)
                self.logger.exception(message)

        try:
            sharepoint_ready = self.check_sharepoint()
        except Exception as exc:  # noqa: BLE001
            message = f"sharepoint_health_check: {exc}"
            errors.append(message)
            self.logger.exception(message)

        end_time = datetime.now()
        duration_ms = (time.perf_counter() - wall_started) * 1000
        success = (
            matrix_file is not None
            and audit_file is not None
            and pivot_file is not None
            and not errors
        )

        if success:
            self.logger.info("Proceso finalizado correctamente")
        else:
            self.logger.error(
                "Proceso finalizado con errores (%d)",
                len(errors),
            )

        self.logger.info("=" * 70)
        self.logger.info(
            "ProcessOrchestrator — fin success=%s duration_ms=%.1f",
            success,
            duration_ms,
        )
        self.logger.info("=" * 70)

        return ProcessResult(
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            matrix_file=matrix_file,
            pivot_file=pivot_file,
            audit_file=audit_file,
            sharepoint_ready=sharepoint_ready,
            success=success,
            errors=errors,
        )


__all__ = (
    "ProcessOrchestrator",
    "ProcessResult",
)
