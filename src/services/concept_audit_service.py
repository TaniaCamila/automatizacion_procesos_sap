from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config.concept_catalog import CURRENCY_NO_USD, CURRENCY_USD
from ..config.config import Config
from ..config.logger import LoggerManager


logger = LoggerManager.get_logger(__name__)


class ConceptAuditService:
    """
    Auditoría de conceptos detectados (BUSINESS-04).

    Usa exclusivamente las columnas generadas por BUSINESS-03:
        grupo, concepto, currency_group

    No vuelve a clasificar registros.

    BUSINESS-13A: la MATRIZ es la fuente oficial para reportes;
    este servicio no debe reconsultar concept_classifier.
    """

    REQUIRED_COLUMNS: tuple[str, ...] = ("grupo", "concepto", "currency_group")
    REPORT_COLUMNS: tuple[str, ...] = (
        "Grupo",
        "Concepto",
        "USD",
        "NO_USD",
        "TOTAL",
    )

    def __init__(
        self,
        config_obj: Config | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        self.config = config_obj or Config()
        self.logger = logger_obj or logger

    def build_report(self, matrix: pd.DataFrame) -> pd.DataFrame:
        """
        Construir tabla de auditoría a partir de la matriz ya clasificada.

        Columns de salida: Grupo, Concepto, USD, NO_USD, TOTAL
        Orden: Grupo, Concepto
        """

        if matrix is None:
            raise ValueError("La matriz proporcionada es None.")
        if not isinstance(matrix, pd.DataFrame):
            raise TypeError("La matriz debe ser un DataFrame.")

        missing = [col for col in self.REQUIRED_COLUMNS if col not in matrix.columns]
        if missing:
            raise ValueError(
                "Faltan columnas de BUSINESS-03 para auditoría: "
                + ", ".join(missing)
            )

        work = matrix.loc[:, list(self.REQUIRED_COLUMNS)].copy()
        work["grupo"] = work["grupo"].fillna("").astype(str).str.strip()
        work["concepto"] = work["concepto"].fillna("").astype(str).str.strip()
        work["currency_group"] = (
            work["currency_group"].fillna("").astype(str).str.strip().str.upper()
        )

        # Solo conceptos detectados por BUSINESS-03.
        work = work.loc[work["concepto"] != ""].copy()

        if work.empty:
            empty = pd.DataFrame(columns=list(self.REPORT_COLUMNS))
            for column in ("USD", "NO_USD", "TOTAL"):
                empty[column] = empty[column].astype(int)
            return empty

        # Separación USD / NO_USD solo vía currency_group.
        work["currency_group"] = work["currency_group"].where(
            work["currency_group"] == CURRENCY_USD,
            CURRENCY_NO_USD,
        )

        counts = (
            work.groupby(["grupo", "concepto", "currency_group"], dropna=False)
            .size()
            .unstack(fill_value=0)
        )

        for column in (CURRENCY_USD, CURRENCY_NO_USD):
            if column not in counts.columns:
                counts[column] = 0

        report = counts.reset_index().rename(
            columns={
                "grupo": "Grupo",
                "concepto": "Concepto",
                CURRENCY_USD: "USD",
                CURRENCY_NO_USD: "NO_USD",
            }
        )
        report["USD"] = report["USD"].astype(int)
        report["NO_USD"] = report["NO_USD"].astype(int)
        report["TOTAL"] = report["USD"] + report["NO_USD"]
        report = report.loc[:, list(self.REPORT_COLUMNS)]
        report = report.sort_values(
            by=["Grupo", "Concepto"],
            kind="mergesort",
        ).reset_index(drop=True)

        self.logger.info(
            "Auditoría de conceptos: %d filas (grupos detectados)",
            len(report),
        )
        return report

    def _build_output_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"CONCEPT_AUDIT_{timestamp}.xlsx"

    def export(self, report: pd.DataFrame, path: Path | None = None) -> Path:
        """Exportar el reporte a CONCEPT_AUDIT_YYYYMMDD_HHMMSS.xlsx."""

        if report is None:
            raise ValueError("El reporte proporcionado es None.")
        if not isinstance(report, pd.DataFrame):
            raise TypeError("El reporte debe ser un DataFrame.")

        output_path = path or self._build_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.to_excel(output_path, sheet_name="CONCEPT_AUDIT", index=False)
        self.logger.info("Auditoría exportada: %s", output_path.name)
        return output_path

    def generate(
        self,
        matrix: pd.DataFrame,
        path: Path | None = None,
    ) -> tuple[pd.DataFrame, Path]:
        """Construir y exportar la auditoría en un solo paso."""

        report = self.build_report(matrix)
        output_path = self.export(report, path=path)
        return report, output_path


__all__ = ("ConceptAuditService",)
