from __future__ import annotations

import logging

import pandas as pd

from ..config.logger import LoggerManager
from ..services.concept_classifier import classify, pattern_matches, to_standard
from ..services.conceptos_service import ConceptosService
from ..services.moneda_service import MonedaService
from ..services.sociedades_service import SociedadesService


logger = LoggerManager.get_logger(__name__)


class MatrizService:
    """
    Servicio encargado de construir la matriz de datos
    a partir del archivo FBL1N.

    Flujo:

        1. Filtrar moneda.
        2. Buscar concepto (catálogo Excel + BUSINESS-02).
        3. Buscar sociedad.
        4. Obtener mes.
        5. Construir matriz final.

    BUSINESS-13A — Modelo de datos definitivo:

        La MATRIZ es la FUENTE OFICIAL para todos los reportes.
        La clasificación se ejecuta una sola vez aquí y se persisten
        las columnas:

            - concepto_detectado
            - concepto
            - grupo
            - currency_group
            - tipo (COM / NO_COM)

        Ningún reporte (Pivot CLP, TD_CLP_NO_COM, TD_CLP_COM_2026,
        auditoría, ni futuros) debe volver a consultar
        concept_classifier: deben leer estas columnas de la MATRIZ.
    """

    def __init__(
        self,
        sociedades: SociedadesService,
        monedas: MonedaService,
        conceptos: ConceptosService,
        logger_obj: logging.Logger | None = None,
    ) -> None:

        self.logger = logger_obj or logger

        self.sociedades = sociedades
        self.monedas = monedas
        self.conceptos = conceptos

    def _resolve_column(
        self,
        df: pd.DataFrame,
        *candidates: str,
    ) -> str | None:
        """
        Resolver la primera columna disponible entre varias opciones.
        """

        for column in candidates:
            if column in df.columns:
                return column

        return None

    def _catalog_concepts(self) -> list[str]:
        """
        Obtener los conceptos del catálogo en orden estable.
        """

        values = getattr(self.conceptos, "values", None)
        if callable(values):
            return list(values())

        items = getattr(self.conceptos, "get_items", None)
        if callable(items):
            return sorted(items())

        return []

    def _detect_concept(self, value: object) -> str:
        """
        Detectar un concepto válido a partir del texto del documento.

        Regla: longest match first. Si varios conceptos del catálogo
        coinciden (igualdad exacta o substring), gana el más largo.
        Empates de longitud se resuelven en orden alfabético.

        BUSINESS-16: la detección respeta las reglas restringidas del
        clasificador (p. ej. EDP_ solo con texto EDP_[).
        """

        if pd.isna(value):
            return ""

        text = str(value).strip()

        if not text:
            return ""

        matches = [
            concept
            for concept in self._catalog_concepts()
            if pattern_matches(concept, text)
        ]

        if not matches:
            return ""

        matches.sort(key=lambda concept: (-len(concept), concept))
        return matches[0]

    def _enrich_concepts(
        self,
        texto: object,
        moneda: object,
    ) -> tuple[str, str, str, str, str, str]:
        """
        Un solo paso por fila: catálogo Excel + clasificador de negocio.

        Retorna:
            concepto_detectado, concepto_estado, concepto, grupo,
            currency_group, tipo

        BUG-01: si el clasificador de negocio detecta `concepto`,
        sincroniza `concepto_detectado` / `concepto_estado` con ese valor.
        """

        detected = self._detect_concept(texto)
        business = classify(texto, moneda if pd.notna(moneda) else None)
        concepto = business["concepto"] or ""
        grupo = business["grupo"] or ""
        currency_group = business["currency_group"]
        tipo = business["tipo"] or ""

        if concepto:
            detected = concepto
            estado = "Identificado"
        else:
            estado = "Identificado" if detected else "No identificado"

        # BUSINESS-12B: persistir solo Concepto estándar (nunca variantes alias).
        detected = to_standard(detected) if detected else ""
        concepto = to_standard(concepto) if concepto else ""

        return (
            detected,
            estado,
            concepto,
            grupo,
            currency_group,
            tipo,
        )

    def _format_month(self, value: object) -> str:
        """
        Convertir una fecha a formato AAAA-MM cuando sea posible.
        """

        if pd.isna(value):
            return ""

        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m")

        try:
            dt = pd.to_datetime(value, dayfirst=False, errors="coerce")
        except Exception:
            return ""

        if pd.isna(dt):
            return ""

        return dt.strftime("%Y-%m")

    def _format_year(self, value: object) -> str:
        """
        Convertir una fecha a formato AAAA cuando sea posible.
        """

        if pd.isna(value):
            return ""

        if isinstance(value, pd.Timestamp):
            return str(value.year)

        try:
            dt = pd.to_datetime(value, dayfirst=False, errors="coerce")
        except Exception:
            return ""

        if pd.isna(dt):
            return ""

        return str(dt.year)

    def create_matrix(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Construir la matriz final con enriquecimiento de catálogos.
        """

        self.logger.info(
            "Construyendo matriz (%d registros)...",
            len(df),
        )

        matrix = df.copy()

        sociedad_column = self._resolve_column(
            matrix,
            "sociedad",
            "Sociedad",
        )
        moneda_column = self._resolve_column(
            matrix,
            "moneda_del_documento",
            "Moneda del documento",
        )
        texto_column = self._resolve_column(
            matrix,
            "texto_cabdocumento",
            "Texto cab.documento",
        )
        fecha_column = self._resolve_column(
            matrix,
            "fecha_compensacion",
            "Fecha compensación",
        )

        if sociedad_column is not None:
            matrix["sociedad_nombre"] = matrix[sociedad_column].apply(
                lambda value: self.sociedades.get_name(str(value).strip())
                if pd.notna(value) and str(value).strip()
                else ""
            )
        else:
            matrix["sociedad_nombre"] = ""

        if moneda_column is not None:
            matrix["moneda_valida"] = matrix[moneda_column].apply(
                lambda value: bool(str(value).strip()) and self.monedas.exists(str(value).strip())
                if pd.notna(value)
                else False
            )
        else:
            matrix["moneda_valida"] = False

        moneda_series = (
            matrix[moneda_column]
            if moneda_column is not None
            else pd.Series([None] * len(matrix), index=matrix.index)
        )
        texto_series = (
            matrix[texto_column]
            if texto_column is not None
            else pd.Series([None] * len(matrix), index=matrix.index)
        )

        # Un solo recorrido para catálogo Excel + BUSINESS-02/03.
        enriched = [
            self._enrich_concepts(texto, moneda)
            for texto, moneda in zip(texto_series, moneda_series, strict=True)
        ]
        concept_frame = pd.DataFrame(
            enriched,
            columns=[
                "concepto_detectado",
                "concepto_estado",
                "concepto",
                "grupo",
                "currency_group",
                "tipo",
            ],
            index=matrix.index,
        )
        matrix[concept_frame.columns] = concept_frame

        if fecha_column is not None:
            matrix["mes_compensacion"] = matrix[fecha_column].apply(
                self._format_month
            )
            matrix["anio_compensacion"] = matrix[fecha_column].apply(
                lambda value: self._format_year(value)
            )
        else:
            matrix["mes_compensacion"] = ""
            matrix["anio_compensacion"] = ""

        return matrix


__all__ = ("MatrizService",)
