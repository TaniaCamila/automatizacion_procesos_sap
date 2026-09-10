from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ...config.config import (
    FBL1N_COMPENSATION_CUTOFF,
    FBL1N_FUTURE_ENABLED,
    FBL1N_FUTURE_PATH,
)
from ...config.logger import LoggerManager
from ...loaders.excel_loader import ExcelLoader
from ...processors.fbl1n_processor import FBL1NProcessor
from ...reports.excel_report import ExcelReport
from ...services.conceptos_service import ConceptosService
from ...services.matriz_service import MatrizService
from ...services.moneda_service import MonedaService
from ...services.pivot_service import PivotService
from ...services.sociedades_service import SociedadesService


logger = LoggerManager.get_logger(__name__)


class InformeMargenModule:
    """
    Módulo de negocio del Informe Margen.

    Este módulo únicamente orquesta el flujo.
    Toda la lógica de negocio permanece en los servicios existentes.

    Flujo:

        1. Cargar catálogos.
        2. Leer FBL1N.
        3. Procesar información.
        4. Construir la matriz.
        5. Generar vistas analíticas.
        6. Exportar Excel.

    Futuras etapas:

        - SAP GUI
        - Power BI
        - Outlook
        - OneDrive / SharePoint
    """

    _NO_CLASIFICADOS_COLUMNS: tuple[tuple[str, ...], ...] = (
        ("Texto cab.documento", "texto_cabdocumento"),
        ("Importe en moneda doc.", "importe_en_moneda_doc"),
        ("Moneda del documento", "moneda_del_documento"),
        ("Fecha compensación", "fecha_compensacion"),
        ("Sociedad", "sociedad"),
        ("sociedad_nombre",),
        ("moneda_valida",),
        ("concepto_estado",),
        ("mes_compensacion",),
        ("anio_compensacion",),
    )

    # Regla BUSINESS-01: excluir del Pivot CLP únicamente.
    _CLP_EXCLUDED_CONCEPT = "PEA_[DEDC]"
    _CLP_EXCLUDED_TEXT_TOKEN = "USD"

    # BUSINESS-13: estructura unificada de tablas dinámicas CLP.
    _TD_MONTH_LABELS: tuple[str, ...] = (
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )
    _TD_SHEET_NO_COM = "TD_CLP_NO_COM"
    _TD_SHEET_COM = "TD_CLP_COM_2026"
    _TD_SHEET_CLP_USD_NO_COM = "CLP_USD_NO_COM"
    _TD_SHEET_CLP_USD_COM = "CLP_USD_COM"
    _TD_CONCEPT_COLUMN = "Concepto de Pago"
    _TD_PROVEEDOR_COLUMN = "Proveedor"
    _TD_PROVEEDOR_SOURCE = ("Name", "name")

    # BUSINESS-18A/18B — Segmentación CLP pagos USD (sin reclasificar).
    _CLP_USD_SOCIEDADES: frozenset[str] = frozenset({"CL44", "CLYD"})
    _CLP_USD_TEXT_TOKEN = "USD"
    _CLP_USD_ACREEDORES_COM: frozenset[str] = frozenset(
        {
            "2000326095",
            "2000123229",
            "2000168164",
            "2000113042",
            "2000139889",
            "2000706717",
            "2000728821",
            "2000680638",
            "2000148788",
            "2000736433",
            "2000129154",
            "2000253935",
        }
    )
    _CLP_USD_ACREEDORES_NO_COM: frozenset[str] = frozenset(
        {
            "2000118098",
            "2000649969",
            "2000649966",
            "2000649968",
            "2000778769",
            "2000649967",
            "2000000001",
            "2000145676",
        }
    )
    # BUSINESS-18B: Acreedor → concepto(s) exactos. Cargado desde
    # data/resources/CLP_USD_ACREEDOR_CONCEPTO.xlsx (múltiples filas =
    # varios conceptos exactos permitidos para el mismo acreedor).
    _clp_usd_acreedor_concepto_cache: dict[str, frozenset[str]] | None = None

    def __init__(self) -> None:

        self.logger = logger

        self.loader = ExcelLoader()

        self.processor = FBL1NProcessor()

        self.sociedades = SociedadesService()
        self.monedas = MonedaService()
        self.conceptos = ConceptosService()

        self.matrix = MatrizService(
            sociedades=self.sociedades,
            monedas=self.monedas,
            conceptos=self.conceptos,
        )

        self.pivot = PivotService()

        self.exporter = ExcelReport()
        self._last_clp_exclusion_count = 0
        self.last_combine_summary = None

    def load_catalogs(self) -> None:

        self.logger.info("Cargando catálogos...")

        self.sociedades.load()
        self.monedas.load()
        self.conceptos.load()

        self.logger.info("Catálogos cargados correctamente.")

    def process_fbl1n(
        self,
        *,
        historical_path: Path | None = None,
        future_enabled: bool | None = None,
        future_path: Path | None = None,
        compensation_cutoff=None,
    ) -> pd.DataFrame:

        self.logger.info("Leyendo archivo FBL1N...")

        df = self.prepare_fbl1n_dataframe(
            historical_path=historical_path,
            future_enabled=future_enabled,
            future_path=future_path,
            compensation_cutoff=compensation_cutoff,
        )

        df = self.processor.process(df)

        self.logger.info(
            "FBL1N procesado (%d registros).",
            len(df),
        )

        return df

    def prepare_fbl1n_dataframe(
        self,
        *,
        historical_path: Path | None = None,
        future_enabled: bool | None = None,
        future_path: Path | None = None,
        compensation_cutoff=None,
    ) -> pd.DataFrame:
        """
        Cargar el histórico y, si el flag está activo, combinar el futuro.

        No llama a processor.process() ni escribe Excel.
        """

        historical_df = self.loader.load_fbl1n(historical_path)
        self.logger.info(
            "Archivo FBL1N leído (%d registros).",
            len(historical_df),
        )

        enabled = (
            FBL1N_FUTURE_ENABLED if future_enabled is None else bool(future_enabled)
        )
        if not enabled:
            self.last_combine_summary = None
            return historical_df

        return self._apply_future_fbl1n(
            historical_df,
            future_path=future_path,
            compensation_cutoff=compensation_cutoff,
        )

    def _apply_future_fbl1n(
        self,
        historical_df: pd.DataFrame,
        *,
        future_path: Path | None = None,
        compensation_cutoff=None,
    ) -> pd.DataFrame:
        from ..fbl1n_fuentes.module import (
            CombineError,
            CompensationCutoffError,
            FutureFbl1nNoDataError,
            FutureFbl1nUnavailableError,
            STATUS_NODATA,
            STATUS_SUCCEEDED,
            combine_fbl1n_sources,
            parse_compensation_cutoff,
        )

        path = Path(future_path) if future_path is not None else Path(FBL1N_FUTURE_PATH)
        name = path.name or "FBL1N_FUTURO.xlsx"
        if not str(path).strip() or name in {".", ""}:
            raise FutureFbl1nUnavailableError(
                "La ruta del FBL1N futuro no está configurada."
            )
        if not path.exists() or not path.is_file():
            raise FutureFbl1nUnavailableError(
                f"El archivo FBL1N futuro no está disponible: {name}."
            )
        if self.loader.is_locked(path):
            raise FutureFbl1nUnavailableError(
                f"El archivo FBL1N futuro está bloqueado o no es estable: {name}."
            )

        try:
            if compensation_cutoff is None:
                compensation_cutoff = FBL1N_COMPENSATION_CUTOFF
            cutoff = parse_compensation_cutoff(compensation_cutoff)
        except CompensationCutoffError as exc:
            raise FutureFbl1nUnavailableError(str(exc)) from exc

        try:
            future_df = self.loader.load_fbl1n(path)
        except Exception as exc:
            raise FutureFbl1nUnavailableError(
                f"El archivo FBL1N futuro no es legible: {name}."
            ) from exc

        try:
            result = combine_fbl1n_sources(
                historical_df,
                future_df,
                compensation_cutoff=cutoff,
            )
        except CompensationCutoffError as exc:
            raise FutureFbl1nUnavailableError(str(exc)) from exc
        except CombineError as exc:
            raise FutureFbl1nUnavailableError(
                f"El FBL1N futuro tiene estructura incompatible: {exc}"
            ) from exc

        summary = result.summary
        self.last_combine_summary = summary
        self.logger.info(
            "FBL1N combinado: status=%s historico=%d futuro_recibido=%d "
            "futuro_invalido=%d futuro_corte=%d cruces=%d final=%d columnas=%d "
            "cutoff=%s",
            summary.status,
            summary.historical_rows,
            summary.future_rows_received,
            summary.future_invalid_excluded,
            summary.future_cutoff_excluded,
            summary.cross_matches_excluded,
            summary.final_rows,
            summary.columns,
            cutoff.isoformat(),
        )

        if summary.status == STATUS_NODATA:
            raise FutureFbl1nNoDataError(
                "FBL1N futuro sin partidas válidas (NoData); "
                f"historico={summary.historical_rows} "
                f"futuro_recibido={summary.future_rows_received} "
                f"futuro_invalido={summary.future_invalid_excluded} "
                f"cruces={summary.cross_matches_excluded}."
            )
        if summary.status != STATUS_SUCCEEDED:
            raise FutureFbl1nUnavailableError(
                f"Combinación FBL1N con estado no controlado: {summary.status}."
            )
        return result.combined

    def build_matrix(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        self.logger.info("Construyendo matriz...")

        matrix = self.matrix.create_matrix(df)

        self.logger.info(
            "Matriz creada (%d registros).",
            len(matrix),
        )

        return matrix

    def _resolve_texto_column(self, matrix: pd.DataFrame) -> str | None:
        """Resolver la columna de texto SAP disponible en la matriz."""

        for column in ("Texto cab.documento", "texto_cabdocumento"):
            if column in matrix.columns:
                return column
        return None

    def _resolve_sociedad_column(self, matrix: pd.DataFrame) -> str | None:
        for column in ("Sociedad", "sociedad"):
            if column in matrix.columns:
                return column
        return None

    def _resolve_acreedor_column(self, matrix: pd.DataFrame) -> str | None:
        for column in ("Acreedor", "acreedor"):
            if column in matrix.columns:
                return column
        return None

    @staticmethod
    def _normalize_acreedor_id(value: object) -> str:
        """Normalizar ID de acreedor a dígitos (sin decimales Excel)."""

        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, bool):
            return ""
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return str(value).strip()
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return ""
        try:
            number = float(text.replace(",", ""))
            if number.is_integer():
                return str(int(number))
        except ValueError:
            pass
        return text

    def _resolve_concepto_column(self, matrix: pd.DataFrame) -> str | None:
        for column in ("concepto_detectado", "concepto"):
            if column in matrix.columns:
                return column
        return None

    @classmethod
    def load_clp_usd_acreedor_concepto(
        cls,
        path: Path | None = None,
        *,
        reload: bool = False,
    ) -> dict[str, frozenset[str]]:
        """
        BUSINESS-18B: cargar mapeo Acreedor → Concepto(s) exactos.

        Fuente: data/resources/CLP_USD_ACREEDOR_CONCEPTO.xlsx
        Columnas: Acreedor | Concepto_esperado | Segmento

        Un acreedor puede tener varias filas (varios conceptos exactos).
        Para agregar acreedores futuros: solo ampliar el Excel.
        """

        if cls._clp_usd_acreedor_concepto_cache is not None and not reload:
            return cls._clp_usd_acreedor_concepto_cache

        from ...config.config import CLP_USD_ACREEDOR_CONCEPTO_PATH

        catalog_path = path or CLP_USD_ACREEDOR_CONCEPTO_PATH
        mapping: dict[str, set[str]] = {}
        if not catalog_path.exists():
            logger.warning(
                "BUSINESS-18B: no existe %s; mapeo Acreedor→Concepto vacío.",
                catalog_path,
            )
            cls._clp_usd_acreedor_concepto_cache = {}
            return cls._clp_usd_acreedor_concepto_cache

        frame = pd.read_excel(catalog_path, engine="calamine")
        columns = {str(c).strip().lower(): c for c in frame.columns}
        acreedor_col = columns.get("acreedor")
        concepto_col = columns.get("concepto_esperado") or columns.get(
            "concepto esperado"
        )
        if acreedor_col is None or concepto_col is None:
            logger.warning(
                "BUSINESS-18B: catálogo sin columnas Acreedor/Concepto_esperado."
            )
            cls._clp_usd_acreedor_concepto_cache = {}
            return cls._clp_usd_acreedor_concepto_cache

        for _, row in frame.iterrows():
            acreedor = cls._normalize_acreedor_id(row[acreedor_col])
            concepto = (
                ""
                if row[concepto_col] is None
                or (isinstance(row[concepto_col], float) and pd.isna(row[concepto_col]))
                else str(row[concepto_col]).strip()
            )
            if not acreedor or not concepto:
                continue
            mapping.setdefault(acreedor, set()).add(concepto)

        cls._clp_usd_acreedor_concepto_cache = {
            key: frozenset(values) for key, values in mapping.items()
        }
        logger.info(
            "BUSINESS-18B: mapeo Acreedor→Concepto cargado (%d acreedores) desde %s",
            len(cls._clp_usd_acreedor_concepto_cache),
            catalog_path.name,
        )
        return cls._clp_usd_acreedor_concepto_cache

    def clp_usd_segment_mask(
        self,
        matrix: pd.DataFrame,
        acreedores: frozenset[str],
    ) -> pd.Series:
        """
        BUSINESS-18A/18B: máscara de pagos CLP con nomenclatura USD.

        Condiciones (TODAS simultáneas):
            - Sociedad in {CL44, CLYD}
            - Texto cab.documento contiene "USD" (cualquier posición)
            - Acreedor existe en el mapeo Acreedor→Concepto
              y pertenece al listado del segmento
            - concepto_detectado == concepto exacto esperado para ese acreedor
              (sin prefijos COMB/PPA/PEA)
        """

        if matrix.empty:
            return pd.Series(dtype=bool)

        sociedad_col = self._resolve_sociedad_column(matrix)
        texto_col = self._resolve_texto_column(matrix)
        acreedor_col = self._resolve_acreedor_column(matrix)
        concepto_col = self._resolve_concepto_column(matrix)
        if (
            sociedad_col is None
            or texto_col is None
            or acreedor_col is None
            or concepto_col is None
        ):
            self.logger.warning(
                "BUSINESS-18B: faltan columnas Sociedad/Acreedor/Texto/concepto; "
                "segmentación CLP_USD vacía."
            )
            return pd.Series(False, index=matrix.index)

        mapping = self.load_clp_usd_acreedor_concepto()
        sociedad = (
            matrix[sociedad_col].fillna("").astype(str).str.strip().str.upper()
        )
        texto = matrix[texto_col].fillna("").astype(str)
        acreedor = matrix[acreedor_col].map(self._normalize_acreedor_id)
        concepto = matrix[concepto_col].fillna("").astype(str).str.strip()

        allowed_pairs = {
            (acr_id, concept)
            for acr_id, concepts in mapping.items()
            if acr_id in acreedores
            for concept in concepts
        }
        pair_ok = pd.Series(
            [
                (acr_id, concept) in allowed_pairs
                for acr_id, concept in zip(acreedor, concepto, strict=True)
            ],
            index=matrix.index,
        )

        return (
            sociedad.isin(self._CLP_USD_SOCIEDADES)
            & texto.str.contains(self._CLP_USD_TEXT_TOKEN, regex=False)
            & pair_ok
        )

    def apply_clp_pivot_exclusions(
        self,
        matrix: pd.DataFrame,
    ) -> tuple[pd.DataFrame, int]:
        """
        Aplicar exclusiones de negocio al dataset del Pivot CLP.

        BUSINESS-01:
            Si concepto_detectado == PEA_[DEDC]
            y el Texto cab.documento contiene "USD",
            el registro se excluye solo del Pivot CLP.

        No modifica la matriz original ni la clasificación.
        """

        texto_column = self._resolve_texto_column(matrix)

        if (
            "concepto_detectado" not in matrix.columns
            or texto_column is None
        ):
            return matrix.copy(), 0

        concept = matrix["concepto_detectado"].fillna("").astype(str).str.strip()
        text = matrix[texto_column].fillna("").astype(str)

        exclude_mask = (concept == self._CLP_EXCLUDED_CONCEPT) & text.str.contains(
            self._CLP_EXCLUDED_TEXT_TOKEN,
            regex=False,
        )

        excluded_count = int(exclude_mask.sum())
        filtered = matrix.loc[~exclude_mask].copy()

        return filtered, excluded_count

    def _filter_by_matrix_tipo(
        self,
        matrix: pd.DataFrame,
        tipo_filter: str,
    ) -> pd.DataFrame:
        """
        BUSINESS-13/13A/15A: filtrar por la columna `tipo` persistida
        en la MATRIZ.

        Regla funcional (BUSINESS-15A):
            COM              → TD_CLP_COM_2026
            todo lo demás    → TD_CLP_NO_COM
            (NO_COM, vacío, NULL o cualquier otro valor)

        La MATRIZ es la fuente oficial para reportes: este método no
        debe reconsultar concept_classifier.
        """

        wanted = str(tipo_filter).strip().upper()

        if "tipo" not in matrix.columns:
            self.logger.warning(
                "Columna 'tipo' ausente en la MATRIZ; "
                "COM vacía y NO_COM con todos los registros.",
            )
            if wanted == "COM":
                return matrix.iloc[0:0].copy()
            return matrix.copy()

        tipo_series = matrix["tipo"].fillna("").astype(str).str.strip().str.upper()
        if wanted == "COM":
            return matrix.loc[tipo_series == "COM"].copy()
        # BUSINESS-15A: NO_COM = todo lo que no sea COM.
        return matrix.loc[tipo_series != "COM"].copy()

    @classmethod
    def _month_label_from_period(cls, value: object) -> str | None:
        """Mapear periodo (YYYY-MM / All) a etiqueta de dinámica."""

        text = "" if value is None else str(value).strip()
        if not text:
            return None
        if text in {"All", "Total", "all", "total"}:
            return "Total"
        if len(text) >= 7 and text[4] == "-":
            try:
                month = int(text[5:7])
            except ValueError:
                return None
            if 1 <= month <= 12:
                return cls._TD_MONTH_LABELS[month - 1]
        if text in cls._TD_MONTH_LABELS:
            return text
        return None

    def _empty_td_frame(self, *, include_proveedor: bool = False) -> pd.DataFrame:
        columns = [self._TD_CONCEPT_COLUMN]
        if include_proveedor:
            columns.append(self._TD_PROVEEDOR_COLUMN)
        columns.extend([*self._TD_MONTH_LABELS, "Total"])
        return pd.DataFrame(columns=columns)

    def _resolve_proveedor_column(self, frame: pd.DataFrame) -> str | None:
        for column in self._TD_PROVEEDOR_SOURCE:
            if column in frame.columns:
                return column
        return None

    def _format_td_clp_structure(
        self,
        pivot_df: pd.DataFrame,
        *,
        include_proveedor: bool = False,
    ) -> pd.DataFrame:
        """
        Unificar columnas de la dinámica:

            Concepto de Pago [| Proveedor] | Enero…Diciembre | Total
        """

        if pivot_df is None or pivot_df.empty:
            return self._empty_td_frame(include_proveedor=include_proveedor)

        work = pivot_df.copy()
        if self._TD_CONCEPT_COLUMN not in work.columns:
            if "concepto_detectado" in work.columns:
                work = work.rename(
                    columns={"concepto_detectado": self._TD_CONCEPT_COLUMN}
                )
            else:
                first = work.columns[0]
                work = work.rename(columns={first: self._TD_CONCEPT_COLUMN})

        if include_proveedor and self._TD_PROVEEDOR_COLUMN not in work.columns:
            source = self._resolve_proveedor_column(work)
            if source is not None:
                work = work.rename(columns={source: self._TD_PROVEEDOR_COLUMN})
            else:
                work[self._TD_PROVEEDOR_COLUMN] = ""

        skip_columns = {self._TD_CONCEPT_COLUMN}
        if include_proveedor:
            skip_columns.add(self._TD_PROVEEDOR_COLUMN)

        rows: list[dict[str, object]] = []
        for _, item in work.iterrows():
            months = {label: 0.0 for label in self._TD_MONTH_LABELS}
            for column, value in item.items():
                if column in skip_columns:
                    continue
                label = self._month_label_from_period(column)
                if label is None or label == "Total":
                    continue
                try:
                    months[label] += float(value or 0)
                except (TypeError, ValueError):
                    continue
            row: dict[str, object] = {
                self._TD_CONCEPT_COLUMN: item[self._TD_CONCEPT_COLUMN],
            }
            if include_proveedor:
                proveedor = item.get(self._TD_PROVEEDOR_COLUMN, "")
                if proveedor is None or (
                    isinstance(proveedor, float) and pd.isna(proveedor)
                ):
                    proveedor = ""
                row[self._TD_PROVEEDOR_COLUMN] = str(proveedor).strip()
            row.update(months)
            row["Total"] = sum(months.values())
            rows.append(row)

        ordered = [self._TD_CONCEPT_COLUMN]
        if include_proveedor:
            ordered.append(self._TD_PROVEEDOR_COLUMN)
        ordered.extend([*self._TD_MONTH_LABELS, "Total"])
        return pd.DataFrame(rows, columns=ordered)

    def generate_pivot_clp(
        self,
        matrix: pd.DataFrame,
        tipo_filter: str | None = None,
        *,
        standardize: bool | None = None,
        clp_usd: bool | None = None,
        clp_usd_acreedores: frozenset[str] | None = None,
        include_proveedor: bool = False,
    ) -> pd.DataFrame:
        """
        Genera la vista analítica CLP.

        Sprint 1:
            Solo filtra CLP.

        BUSINESS-01:
            Excluye PEA_[DEDC] cuyo texto contiene USD
            únicamente del dataset del Pivot CLP.

        BUSINESS-13:
            tipo_filter=COM|NO_COM selecciona registros según la
            columna `tipo` persistida en la MATRIZ. standardize=True
            unifica columnas Concepto de Pago / Enero…Diciembre / Total.

        BUSINESS-18A/18B:
            clp_usd=True  → solo segmento CLP pagos USD
            clp_usd=False → excluye ese segmento de las TD CLP
            (sociedad + USD + acreedor en mapeo + concepto exacto)
        """

        self.logger.info(
            "Generando vista analítica CLP%s%s...",
            f" (Tipo={tipo_filter})" if tipo_filter else "",
            " [CLP_USD]" if clp_usd else "",
        )

        pivot_source, excluded_count = self.apply_clp_pivot_exclusions(matrix)
        self._last_clp_exclusion_count = excluded_count

        self.logger.info(
            "Registros excluidos del Pivot CLP (PEA_[DEDC] + USD): %d",
            excluded_count,
        )

        if tipo_filter:
            before = len(pivot_source)
            pivot_source = self._filter_by_matrix_tipo(pivot_source, tipo_filter)
            self.logger.info(
                "Filtro Tipo=%s (columna MATRIZ): %d → %d registros",
                tipo_filter,
                before,
                len(pivot_source),
            )

        if clp_usd is not None:
            acreedores = clp_usd_acreedores or frozenset()
            before = len(pivot_source)
            usd_mask = self.clp_usd_segment_mask(pivot_source, acreedores)
            pivot_source = (
                pivot_source.loc[usd_mask].copy()
                if clp_usd
                else pivot_source.loc[~usd_mask].copy()
            )
            self.logger.info(
                "Filtro BUSINESS-18B clp_usd=%s: %d → %d registros",
                clp_usd,
                before,
                len(pivot_source),
            )

        filters = {
            "moneda_del_documento": "CLP",
        }

        # Preservar registros sin concepto (NaN/""): pivot_table(dropna=True)
        # los elimina y rompe la igualdad TD = MATRIZ CLP.
        if "concepto_detectado" in pivot_source.columns:
            pivot_source = pivot_source.copy()
            pivot_source["concepto_detectado"] = (
                pivot_source["concepto_detectado"].fillna("").astype(str)
            )

        pivot_index: str | list[str] = "concepto_detectado"
        if include_proveedor:
            proveedor_col = self._resolve_proveedor_column(pivot_source)
            if proveedor_col is None:
                pivot_source = pivot_source.copy()
                pivot_source[self._TD_PROVEEDOR_COLUMN] = ""
                proveedor_col = self._TD_PROVEEDOR_COLUMN
            else:
                pivot_source = pivot_source.copy()
                pivot_source[proveedor_col] = (
                    pivot_source[proveedor_col].fillna("").astype(str)
                )
            pivot_index = ["concepto_detectado", proveedor_col]

        pivot_df = self.pivot.create_pivot(
            df=pivot_source,
            index=pivot_index,
            columns="mes_compensacion",
            values="importe_en_moneda_doc",
            aggfunc="sum",
            filters=filters,
            margins=True,
            fill_value=0,
        )

        # BUSINESS-11: exponer concepto_detectado como fila visible.
        if not pivot_df.empty:
            pivot_df = pivot_df.reset_index()
            if "concepto_detectado" in pivot_df.columns:
                pivot_df = pivot_df.rename(
                    columns={"concepto_detectado": self._TD_CONCEPT_COLUMN}
                )
            if include_proveedor:
                source = self._resolve_proveedor_column(pivot_df)
                if source is not None and source != self._TD_PROVEEDOR_COLUMN:
                    pivot_df = pivot_df.rename(
                        columns={source: self._TD_PROVEEDOR_COLUMN}
                    )

        should_standardize = (
            True if standardize is None and tipo_filter else bool(standardize)
        )
        if should_standardize:
            pivot_df = self._format_td_clp_structure(
                pivot_df,
                include_proveedor=include_proveedor,
            )

        self.logger.info(
            "Vista analítica generada (%s).",
            pivot_df.shape,
        )

        return pivot_df

    def generate_td_clp_dynamics(
        self,
        matrix: pd.DataFrame,
        *,
        include_proveedor: bool = False,
    ) -> dict[str, pd.DataFrame]:
        """
        BUSINESS-13/15A/18A/18B: dinámicas CLP según `tipo` persistido,
        segmentando pagos CLP con nomenclatura USD a hojas CLP_USD_*.
        """

        return {
            self._TD_SHEET_NO_COM: self.generate_pivot_clp(
                matrix,
                tipo_filter="NO_COM",
                standardize=True,
                clp_usd=False,
                clp_usd_acreedores=self._CLP_USD_ACREEDORES_NO_COM,
                include_proveedor=include_proveedor,
            ),
            self._TD_SHEET_COM: self.generate_pivot_clp(
                matrix,
                tipo_filter="COM",
                standardize=True,
                clp_usd=False,
                clp_usd_acreedores=self._CLP_USD_ACREEDORES_COM,
                include_proveedor=include_proveedor,
            ),
            self._TD_SHEET_CLP_USD_NO_COM: self.generate_pivot_clp(
                matrix,
                tipo_filter="NO_COM",
                standardize=True,
                clp_usd=True,
                clp_usd_acreedores=self._CLP_USD_ACREEDORES_NO_COM,
                include_proveedor=include_proveedor,
            ),
            self._TD_SHEET_CLP_USD_COM: self.generate_pivot_clp(
                matrix,
                tipo_filter="COM",
                standardize=True,
                clp_usd=True,
                clp_usd_acreedores=self._CLP_USD_ACREEDORES_COM,
                include_proveedor=include_proveedor,
            ),
        }

    def build_resumen_conceptos(
        self,
        matrix: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Construir resumen de cobertura por concepto detectado.
        """

        classified = matrix[
            matrix["concepto_detectado"].astype(str).str.strip() != ""
        ]

        if classified.empty:
            resumen = pd.DataFrame(columns=["Concepto", "Cantidad"])
        else:
            resumen = (
                classified.groupby("concepto_detectado", dropna=False)
                .size()
                .reset_index(name="Cantidad")
                .rename(columns={"concepto_detectado": "Concepto"})
                .sort_values(
                    by=["Cantidad", "Concepto"],
                    ascending=[False, True],
                    kind="mergesort",
                )
                .reset_index(drop=True)
            )

        sin_clasificar = int(
            (matrix["concepto_detectado"].astype(str).str.strip() == "").sum()
        )

        resumen = pd.concat(
            [
                resumen,
                pd.DataFrame(
                    [{"Concepto": "SIN CLASIFICAR", "Cantidad": sin_clasificar}]
                ),
            ],
            ignore_index=True,
        )

        return resumen

    def build_no_clasificados(
        self,
        matrix: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Extraer registros sin concepto detectado para revisión de negocio.
        """

        mask = matrix["concepto_detectado"].astype(str).str.strip() == ""
        pending = matrix.loc[mask].copy()

        selected: list[str] = []
        for candidates in self._NO_CLASIFICADOS_COLUMNS:
            for column in candidates:
                if column in pending.columns:
                    selected.append(column)
                    break

        if not selected:
            return pending.iloc[0:0].copy()

        return pending.loc[:, selected].reset_index(drop=True)

    def export_matrix(
        self,
        matrix: pd.DataFrame,
        td_dynamics: dict[str, pd.DataFrame],
        resumen: pd.DataFrame,
        no_clasificados: pd.DataFrame,
    ) -> Path | None:

        self.logger.info(
            "Exportando archivo Excel..."
        )

        additional_sheets = {
            **td_dynamics,
            "RESUMEN_CONCEPTOS": resumen,
            "NO_CLASIFICADOS": no_clasificados,
        }

        output = self.exporter.export(
            dataframe=matrix,
            additional_sheets=additional_sheets,
        )

        self.logger.info(
            "Archivo generado: %s",
            output,
        )
        return output

    def _log_classification_summary(
        self,
        matrix: pd.DataFrame,
        elapsed_seconds: float,
    ) -> None:

        detected = matrix["concepto_detectado"].astype(str).str.strip()
        classified_mask = detected != ""
        classified_count = int(classified_mask.sum())
        unclassified_count = int((~classified_mask).sum())
        used_concepts = sorted(detected[classified_mask].unique().tolist())

        self.logger.info("Conceptos cargados: %d", self.conceptos.count())
        self.logger.info("Conceptos utilizados: %d", len(used_concepts))
        self.logger.info("Registros clasificados: %d", classified_count)
        self.logger.info("Registros sin clasificar: %d", unclassified_count)
        self.logger.info("Tiempo total: %.2f s", elapsed_seconds)

    def run(self) -> None:

        started = time.perf_counter()

        self.logger.info("=" * 70)
        self.logger.info("INICIO INFORME MARGEN")
        self.logger.info("=" * 70)

        self.load_catalogs()

        df = self.process_fbl1n()

        matrix = self.build_matrix(df)

        td_dynamics = self.generate_td_clp_dynamics(matrix)

        resumen = self.build_resumen_conceptos(matrix)
        no_clasificados = self.build_no_clasificados(matrix)

        self.export_matrix(
            matrix,
            td_dynamics,
            resumen,
            no_clasificados,
        )

        elapsed = time.perf_counter() - started
        self._log_classification_summary(matrix, elapsed)

        self.logger.info(
            "Proceso terminado correctamente."
        )

        self.logger.info("=" * 70)
        self.logger.info("FIN INFORME MARGEN")
        self.logger.info("=" * 70)


__all__ = (
    "InformeMargenModule",
)
