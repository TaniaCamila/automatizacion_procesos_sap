from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from python_calamine import CalamineWorkbook

from ..config.config import Config
from ..config.logger import LoggerManager
from ..modules.margen.module import InformeMargenModule
from ..services import concept_classifier
from ..services.output_artifact_service import OutputArtifactService
from ..services.sharepoint_service import SharePointService


"""
BUSINESS-14 — Centro de Validación Funcional.

Módulo independiente que valida que el proceso completo cumple las
reglas de negocio antes de publicar resultados. Solo LEE artefactos
y catálogos; no modifica clasificación, MATRIZ ni reportes.
"""


logger = LoggerManager.get_logger(__name__)

REPORT_TITLE = "CENTRO DE VALIDACIÓN FUNCIONAL"

MATRIX_REQUIRED_COLUMNS: tuple[str, ...] = (
    "concepto_detectado",
    "concepto",
    "grupo",
    "currency_group",
    "tipo",
)

TD_SHEETS: tuple[str, ...] = (
    InformeMargenModule._TD_SHEET_NO_COM,
    InformeMargenModule._TD_SHEET_COM,
    InformeMargenModule._TD_SHEET_CLP_USD_NO_COM,
    InformeMargenModule._TD_SHEET_CLP_USD_COM,
)

POWERBI_SHEETS: tuple[str, ...] = ("KPIS", "METADATA")

_AMOUNT_TOLERANCE = 0.01


@dataclass(frozen=True)
class CheckResult:
    """Resultado individual de una validación."""

    name: str
    ok: bool
    detail: str

    @property
    def status(self) -> str:
        return "OK" if self.ok else "ERROR"


@dataclass
class ValidationReport:
    """Resumen del Centro de Validación Funcional."""

    checks: list[CheckResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        return all(check.ok for check in self.checks)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            REPORT_TITLE,
            self.generated_at.strftime("%d/%m/%Y %H:%M:%S"),
            "=" * 60,
        ]
        for index, check in enumerate(self.checks, start=1):
            lines.append(
                f"{index}. {check.name:<16} {check.status:<5} — {check.detail}"
            )
        lines.append("-" * 60)
        lines.append(
            "RESULTADO GLOBAL: " + ("OK" if self.success else "ERROR")
        )
        lines.append("=" * 60)
        return "\n".join(lines)


