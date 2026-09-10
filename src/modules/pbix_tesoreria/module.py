"""
Módulo EF-08 — Preparación del paquete Power BI Tesorería.

Genera la estructura completa del proyecto Power BI (sin .pbix final):
  - tema corporativo
  - recursos gráficos
  - documentación de construcción
  - organización de páginas (EF-07)
  - estructura de medidas DAX (sin implementar fórmulas)
  - checklist de construcción del PBIX

NO modifica MODELO_POWERBI ni MATRIZ_OPERACIONAL_TESORERIA.
NO modifica pipeline ni módulos anteriores.
NO genera .pbix. NO abre Power BI Desktop.
Fuente única: MODELO_POWERBI.xlsx
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODELO = ROOT / "data" / "output" / "MODELO_POWERBI.xlsx"
DEFAULT_PACKAGE = ROOT / "data" / "output" / "PBIX_TESORERIA_PACKAGE"
THEME_SRC = ROOT / "assets" / "branding" / "theme_tesoreria.json"
LOGO_SRC = ROOT / "assets" / "branding" / "logo_corporativo.svg"
SPEC_EF07 = ROOT / "docs" / "EF07_DASHBOARD_POWERBI_SPEC.md"
DOC_EF08 = ROOT / "docs" / "EF08_PBIX_CONSTRUCTION.md"

DASHBOARD_NAME = "Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)"

# Catálogo de medidas (estructura). Sin fórmulas DAX en esta fase.
MEASURE_CATALOG: tuple[dict[str, str], ...] = (
    {"nombre": "Procesos SAP", "descripcion": "Conteo de filas FACT_PAGOS", "estado": "PENDIENTE_DAX"},
    {"nombre": "Monto Total USD", "descripcion": "Suma MONTO_USD", "estado": "PENDIENTE_DAX"},
    {"nombre": "Monto Promedio USD", "descripcion": "Monto Total / Procesos SAP", "estado": "PENDIENTE_DAX"},
    {"nombre": "Procesos con PA25USD", "descripcion": "Conteo con FECHA_PA25USD no vacío", "estado": "PENDIENTE_DAX"},
    {"nombre": "Procesos sin PA25USD", "descripcion": "Conteo con FECHA_PA25USD vacío", "estado": "PENDIENTE_DAX"},
    {"nombre": "Cobertura PA25USD %", "descripcion": "Con PA25USD / Procesos SAP", "estado": "PENDIENTE_DAX"},
    {"nombre": "Sociedades activas", "descripcion": "Distinct SOCIEDAD", "estado": "PENDIENTE_DAX"},
    {"nombre": "Proveedores activos", "descripcion": "Distinct ACREEDOR", "estado": "PENDIENTE_DAX"},
    {"nombre": "Conceptos activos", "descripcion": "Distinct PROVISION_CONTABLE", "estado": "PENDIENTE_DAX"},
    {"nombre": "Referencias distintas", "descripcion": "Distinct REFERENCIA_DERIVADA", "estado": "PENDIENTE_DAX"},
)

PAGES: tuple[dict[str, str], ...] = (
    {
        "id": "P00",
        "name": "INICIO",
        "role": "portada",
        "slicers": "no",
        "contenido": "Logo · Nombre Dashboard · Fecha actualización · Última carga · Botón Ingresar → P01",
    },
    {
        "id": "P01",
        "name": "Resumen Ejecutivo",
        "role": "analitica",
        "slicers": "globales",
        "contenido": "KPIs · Monto por Sociedad · Variante · Mes · Top proveedores",
    },
    {
        "id": "P02",
        "name": "Análisis por Proveedor",
        "role": "analitica",
        "slicers": "globales+Acreedor",
        "contenido": "Matriz Proveedor→Acreedor→Mes · Top N · Detalle",
    },
    {
        "id": "P03",
        "name": "Análisis por Concepto",
        "role": "analitica",
        "slicers": "globales+Provision",
        "contenido": "Matriz PROVISION_CONTABLE→Mes · Barras · Tabla",
    },
    {
        "id": "P04",
        "name": "Análisis por Sociedad",
        "role": "analitica",
        "slicers": "globales",
        "contenido": "Matriz Sociedad→Mes · Columnas · Tabla",
    },
    {
        "id": "P05",
        "name": "Análisis por Referencia",
        "role": "analitica",
        "slicers": "globales+Referencia",
        "contenido": "Matriz REFERENCIA_DERIVADA · Tabla operacional · Variante",
    },
    {
        "id": "P06",
        "name": "Temporalidad de Pagos",
        "role": "analitica",
        "slicers": "globales+Trimestre",
        "contenido": "Evolución Mes/Año · Matriz temporal · Tabla fechas",
    },
    {
        "id": "P07",
        "name": "Detalle Operacional",
        "role": "analitica",
        "slicers": "globales",
        "contenido": "Tabla completa FACT_PAGOS (11 columnas)",
    },
)

RELATIONSHIPS: tuple[dict[str, str], ...] = (
    {"from": "FACT_PAGOS[SOCIEDAD]", "to": "DIM_SOCIEDAD[SOCIEDAD]", "cardinality": "N:1"},
    {"from": "FACT_PAGOS[ACREEDOR]", "to": "DIM_PROVEEDOR[ACREEDOR]", "cardinality": "N:1"},
    {"from": "FACT_PAGOS[FECHA_PA25USD]", "to": "DIM_FECHA[FECHA]", "cardinality": "N:1"},
    {"from": "FACT_PAGOS[MONEDA]", "to": "DIM_MONEDA[MONEDA]", "cardinality": "N:1"},
)

GLOBAL_SLICERS: tuple[str, ...] = (
    "Sociedad → DIM_SOCIEDAD[SOCIEDAD]",
    "Año → FACT_PAGOS[AÑO_PAGO]",
    "Mes → FACT_PAGOS[MES_PAGO]",
    "Proveedor → DIM_PROVEEDOR[NOMBRE_BENEFICIARIO]",
    "Variante → FACT_PAGOS[VARIANTE]",
)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_portada_metadata(modelo: Path = DEFAULT_MODELO) -> dict[str, str]:
    modelo = Path(modelo)
    ultima_carga = ""
    if modelo.exists():
        ultima_carga = datetime.fromtimestamp(modelo.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    return {
        "dashboard_name": DASHBOARD_NAME,
        "fecha_actualizacion": _now_stamp(),
        "ultima_carga_datos": ultima_carga or "MODELO_POWERBI.xlsx no encontrado",
        "fuente": str(modelo.resolve()) if modelo.exists() else str(modelo),
        "logo_relativo": "recursos/logo_corporativo.svg",
        "boton_cta": "Ingresar al Dashboard",
        "destino_cta": "P01 Resumen Ejecutivo",
    }


def build_blueprint() -> dict:
    return {
        "ef": "EF-08",
        "fase": "PREPARACION_PAQUETE",
        "pbix_generado": False,
        "dax_implementado": False,
        "dashboard": DASHBOARD_NAME,
        "fuente_unica": "MODELO_POWERBI.xlsx",
        "fuente_prohibida": "Archivo Solicitud Pago Extranjero",
        "hojas_importar": [
            "FACT_PAGOS",
            "DIM_SOCIEDAD",
            "DIM_PROVEEDOR",
            "DIM_FECHA",
            "DIM_MONEDA",
        ],
        "pages": list(PAGES),
        "relationships": list(RELATIONSHIPS),
        "global_slicers": list(GLOBAL_SLICERS),
        "nav_order_analitica": [
            "Resumen",
            "Proveedor",
            "Concepto",
            "Sociedad",
            "Referencia",
            "Temporalidad",
            "Detalle",
        ],
        "medidas": list(MEASURE_CATALOG),
        "spec_ef07": "docs/EF07_DASHBOARD_POWERBI_SPEC.md",
    }


def _write_medidas_estructura(path: Path) -> None:
    lines = [
        "# Estructura de medidas DAX — EF-08",
        "",
        "**Estado:** ESTRUCTURA ÚNICAMENTE — fórmulas DAX no implementadas en esta fase.",
        "",
        "Tabla sugerida en Power BI: `_Medidas`",
        "",
        "| # | Medida | Descripción | Estado |",
        "|---|---|---|---|",
    ]
    for i, m in enumerate(MEASURE_CATALOG, start=1):
        lines.append(
            f"| {i} | {m['nombre']} | {m['descripcion']} | {m['estado']} |"
        )
    lines.extend(
        [
            "",
            "## Notas",
            "",
            "- No incluir fórmulas DAX hasta la fase de ensamblaje del PBIX.",
            "- Las definiciones de negocio están en docs/EF07_DASHBOARD_POWERBI_SPEC.md § KPIs.",
            "- Fuente de cálculo: únicamente FACT_PAGOS / DIMs de MODELO_POWERBI.xlsx.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_pages_index(path: Path) -> None:
    lines = [
        "# Organización de páginas — EF-07 / EF-08",
        "",
        "| ID | Página | Rol | Segmentadores | Contenido |",
        "|---|---|---|---|---|",
    ]
    for p in PAGES:
        lines.append(
            f"| {p['id']} | {p['name']} | {p['role']} | {p['slicers']} | {p['contenido']} |"
        )
    lines.extend(
        [
            "",
            "## Navegación",
            "",
            "- P00: botón **Ingresar al Dashboard** → P01",
            "- P01–P07: barra de botones Resumen · Proveedor · Concepto · Sociedad · Referencia · Temporalidad · Detalle",
            "- Segmentadores globales (solo P01–P07): Sociedad · Año · Mes · Proveedor · Variante",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_checklist(path: Path, meta: dict[str, str]) -> None:
    lines = [
        "# Checklist construcción DASHBOARD_TESORERIA.pbix",
        "",
        f"- Paquete generado: {meta['fecha_actualizacion']}",
        f"- Última carga MODELO_POWERBI.xlsx: {meta['ultima_carga_datos']}",
        f"- Dashboard: {meta['dashboard_name']}",
        "",
        "## A. Datos (fuente única)",
        "- [ ] Abrir Power BI Desktop",
        "- [ ] Obtener datos → Excel → `data/output/MODELO_POWERBI.xlsx`",
        "- [ ] Importar: FACT_PAGOS, DIM_SOCIEDAD, DIM_PROVEEDOR, DIM_FECHA, DIM_MONEDA",
        "- [ ] NO importar Archivo Solicitud Pago Extranjero",
        "- [ ] NO modificar el archivo Excel fuente",
        "",
        "## B. Modelo",
        "- [ ] Crear relaciones N:1 según `modelo/relationships.json`",
        "- [ ] Crear tabla vacía `_Medidas`",
        "- [ ] Implementar medidas DAX según `medidas/ESTRUCTURA_MEDIDAS.md` (fase posterior)",
        "",
        "## C. Tema y recursos",
        "- [ ] Ver → Temas → Examinar → `tema/theme_tesoreria.json`",
        "- [ ] Usar `recursos/logo_corporativo.svg` en portada (o logo oficial)",
        "",
        "## D. Páginas (ver `paginas/ORGANIZACION_PAGINAS.md`)",
        "- [ ] P00 INICIO (portada)",
        "- [ ] P01 Resumen Ejecutivo",
        "- [ ] P02 Análisis por Proveedor",
        "- [ ] P03 Análisis por Concepto",
        "- [ ] P04 Análisis por Sociedad",
        "- [ ] P05 Análisis por Referencia",
        "- [ ] P06 Temporalidad de Pagos",
        "- [ ] P07 Detalle Operacional",
        "",
        "## E. Portada P00",
        "- [ ] Logo corporativo",
        f"- [ ] Nombre: {meta['dashboard_name']}",
        f"- [ ] Fecha de actualización: {meta['fecha_actualizacion']}",
        f"- [ ] Última carga de datos: {meta['ultima_carga_datos']}",
        "- [ ] Botón **Ingresar al Dashboard** → P01",
        "",
        "## F. Segmentadores globales (P01–P07, sincronizados)",
        "- [ ] Sociedad",
        "- [ ] Año",
        "- [ ] Mes",
        "- [ ] Proveedor",
        "- [ ] Variante",
        "",
        "## G. Navegación",
        "- [ ] Botón CTA en P00",
        "- [ ] Barra de botones en P01–P07",
        "",
        "## H. Guardar PBIX",
        "- [ ] Guardar como `data/output/DASHBOARD_TESORERIA.pbix`",
        "",
        "## Referencias",
        "- docs/EF07_DASHBOARD_POWERBI_SPEC.md (congelado)",
        "- docs/EF08_PBIX_CONSTRUCTION.md",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    modelo: Path = DEFAULT_MODELO,
    package_dir: Path = DEFAULT_PACKAGE,
) -> Path:
    """Genera la estructura completa del paquete Power BI (sin .pbix)."""
    modelo = Path(modelo)
    package_dir = Path(package_dir)
    if package_dir.exists():
        shutil.rmtree(package_dir)

    dirs = {
        "tema": package_dir / "tema",
        "recursos": package_dir / "recursos",
        "docs": package_dir / "docs",
        "paginas": package_dir / "paginas",
        "medidas": package_dir / "medidas",
        "modelo": package_dir / "modelo",
        "checklist": package_dir / "checklist",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    meta = build_portada_metadata(modelo)
    blueprint = build_blueprint()

    # Tema
    if THEME_SRC.exists():
        shutil.copy2(THEME_SRC, dirs["tema"] / "theme_tesoreria.json")

    # Recursos gráficos
    if LOGO_SRC.exists():
        shutil.copy2(LOGO_SRC, dirs["recursos"] / "logo_corporativo.svg")
    (dirs["recursos"] / "README.md").write_text(
        "\n".join(
            [
                "# Recursos gráficos",
                "",
                "- `logo_corporativo.svg` — placeholder corporativo (reemplazar por logo oficial si aplica)",
                "- Paleta: ver tema `../tema/theme_tesoreria.json`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Documentación
    if SPEC_EF07.exists():
        shutil.copy2(SPEC_EF07, dirs["docs"] / "EF07_DASHBOARD_POWERBI_SPEC.md")
    if DOC_EF08.exists():
        shutil.copy2(DOC_EF08, dirs["docs"] / "EF08_PBIX_CONSTRUCTION.md")
    (dirs["docs"] / "portada_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Páginas
    (dirs["paginas"] / "blueprint.json").write_text(
        json.dumps(blueprint, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_pages_index(dirs["paginas"] / "ORGANIZACION_PAGINAS.md")

    # Medidas — solo estructura
    _write_medidas_estructura(dirs["medidas"] / "ESTRUCTURA_MEDIDAS.md")
    (dirs["medidas"] / "catalogo_medidas.json").write_text(
        json.dumps(list(MEASURE_CATALOG), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Modelo (relaciones + puntero a fuente; no copia el xlsx)
    (dirs["modelo"] / "relationships.json").write_text(
        json.dumps(list(RELATIONSHIPS), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (dirs["modelo"] / "FUENTE.txt").write_text(
        "\n".join(
            [
                "Fuente unica del Dashboard (NO modificar este archivo):",
                str(modelo.resolve()) if modelo.exists() else str(modelo),
                "",
                "Hojas a importar:",
                "  FACT_PAGOS",
                "  DIM_SOCIEDAD",
                "  DIM_PROVEEDOR",
                "  DIM_FECHA",
                "  DIM_MONEDA",
                "",
                "PROHIBIDO: Archivo Solicitud Pago Extranjero como fuente.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Checklist
    _write_checklist(dirs["checklist"] / "CHECKLIST_CONSTRUCCION_PBIX.md", meta)

    # README raíz del paquete
    (package_dir / "README.md").write_text(
        "\n".join(
            [
                "# PBIX Tesorería — Paquete EF-08 (preparación)",
                "",
                f"**Dashboard:** {DASHBOARD_NAME}",
                "",
                "**Estado:** Estructura completa del proyecto Power BI.",
                "**No incluye:** archivo `.pbix` final ni fórmulas DAX implementadas.",
                "",
                "## Contenido",
                "",
                "| Carpeta | Contenido |",
                "|---|---|",
                "| `tema/` | Tema corporativo JSON |",
                "| `recursos/` | Logo y assets gráficos |",
                "| `docs/` | Spec EF-07 + guía EF-08 + metadatos portada |",
                "| `paginas/` | Organización de páginas P00–P07 |",
                "| `medidas/` | Estructura/catálogo de medidas (sin DAX) |",
                "| `modelo/` | Relaciones + puntero a MODELO_POWERBI.xlsx |",
                "| `checklist/` | Checklist de construcción del PBIX |",
                "",
                "## Siguiente paso",
                "",
                "Abrir Power BI Desktop y seguir `checklist/CHECKLIST_CONSTRUCCION_PBIX.md`",
                "para producir `data/output/DASHBOARD_TESORERIA.pbix`.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return package_dir


__all__ = (
    "DASHBOARD_NAME",
    "MEASURE_CATALOG",
    "PAGES",
    "build_blueprint",
    "build_portada_metadata",
    "run",
)
