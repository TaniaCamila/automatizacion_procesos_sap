"""
Módulo EF-05 — PivotTables nativas de Excel para Tesorería.

Crea PivotTables reales (Analizar / Diseño tabla dinámica) desde
MATRIZ_OPERACIONAL_TESORERIA.xlsx mediante Excel COM.

NO modifica pipeline, src existentes, PM anteriores ni matrices previas.
NO genera tablas estaticas, graficos ni macros.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FUENTE = ROOT / "data" / "output" / "MATRIZ_OPERACIONAL_TESORERIA.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "output" / "TABLAS_DINAMICAS_TESORERIA.xlsx"

# Excel constants
XL_DATABASE = 1
XL_ROW_FIELD = 1
XL_COLUMN_FIELD = 2
XL_PAGE_FIELD = 3
XL_DATA_FIELD = 4
XL_SUM = -4157
XL_COUNT = -4112
XL_OPEN_XML_WORKBOOK = 51  # .xlsx


def _as_str(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
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


def _to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _prepare_source_frame(fuente: Path) -> pd.DataFrame:
    df = pd.read_excel(fuente, sheet_name="TESORERIA", dtype=str)
    if df.empty:
        raise ValueError(f"Hoja TESORERIA vacia: {fuente}")

    required = {
        "NOMBRE_BENEFICIARIO",
        "ACREEDOR",
        "MES_PAGO",
        "MONTO_USD",
        "PROVISION_CONTABLE",
        "SOCIEDAD",
        "REFERENCIA_DERIVADA",
        "VARIANTE",
    }
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Columnas ausentes en TESORERIA: {sorted(missing)}")

    work = df.copy()
    # Normalizar campos de fila/filtro como texto (evitar 3.0)
    for col in (
        "SOCIEDAD",
        "ACREEDOR",
        "PROVISION_CONTABLE",
        "DOCUMENTO_CONTABLE",
        "NOMBRE_BENEFICIARIO",
        "REFERENCIA_DERIVADA",
        "REFERENCIA_BASE",
        "VARIANTE",
        "MONEDA",
        "MES_PAGO",
        "AÑO_PAGO",
        "DOCUMENTO_PA25USD",
        "ESTADO_PROCESO",
        "OBSERVACION",
        "FECHA_PA25USD",
    ):
        if col in work.columns:
            work[col] = work[col].map(_as_str)

    work["MONTO_USD"] = work["MONTO_USD"].map(_to_float)
    return work


def _write_datos_sheet(ws, df: pd.DataFrame) -> tuple[int, int]:
    """Escribe encabezados + datos en la hoja. Retorna (n_rows, n_cols) incl. header."""
    headers = list(df.columns)
    for col_idx, name in enumerate(headers, start=1):
        ws.Cells(1, col_idx).Value = name

    values = df.where(pd.notna(df), None).values.tolist()
    n_rows = len(values)
    n_cols = len(headers)
    if n_rows:
        # Escribir bloque de datos
        start = ws.Range(ws.Cells(2, 1), ws.Cells(n_rows + 1, n_cols))
        start.Value = values

    # Forzar MONTO_USD como numero
    try:
        monto_idx = headers.index("MONTO_USD") + 1
        if n_rows:
            ws.Range(
                ws.Cells(2, monto_idx), ws.Cells(n_rows + 1, monto_idx)
            ).NumberFormat = "#,##0.00"
    except ValueError:
        pass

    return n_rows + 1, n_cols


def _set_row_fields(pivot, names: list[str]) -> None:
    """Agrega campos de fila en el orden solicitado (primero = mas externo)."""
    # Insertar en orden inverso en Position=1 para que el primero de `names`
    # quede como campo de fila externo.
    for name in reversed(names):
        field = pivot.PivotFields(name)
        field.Orientation = XL_ROW_FIELD
        field.Position = 1
    # Refuerzo final de posiciones
    for idx, name in enumerate(names, start=1):
        pivot.PivotFields(name).Position = idx


def _add_page_field(pivot, name: str, position: int) -> None:
    field = pivot.PivotFields(name)
    field.Orientation = XL_PAGE_FIELD
    field.Position = position


def _add_sum_field(pivot, source_name: str, caption: str) -> None:
    pivot.AddDataField(pivot.PivotFields(source_name), caption, XL_SUM)


def _add_count_field(pivot, source_name: str, caption: str) -> None:
    # Contar procesos: usar un campo de fila como base de conteo
    pivot.AddDataField(pivot.PivotFields(source_name), caption, XL_COUNT)


def build_pivots_tesoreria(
    fuente: Path = DEFAULT_FUENTE,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Path, int]:
    """
    Genera TABLAS_DINAMICAS_TESORERIA.xlsx con 4 PivotTables nativas.

    Returns:
        (ruta_salida, cantidad_pivots)
    """
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Se requiere pywin32 y Microsoft Excel para crear PivotTables nativas."
        ) from exc

    fuente = Path(fuente)
    output_path = Path(output_path)
    if not fuente.exists():
        raise FileNotFoundError(fuente)

    df = _prepare_source_frame(fuente)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    excel = None
    wb = None
    n_pivots = 0

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False

        wb = excel.Workbooks.Add()
        # Dejar una hoja para datos
        while wb.Worksheets.Count > 1:
            wb.Worksheets(wb.Worksheets.Count).Delete()

        ws_datos = wb.Worksheets(1)
        ws_datos.Name = "DATOS"
        n_rows, n_cols = _write_datos_sheet(ws_datos, df)

        # Tabla Excel (ListObject) para fuente estable del PivotCache
        data_range = ws_datos.Range(
            ws_datos.Cells(1, 1), ws_datos.Cells(n_rows, n_cols)
        )
        list_obj = ws_datos.ListObjects.Add(1, data_range, None, 1)  # xlSrcRange, xlYes
        list_obj.Name = "TablaTesoreria"

        source = f"{ws_datos.Name}!R1C1:R{n_rows}C{n_cols}"
        cache = wb.PivotCaches().Create(SourceType=XL_DATABASE, SourceData=source)

        def _new_sheet(name: str):
            ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
            ws.Name = name
            return ws

        # --- TD_CONCEPTO_PROVEEDOR ---
        ws1 = _new_sheet("TD_CONCEPTO_PROVEEDOR")
        pt1 = cache.CreatePivotTable(
            TableDestination=ws1.Range("A3"),
            TableName="PT_CONCEPTO_PROVEEDOR",
        )
        _set_row_fields(pt1, ["NOMBRE_BENEFICIARIO", "ACREEDOR", "MES_PAGO"])
        _add_sum_field(pt1, "MONTO_USD", "Suma de MONTO_USD")
        n_pivots += 1

        # --- TD_PROVISION ---
        ws2 = _new_sheet("TD_PROVISION")
        pt2 = cache.CreatePivotTable(
            TableDestination=ws2.Range("A3"),
            TableName="PT_PROVISION",
        )
        _set_row_fields(pt2, ["PROVISION_CONTABLE", "MES_PAGO"])
        _add_sum_field(pt2, "MONTO_USD", "Suma de MONTO_USD")
        n_pivots += 1

        # --- TD_SOCIEDAD ---
        ws3 = _new_sheet("TD_SOCIEDAD")
        pt3 = cache.CreatePivotTable(
            TableDestination=ws3.Range("A3"),
            TableName="PT_SOCIEDAD",
        )
        _set_row_fields(pt3, ["SOCIEDAD", "MES_PAGO"])
        _add_sum_field(pt3, "MONTO_USD", "Suma de MONTO_USD")
        _add_count_field(pt3, "REFERENCIA_BASE", "Conteo de procesos")
        n_pivots += 1

        # --- TD_REFERENCIAS ---
        ws4 = _new_sheet("TD_REFERENCIAS")
        pt4 = cache.CreatePivotTable(
            TableDestination=ws4.Range("A3"),
            TableName="PT_REFERENCIAS",
        )
        _add_page_field(pt4, "SOCIEDAD", 1)
        _add_page_field(pt4, "VARIANTE", 2)
        _set_row_fields(pt4, ["REFERENCIA_DERIVADA"])
        _add_sum_field(pt4, "MONTO_USD", "Suma de MONTO_USD")
        n_pivots += 1

        # Mover DATOS al final
        ws_datos.Move(After=wb.Worksheets(wb.Worksheets.Count))

        wb.SaveAs(str(output_path.resolve()), FileFormat=XL_OPEN_XML_WORKBOOK)
        wb.Close(SaveChanges=False)
        wb = None
    finally:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass

    if not output_path.exists():
        raise RuntimeError(f"No se genero el archivo: {output_path}")
    if n_pivots != 4:
        raise RuntimeError(f"Se esperaban 4 PivotTables, se crearon {n_pivots}")

    return output_path, n_pivots


def run(
    fuente: Path = DEFAULT_FUENTE,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Path, int]:
    return build_pivots_tesoreria(fuente=fuente, output_path=output_path)