class FunctionalValidationService:
    """
    Centro de Validación Funcional (BUSINESS-14).

    Valida catálogo, MATRIZ, normalización, dinámicas, importes,
    modelo Power BI y SharePoint (solo health check).

    BUSINESS-13A: consume exclusivamente la información persistida
    en la MATRIZ para los checks de reportes.
    """

    def __init__(
        self,
        config_obj: Config | None = None,
        output_service: OutputArtifactService | None = None,
        sharepoint_service: SharePointService | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        self.config = config_obj or Config()
        self.output_service = output_service or OutputArtifactService(
            config_obj=self.config
        )
        self.sharepoint_service = sharepoint_service or SharePointService()
        self.logger = logger_obj or logger

    # ------------------------------------------------------------------
    # 1. Catálogo
    # ------------------------------------------------------------------
    def validate_catalog(self) -> CheckResult:
        """Conceptos activos, estándar, grupo y tipo del ADMIN."""

        try:
            catalog = concept_classifier.ensure_loaded()
        except Exception as exc:  # noqa: BLE001
            return CheckResult("Catálogo", False, f"No se pudo cargar: {exc}")

        rows = catalog.rows
        if not rows:
            return CheckResult(
                "Catálogo",
                False,
                "CONCEPTOS_ADMIN sin conceptos activos",
            )

        issues: list[str] = []
        for row in rows:
            if not row.estandar:
                issues.append(f"'{row.encontrado}' sin Concepto estándar")
            if not row.grupo:
                issues.append(f"'{row.encontrado}' sin Grupo")
            if row.tipo not in ("COM", "NO_COM"):
                issues.append(f"'{row.encontrado}' Tipo inválido: {row.tipo}")

        if issues:
            return CheckResult("Catálogo", False, "; ".join(issues[:5]))

        groups = len({row.grupo for row in rows})
        com = sum(1 for row in rows if row.tipo == "COM")
        return CheckResult(
            "Catálogo",
            True,
            f"{len(rows)} conceptos activos, {groups} grupos, "
            f"{com} COM / {len(rows) - com} NO_COM",
        )

    # ------------------------------------------------------------------
    # 2. MATRIZ
    # ------------------------------------------------------------------
    def validate_matrix(self, matrix: pd.DataFrame) -> CheckResult:
        """Existencia del modelo de datos definitivo (BUSINESS-13A)."""

        missing = [
            column
            for column in MATRIX_REQUIRED_COLUMNS
            if column not in matrix.columns
        ]
        if missing:
            return CheckResult(
                "MATRIZ",
                False,
                "Faltan columnas: " + ", ".join(missing),
            )
        return CheckResult(
            "MATRIZ",
            True,
            f"{len(matrix)} filas con las {len(MATRIX_REQUIRED_COLUMNS)} "
            "columnas del modelo",
        )

    # ------------------------------------------------------------------
    # 3. Normalización
    # ------------------------------------------------------------------
    def validate_normalization(self, matrix: pd.DataFrame) -> CheckResult:
        """Sin variantes alias tras aplicar Concepto estándar."""

        columns = [
            column
            for column in ("concepto_detectado", "concepto")
            if column in matrix.columns
        ]
        if not columns:
            return CheckResult(
                "Normalización",
                False,
                "Sin columnas de concepto en la MATRIZ",
            )

        variants: set[str] = set()
        for column in columns:
            values = (
                matrix[column].fillna("").astype(str).str.strip().unique()
            )
            for value in values:
                if value and concept_classifier.to_standard(value) != value:
                    variants.add(value)

        if variants:
            shown = ", ".join(sorted(variants)[:5])
            return CheckResult(
                "Normalización",
                False,
                f"Variantes sin normalizar: {shown}",
            )
        return CheckResult(
            "Normalización",
            True,
            "Todos los conceptos persistidos son Concepto estándar",
        )

    # ------------------------------------------------------------------
    # 4. Dinámicas
    # ------------------------------------------------------------------
    def _matrix_expected_clp_total(self, matrix: pd.DataFrame) -> float:
        """
        Total esperado de las dinámicas: TODOS los registros CLP tras
        la exclusión BUSINESS-01 (reutiliza la lógica del módulo).

        BUSINESS-15A/18A: COM/NO_COM y segmento CLP_USD_* particionan
        el mismo universo CLP; la suma de las cuatro dinámicas debe
        igualar el total CLP de la MATRIZ (no se pierden registros).
        """

        module = InformeMargenModule.__new__(InformeMargenModule)
        module.logger = self.logger

        filtered, _ = module.apply_clp_pivot_exclusions(matrix)

        if "moneda_del_documento" in filtered.columns:
            moneda = (
                filtered["moneda_del_documento"].fillna("").astype(str).str.strip()
            )
            filtered = filtered.loc[moneda == "CLP"]

        return float(
            pd.to_numeric(
                filtered.get("importe_en_moneda_doc", pd.Series(dtype=float)),
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )

    @staticmethod
    def _td_grand_total(td: pd.DataFrame) -> float:
        """Suma de Total de una dinámica excluyendo la fila All."""

        if td is None or td.empty or "Total" not in td.columns:
            return 0.0
        concept_col = InformeMargenModule._TD_CONCEPT_COLUMN
        work = td
        if concept_col in td.columns:
            concepts = td[concept_col].fillna("").astype(str).str.strip()
            work = td.loc[~concepts.isin(["All", "Total"])]
        return float(
            pd.to_numeric(work["Total"], errors="coerce").fillna(0).sum()
        )

    def validate_dynamics(
        self,
        matrix: pd.DataFrame,
        dynamics: dict[str, pd.DataFrame],
    ) -> CheckResult:
        """TD_CLP_* + CLP_USD_* = total CLP de la MATRIZ (BUSINESS-18A)."""

        missing = [name for name in TD_SHEETS if name not in dynamics]
        if missing:
            return CheckResult(
                "Dinámicas",
                False,
                "Faltan dinámicas: " + ", ".join(missing),
            )

        actual = sum(
            self._td_grand_total(dynamics[name]) for name in TD_SHEETS
        )
        expected = self._matrix_expected_clp_total(matrix)

        if abs(actual - expected) > _AMOUNT_TOLERANCE:
            return CheckResult(
                "Dinámicas",
                False,
                f"TD suman {actual:,.2f} vs MATRIZ {expected:,.2f}",
            )
        return CheckResult(
            "Dinámicas",
            True,
            f"TD_CLP + CLP_USD = MATRIZ ({actual:,.2f})",
        )

    # ------------------------------------------------------------------
    # 5. Importes
    # ------------------------------------------------------------------
    def validate_amounts(
        self,
        dynamics: dict[str, pd.DataFrame],
    ) -> CheckResult:
        """Suma mensual = Total en cada fila de cada dinámica."""

        month_labels = list(InformeMargenModule._TD_MONTH_LABELS)
        concept_col = InformeMargenModule._TD_CONCEPT_COLUMN
        errors: list[str] = []
        rows_checked = 0

        for name, td in dynamics.items():
            if td is None or td.empty:
                continue
            available = [m for m in month_labels if m in td.columns]
            if not available or "Total" not in td.columns:
                errors.append(f"{name}: estructura incompleta")
                continue
            for _, row in td.iterrows():
                concept = str(row.get(concept_col, "")).strip()
                if concept in ("All", "Total"):
                    continue
                rows_checked += 1
                months_sum = float(
                    pd.to_numeric(
                        pd.Series([row[m] for m in available]),
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )
                total = float(row["Total"] or 0)
                if abs(months_sum - total) > _AMOUNT_TOLERANCE:
                    errors.append(
                        f"{name}/{concept}: meses={months_sum:,.2f} "
                        f"total={total:,.2f}"
                    )

        if errors:
            return CheckResult("Importes", False, "; ".join(errors[:5]))
        return CheckResult(
            "Importes",
            True,
            f"Suma mensual = Total en {rows_checked} filas",
        )

    # ------------------------------------------------------------------
    # 6. Modelo Power BI
    # ------------------------------------------------------------------
    def validate_powerbi_model(
        self,
        matrix_file: Path | None,
        pivot_file: Path | None,
    ) -> CheckResult:
        """Hojas KPIS, METADATA, TD_CLP_* y CLP_USD_*."""

        missing: list[str] = []

        if matrix_file is None or not Path(matrix_file).exists():
            missing.extend(TD_SHEETS)
        else:
            sheets = set(
                CalamineWorkbook.from_path(str(matrix_file)).sheet_names
            )
            missing.extend(name for name in TD_SHEETS if name not in sheets)

        if pivot_file is None or not Path(pivot_file).exists():
            missing.extend(POWERBI_SHEETS)
            missing.extend(TD_SHEETS)
        else:
            sheets = set(
                CalamineWorkbook.from_path(str(pivot_file)).sheet_names
            )
            missing.extend(
                name for name in POWERBI_SHEETS if name not in sheets
            )
            missing.extend(name for name in TD_SHEETS if name not in sheets)

        if missing:
            return CheckResult(
                "Modelo Power BI",
                False,
                "Faltan hojas: " + ", ".join(missing),
            )
        return CheckResult(
            "Modelo Power BI",
            True,
            "KPIS, METADATA, TD_CLP_* y CLP_USD_* presentes",
        )

    # ------------------------------------------------------------------
    # 7. SharePoint
    # ------------------------------------------------------------------
    def validate_sharepoint(self) -> CheckResult:
        """Solo health check (BUSINESS-07); sin conexiones reales."""

        try:
            health = self.sharepoint_service.health_check()
        except Exception as exc:  # noqa: BLE001
            return CheckResult("SharePoint", False, f"Health check falló: {exc}")

        configured = bool(health.get("configured"))
        missing = health.get("missing") or []
        detail = (
            "Health check OK — configuración completa"
            if configured
            else "Health check OK — pendiente: " + ", ".join(missing)
        )
        return CheckResult("SharePoint", True, detail)

    # ------------------------------------------------------------------
    # Carga de artefactos
    # ------------------------------------------------------------------
    def _load_matrix_columns(self, matrix_file: Path) -> pd.DataFrame:
        """
        Leer de la hoja MATRIZ_FBL1N solo las columnas necesarias
        (streaming calamine; el archivo puede superar 15 MB).
        """

        wanted = [
            *MATRIX_REQUIRED_COLUMNS,
            "moneda_del_documento",
            "importe_en_moneda_doc",
            "mes_compensacion",
            "Texto cab.documento",
            "texto_cabdocumento",
        ]

        workbook = CalamineWorkbook.from_path(str(matrix_file))
        sheet = workbook.get_sheet_by_name("MATRIZ_FBL1N")
        rows = sheet.iter_rows()
        header = [
            str(cell).strip() if cell is not None else ""
            for cell in next(rows)
        ]
        indexes = {
            name: header.index(name) for name in wanted if name in header
        }

        data = [
            {
                name: (row[i] if i < len(row) else None)
                for name, i in indexes.items()
            }
            for row in rows
        ]
        return pd.DataFrame(data)

    def _load_dynamics(self, matrix_file: Path) -> dict[str, pd.DataFrame]:
        dynamics: dict[str, pd.DataFrame] = {}
        sheets = set(CalamineWorkbook.from_path(str(matrix_file)).sheet_names)
        for name in TD_SHEETS:
            if name in sheets:
                dynamics[name] = pd.read_excel(matrix_file, sheet_name=name)
        return dynamics

    def _latest_pivot_file(self) -> Path | None:
        files = sorted(
            self.config.output_dir.glob("PIVOT_MARGEN_*.xlsx"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return files[0] if files else None

    # ------------------------------------------------------------------
    # Ejecución completa
    # ------------------------------------------------------------------
    def run(
        self,
        matrix: pd.DataFrame | None = None,
        dynamics: dict[str, pd.DataFrame] | None = None,
        matrix_file: Path | None = None,
        pivot_file: Path | None = None,
    ) -> ValidationReport:
        """
        Ejecutar las 7 validaciones y construir el resumen.

        Sin argumentos, valida los últimos artefactos generados.
        """

        report = ValidationReport()

        report.checks.append(self._safe(self.validate_catalog))

        if matrix is None:
            matrix_file = matrix_file or self.output_service.latest()
            if matrix_file is not None:
                try:
                    matrix = self._load_matrix_columns(matrix_file)
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception("No se pudo leer la MATRIZ")
                    matrix = None
                    report.checks.append(
                        CheckResult("MATRIZ", False, f"Lectura falló: {exc}")
                    )

        if dynamics is None and matrix_file is not None:
            try:
                dynamics = self._load_dynamics(matrix_file)
            except Exception:  # noqa: BLE001
                self.logger.exception("No se pudieron leer las dinámicas")
                dynamics = {}

        dynamics = dynamics or {}

        if matrix is not None:
            report.checks.append(
                self._safe(lambda: self.validate_matrix(matrix))
            )
            report.checks.append(
                self._safe(lambda: self.validate_normalization(matrix))
            )
            report.checks.append(
                self._safe(lambda: self.validate_dynamics(matrix, dynamics))
            )
        elif not any(check.name == "MATRIZ" for check in report.checks):
            report.checks.append(
                CheckResult("MATRIZ", False, "Sin artefacto MATRIZ_FBL1N")
            )

        report.checks.append(
            self._safe(lambda: self.validate_amounts(dynamics))
        )
        report.checks.append(
            self._safe(
                lambda: self.validate_powerbi_model(
                    matrix_file,
                    pivot_file or self._latest_pivot_file(),
                )
            )
        )
        report.checks.append(self._safe(self.validate_sharepoint))

        for line in report.summary().splitlines():
            self.logger.info(line)

        return report

    def _safe(self, check) -> CheckResult:
        """Ejecutar un check capturando errores inesperados."""

        try:
            return check()
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Validación falló")
            return CheckResult("Validación", False, str(exc))


__all__ = (
    "CheckResult",
    "FunctionalValidationService",
    "ValidationReport",
    "REPORT_TITLE",
)
