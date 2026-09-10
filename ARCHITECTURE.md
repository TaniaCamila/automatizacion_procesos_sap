# Arquitectura — Automatización FBL1N

**Proyecto:** Operations Analytics — Automatización de Procesos SAP
**Producto UI:** Operations Analytics — Automatización de Procesos SAP
**Versión:** 1.0.0
**Autor:** Tania Herrera
**Última actualización:** Septiembre 2026
**Documentos relacionados:** [business_matrix_v1.md](docs/business_matrix_v1.md) · [DESIGN.md](DESIGN.md)

---

## Tabla de contenidos

1. [Objetivo del proyecto](#1-objetivo-del-proyecto)
2. [Contexto de negocio](#2-contexto-de-negocio)
3. [Problema que resuelve](#3-problema-que-resuelve)
4. [Arquitectura actual](#4-arquitectura-actual)
5. [Flujo completo del sistema](#5-flujo-completo-del-sistema)
6. [Responsabilidad de cada carpeta](#6-responsabilidad-de-cada-carpeta)
7. [Responsabilidad de cada módulo](#7-responsabilidad-de-cada-módulo)
8. [Dependencias](#8-dependencias)
9. [Riesgos](#9-riesgos)
10. [Mejoras futuras](#10-mejoras-futuras)
11. [Arquitectura objetivo](#11-arquitectura-objetivo)
12. [Roadmap dividido por Sprint](#12-roadmap-dividido-por-sprint)

---

## 1. Objetivo del proyecto

Automatizar el procesamiento del archivo exportado desde SAP (transacción **FBL1N**) para construir una **matriz empresarial de detalle** — una fila por transacción — enriquecida con catálogos maestros y lista para consumo analítico.

El proyecto busca:

- Eliminar el trabajo manual de tablas dinámicas en Excel.
- Establecer una **única fuente de verdad** para análisis financiero y operativo.
- Preservar la integridad de los datos originales de SAP.
- Parametrizar reglas de negocio mediante archivos Excel, sin modificar código.
- Generar reportes estandarizados de forma reproducible y auditable.
- Sentar las bases para integraciones futuras (Power BI, SAP GUI, Outlook, SharePoint).

---

## 2. Contexto de negocio

### 2.1 Origen de los datos

El área financiera/operativa extrae periódicamente un archivo Excel desde SAP mediante la transacción **FBL1N** (partidas abiertas / documentos de proveedores). Este archivo contiene transacciones con campos como:

- Texto cab.documento
- Importe en moneda doc.
- Moneda del documento
- Fecha compensación
- Sociedad

### 2.2 Catálogos maestros

El enriquecimiento de la matriz depende de tres catálogos mantenidos por el negocio:

| Catálogo | Archivo | Propósito |
|---|---|---|
| Sociedades | `SOCIEDADES.xlsx` | Traducir códigos de sociedad a nombres legibles |
| Monedas | `MONEDA.xlsx` | Validar monedas reconocidas por el negocio |
| Conceptos | `CONCEPTOS.xlsx` | Clasificar transacciones según nomenclatura en el texto del documento |

### 2.3 Consumidores del dato

| Consumidor | Uso |
|---|---|
| Excel | Filtros, tablas dinámicas operativas, revisión de conceptos no identificados |
| Power BI | Modelado analítico y dashboards (**en ajustes**; fuera del flujo diario automatizado) |
| Informe Margen | Primer informe automatizado; vista analítica CLP (Sprint 1) |
| Procesos automáticos | Distribución, alertas y publicación (futuro) |

### 2.4 Principios de negocio

Definidos en detalle en `docs/business_matrix_v1.md`:

- Una fila por transacción; sin subtotales ni totales en la matriz base.
- Conservar nombres y semántica original de columnas SAP.
- No convertir importes entre monedas.
- No eliminar registros por falta de match en catálogos.
- Parametrización exclusiva vía catálogos Excel para sociedades, monedas y conceptos.

---

## 3. Problema que resuelve

### 3.1 Situación anterior (manual)

El proceso previo requería que un analista:

1. Descargara el archivo FBL1N desde SAP.
2. Abriera el Excel y construyera tablas dinámicas manualmente.
3. Cruzara sociedades, monedas y conceptos de forma ad hoc.
4. Aplicara filtros (por moneda, concepto, período) repetidamente cada ciclo.
5. Generara reportes sin trazabilidad ni estandarización.

### 3.2 Consecuencias del proceso manual

| Problema | Impacto |
|---|---|
| Repetitividad | Horas de trabajo en cada cierre o ciclo de reporte |
| Inconsistencia | Distintos criterios según quien ejecute el proceso |
| Errores humanos | Filtros mal aplicados, conceptos mal clasificados |
| Falta de trazabilidad | Sin logs ni historial de transformaciones |
| Escalabilidad limitada | Nuevas sociedades/monedas/conceptos requieren ajustes manuales |
| Duplicación de lógica | Excel y Power BI replican las mismas reglas por separado |

### 3.3 Solución propuesta

Un pipeline automatizado en Python que:

1. Lee el FBL1N y valida su estructura.
2. Normaliza y limpia datos sin alterar el origen SAP.
3. Enriquece cada registro con catálogos parametrizables.
4. Genera la matriz de detalle como fuente única de verdad.
5. Produce vistas analíticas (pivots) según reglas de negocio.
6. Exporta un Excel formateado listo para revisión y análisis.

---

## 4. Arquitectura actual

### 4.1 Estilo arquitectónico

El sistema sigue una **arquitectura en capas** con separación de responsabilidades:

```
┌─────────────────────────────────────────────────────────┐
│                    PUNTO DE ENTRADA                      │
│              main.py  →  app.py (Application)            │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│              MÓDULOS DE NEGOCIO (Informes)               │
│              modules/margen/InformeMargenModule          │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐  ┌─────────▼────────┐  ┌───────▼───────┐
│  PROCESADORES │  │    SERVICIOS     │  │   REPORTES    │
│  fbl1n_proc.  │  │ matriz, pivot,   │  │ excel_report  │
│               │  │ catálogos        │  │               │
└───────┬──────┘  └─────────┬────────┘  └───────────────┘
        │                   │
┌───────▼───────────────────▼───────────────────────────┐
│              INFRAESTRUCTURA COMPARTIDA                  │
│   loaders · validators · config · logger · models       │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Patrones de diseño aplicados

| Patrón | Implementación |
|---|---|
| Orquestador | `Application` delega en módulos de informe |
| Módulo de negocio | `InformeMargenModule` coordina el flujo sin lógica pesada |
| Servicio | `MatrizService`, `PivotService`, servicios de catálogo |
| Template Method | `CatalogService` y `ListCatalogService` como bases abstractas |
| Inyección de dependencias | Servicios reciben loader, validator y logger por constructor |
| Configuración centralizada | `Config` expone rutas y paths de archivos |
| Alias interno | Columnas SAP originales se conservan; se añaden aliases técnicos |

### 4.3 Decisiones técnicas clave

| Decisión | Justificación |
|---|---|
| Pandas como motor de datos | Eficiente para volúmenes de decenas de miles de filas; familiar para analistas |
| Catálogos en Excel | El negocio ya mantiene estos archivos; no requiere base de datos |
| Aliases sin renombrar SAP | Cumple regla de preservación de datos originales |
| openpyxl para exportación | Control fino de estilos, formatos y múltiples hojas |
| Logging dual (archivo + consola) | Trazabilidad operativa y depuración |
| Módulos por informe | Permite agregar nuevos informes sin modificar el orquestador central |

---

## 5. Flujo completo del sistema

### 5.1 Diagrama de secuencia

```
Usuario / Scheduler
        │
        ▼
   [main.py]
        │  Inicializa Config, Logger, Application
        ▼
   [Application.run()]
        │
        ▼
   [InformeMargenModule.run()]
        │
        ├──► load_catalogs()
        │         ├── SociedadesService.load()  ← SOCIEDADES.xlsx
        │         ├── MonedaService.load()      ← MONEDA.xlsx
        │         └── ConceptosService.load()   ← CONCEPTOS.xlsx
        │
        ├──► process_fbl1n()
        │         ├── ExcelLoader.load_fbl1n()  ← FBL1N.xlsx
        │         └── FBL1NProcessor.process()
        │               ├── DataValidator.validate_dataframe()
        │               ├── normalize_columns()   (aliases internos)
        │               ├── clean_strings()
        │               └── normalize_types()     (importes numéricos)
        │
        ├──► build_matrix()
        │         └── MatrizService.create_matrix()
        │               ├── sociedad_nombre      (lookup SOCIEDADES)
        │               ├── moneda_valida          (validación MONEDA)
        │               ├── concepto_detectado     (búsqueda en CONCEPTOS)
        │               ├── concepto_estado        (Identificado / No identificado)
        │               ├── mes_compensacion       (formato AAAA-MM)
        │               └── anio_compensacion      (formato AAAA)
        │
        ├──► generate_pivot_clp()                  [Sprint 1]
        │         └── PivotService.create_pivot()
        │               ├── Filtro: moneda_del_documento = CLP
        │               ├── Index: concepto_detectado
        │               ├── Columns: mes_compensacion
        │               └── Values: importe_en_moneda_doc (sum)
        │
        └──► export_matrix()
                  └── ExcelReport.export()
                        ├── Hoja: MATRIZ_FBL1N      (detalle completo)
                        └── Hoja: CLP_NO_COMBUSTIBLE (vista analítica)
                              → data/output/MATRIZ_FBL1N_{timestamp}.xlsx
```

### 5.2 Transformación de datos por etapa

| Etapa | Entrada | Salida | Transformaciones |
|---|---|---|---|
| Carga FBL1N | Excel SAP | DataFrame crudo | Lectura sin transformación |
| Procesamiento | DataFrame crudo | DataFrame limpio | Validación, aliases, limpieza, tipos |
| Matriz | DataFrame limpio | DataFrame enriquecido | Lookups, detección de conceptos, derivación temporal |
| Pivot | Matriz enriquecida | Tabla cruzada | Filtros + agregación |
| Exportación | Matriz + Pivot | Archivo .xlsx | Formato, estilos, múltiples hojas |

### 5.3 Columnas de la matriz final

| Columna | Origen | Descripción |
|---|---|---|
| Texto cab.documento | FBL1N (SAP) | Texto original del documento |
| Importe en moneda doc. | FBL1N (SAP) | Importe numérico normalizado |
| Moneda del documento | FBL1N (SAP) | Código de moneda original |
| Fecha compensación | FBL1N (SAP) | Fecha de compensación |
| Sociedad | FBL1N (SAP) | Código de sociedad |
| sociedad_nombre | SOCIEDADES | Nombre legible de la sociedad |
| moneda_valida | MONEDA | `True` si la moneda existe en catálogo |
| concepto_detectado | CONCEPTOS | Nomenclatura encontrada en el texto |
| concepto_estado | Derivada | `Identificado` o `No identificado` |
| mes_compensacion | Derivada | Período en formato `AAAA-MM` |
| anio_compensacion | Derivada | Año en formato `AAAA` |

Adicionalmente, el procesador crea **aliases internos** (por ejemplo, `texto_cabdocumento`, `importe_en_moneda_doc`) para uso técnico del pipeline, sin reemplazar los nombres SAP.

---

## 6. Responsabilidad de cada carpeta

```
automatizacion_procesos_sap/
│
├── data/                    Datos del proyecto (entrada, catálogos, salida)
│   ├── input/               Archivo FBL1N exportado desde SAP
│   ├── resources/           Catálogos maestros y plantillas
│   │   └── templates/       Plantillas de reporte (reservado)
│   ├── output/              Excel generados por el pipeline
│   └── master/              Datos maestros consolidados (reservado, sin uso)
│
├── docs/                    Documentación del proyecto
│   └── business_matrix_v1.md   Especificación funcional de la matriz
│
├── logs/                    Registros de ejecución
│   └── historico/           Logs archivados (reservado)
│
├── scripts/                 Scripts de ejecución y automatización (reservado)
│
├── src/                     Código fuente de la aplicación
│   ├── config/              Configuración, logging y settings
│   ├── constants/           Constantes globales (reservado)
│   ├── exceptions/          Excepciones personalizadas (reservado)
│   ├── interfaces/          Contratos e interfaces (reservado)
│   ├── loaders/             Carga de archivos externos
│   ├── models/              Modelos de datos (schemas)
│   ├── modules/             Módulos de informes de negocio
│   │   └── margen/          Informe Margen
│   ├── processors/          Transformación y normalización de datos
│   ├── reports/             Generación de reportes de salida
│   ├── services/            Lógica de negocio y catálogos
│   ├── utils/               Utilidades compartidas (reservado)
│   └── validators/          Validación estructural de datos
│
├── temp/                    Archivos temporales de procesamiento
│
├── tests/                   Pruebas automatizadas
│
├── .venv/                   Entorno virtual Python (no versionado)
│
├── ARCHITECTURE.md          Este documento
├── README.md                Guía rápida del proyecto
├── config.yml               Configuración externa (reservado)
├── requirements.txt         Dependencias Python (pendiente de completar)
└── .env                     Variables de entorno locales (no versionado)
```

### Convenciones de datos

| Carpeta | Escritura | Versionado Git |
|---|---|---|
| `data/input/` | Usuario / SAP | No (`.gitignore`: `*.xlsx`) |
| `data/resources/` | Negocio | No (catálogos locales) |
| `data/output/` | Sistema | No |
| `logs/` | Sistema | No (`.gitignore`: `*.log`) |

---

## 7. Responsabilidad de cada módulo

### 7.1 Punto de entrada

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Entry point | `src/main.py` | Banner, inicialización, manejo global de errores, código de salida |
| Orquestador | `src/app.py` | Instancia y ejecuta módulos de informe disponibles |

### 7.2 Configuración

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Config | `src/config/config.py` | Rutas del proyecto, nombres de archivos, carga de `.env`, creación de directorios |
| Logger | `src/config/logger.py` | Logging centralizado (archivo + consola), niveles configurables |
| Settings | `src/config/settings.py` | Carga de YAML desde `resources/` — **definido pero no integrado al flujo actual** |

### 7.3 Módulos de negocio

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Informe Margen | `src/modules/margen/module.py` | Orquesta el flujo completo del Informe Margen: catálogos → FBL1N → matriz → pivot CLP → exportación |

### 7.4 Procesadores

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| FBL1N Processor | `src/processors/fbl1n_processor.py` | Validación estructural, creación de aliases internos, limpieza de textos, normalización de importes |

### 7.5 Servicios

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Matriz Service | `src/services/matriz_service.py` | Construcción de la matriz enriquecida con lookups y columnas derivadas |
| Pivot Service | `src/services/pivot_service.py` | Generación genérica de tablas cruzadas con filtros parametrizables |
| Sociedades Service | `src/services/sociedades_service.py` | Catálogo código → nombre de sociedad |
| Moneda Service | `src/services/moneda_service.py` | Catálogo de monedas válidas |
| Conceptos Service | `src/services/conceptos_service.py` | Catálogo de nomenclaturas de conceptos |
| Catalog Service | `src/services/catalog_service.py` | Clase base abstracta para catálogos de dos columnas |
| List Catalog Service | `src/services/list_catalog_service.py` | Clase base abstracta para catálogos de una columna |

### 7.6 Infraestructura

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Excel Loader | `src/loaders/excel_loader.py` | Lectura centralizada de archivos Excel (FBL1N y catálogos) |
| Data Validator | `src/validators/validator.py` | Validación estructural de DataFrames (no reglas de negocio) |
| Excel Report | `src/reports/excel_report.py` | Exportación formateada a Excel con múltiples hojas |
| Registro FBL1N | `src/models/schemas.py` | Dataclass de registro — **definido pero no utilizado en el pipeline actual** |

### 7.7 Pruebas

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Pipeline | `tests/test_processing_pipeline.py` | Aliases, enriquecimiento de matriz, conceptos no identificados |
| Exportación | `tests/test_excel_export.py` | Generación básica de workbook Excel |
| Catálogo sociedades | `tests/test_sociedades_catalog.py` | Carga real del catálogo SOCIEDADES (integración) |

### 7.8 Matriz de responsabilidades (quién hace qué)

| Capacidad | Responsable | No hace |
|---|---|---|
| Validación estructural | `DataValidator` | Reglas de negocio, limpieza, cruces |
| Limpieza y normalización | `FBL1NProcessor` | Enriquecimiento con catálogos |
| Enriquecimiento | `MatrizService` | Filtrado, agregación, exportación |
| Catálogos | Servicios de catálogo | Transformación de FBL1N |
| Vistas analíticas | `PivotService` | Reglas de negocio (recibe parámetros) |
| Reglas de informe | Módulo de negocio | Lógica genérica reutilizable |
| Exportación | `ExcelReport` | Transformación de datos |
| Orquestación global | `Application` | Lógica de negocio específica |

---

## 8. Dependencias

### 8.1 Runtime

| Paquete | Versión (venv actual) | Uso en el proyecto |
|---|---|---|
| Python | 3.13 | Lenguaje base |
| pandas | 3.0.3 | Manipulación de DataFrames, pivot tables |
| numpy | 2.5.1 | Dependencia de pandas |
| openpyxl | 3.1.5 | Lectura/escritura Excel con estilos |
| xlsxwriter | 3.2.9 | Instalado; **no utilizado actualmente** en exportación |
| PyYAML | 6.0.3 | Carga de configuración YAML (Settings, sin uso activo) |
| python-dateutil | 2.9.0 | Parsing de fechas |
| et-xmlfile | 2.0.0 | Dependencia de openpyxl |
| tzdata | 2026.3 | Zonas horarias |
| colorlog | 6.10.1 | Instalado; logging usa stdlib |
| colorama | 0.4.6 | Dependencia de colorlog |

### 8.2 Dependencias del sistema

| Requisito | Detalle |
|---|---|
| Sistema operativo | Windows 10+ (entorno actual de desarrollo) |
| Excel | Para revisión de archivos de entrada/salida |
| SAP | Fuente original del archivo FBL1N (exportación manual hoy) |

### 8.3 Dependencias de datos

| Archivo | Ubicación | Obligatorio |
|---|---|---|
| FBL1N.xlsx | `data/input/` | Sí |
| SOCIEDADES.xlsx | `data/resources/` | Sí |
| MONEDA.xlsx | `data/resources/` | Sí |
| CONCEPTOS.xlsx | `data/resources/` | Sí |

### 8.4 Estado de empaquetado

> **Nota:** `requirements.txt` existe pero está vacío. Las versiones documentadas aquí provienen del entorno virtual actual. Se recomienda generar un `requirements.txt` con versiones fijadas como parte del Sprint 0 de estabilización.

---

## 9. Riesgos

### 9.1 Riesgos funcionales

| ID | Riesgo | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|
| R-F01 | Detección de conceptos en orden alfabético, no por aparición en texto | Media | Medio | Definir regla explícita y alinear algoritmo con negocio |
| R-F02 | Sociedad no encontrada devuelve código en lugar de vacío | Media | Bajo | Ajustar `get_name()` según spec §6.3 |
| R-F03 | Hoja `CLP_NO_COMBUSTIBLE` no excluye combustible aún | Alta | Medio | Completar regla en Sprint 1 cuando negocio la defina |
| R-F04 | Inconsistencia `dayfirst` entre processor y matriz en fechas | Media | Medio | Unificar criterio de parsing de fechas |
| R-F05 | Columnas SAP renombradas o ausentes en futuras exportaciones | Media | Alto | Validar columnas obligatorias al inicio del pipeline |

### 9.2 Riesgos técnicos

| ID | Riesgo | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|
| R-T01 | `requirements.txt` vacío impide reproducibilidad | Alta | Alto | Fijar dependencias en Sprint 0 |
| R-T02 | Entorno virtual atado a ruta de otro usuario | Media | Alto | Documentar recreación de `.venv` |
| R-T03 | Código muerto (`Settings`, `RegistroFBL1N`) genera confusión | Media | Bajo | Integrar o eliminar en sprint de limpieza |
| R-T04 | `.apply()` fila a fila en matriz de ~70k registros | Media | Medio | Vectorizar operaciones críticas si el volumen crece |
| R-T05 | Exportación Excel lenta (~2.5 min para 70k filas) | Media | Medio | Evaluar escritura por chunks o alternativa más eficiente |

### 9.3 Riesgos operativos

| ID | Riesgo | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|
| R-O01 | Archivos Excel no versionados en Git | Alta | Medio | Proceso documentado de despliegue de catálogos |
| R-O02 | Exportación FBL1N manual desde SAP | Alta | Medio | Integración SAP GUI en roadmap |
| R-O03 | Sin CI/CD ni tests de integración completos | Alta | Medio | Pipeline de tests en Sprint de calidad |
| R-O04 | Datos sensibles en `.env` y archivos Excel locales | Media | Alto | Mantener `.gitignore`; no commitear credenciales |

### 9.4 Riesgos de negocio

| ID | Riesgo | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|
| R-N01 | Reglas de "No Combustible" no definidas por negocio | Alta | Alto | Workshop de definición antes de cerrar Sprint 1 |
| R-N02 | Catálogo MONEDA con una sola moneda (CLP) | Media | Medio | Ampliar catálogo cuando aparezcan otras monedas |
| R-N03 | Cambio de formato en exportación SAP | Baja | Alto | Validación estructural + tests con archivos reales |

---

## 10. Mejoras futuras

### 10.1 Corto plazo (Sprints 0–2)

- Completar `requirements.txt` con versiones fijadas.
- Validar columnas SAP obligatorias en el validator.
- Unificar lógica duplicada de `normalize_column()`.
- Completar regla "No Combustible" en Informe Margen.
- Alinear comportamiento de sociedad no encontrada con la spec.
- Ampliar cobertura de tests (pivot, detección parcial de conceptos, módulo completo).
- Completar `scripts/run.ps1` para ejecución estandarizada.

### 10.2 Mediano plazo (Sprints 3–5)

- Integrar `Settings` con YAML o eliminar si no se usará.
- Usar o eliminar `RegistroFBL1N` según decisión de modelado.
- Vectorizar operaciones de `MatrizService` para mejor rendimiento.
- Agregar más vistas analíticas (USD, EUR, otras segmentaciones).
- Soporte para plantilla Excel (`plantilla_reporte.xlsx`).
- Logging estructurado y rotación de logs en `logs/historico/`.

### 10.3 Largo plazo

- **SAP GUI / SAP Scripting:** extracción automática del FBL1N.
- **Power BI:** en ajustes (especificación y material de referencia; no automatizado en el flujo diario).
- **Outlook:** envío automático de reportes por correo.
- **OneDrive / SharePoint:** almacenamiento y distribución centralizada.
- **Scheduler:** ejecución programada (Task Scheduler / cron).
- **API REST:** exposición de matriz para otros sistemas.
- **Dashboard web:** visualización interactiva sin depender de Excel.

---

## 11. Arquitectura objetivo

### 11.1 Visión

El sistema evolucionará de un **pipeline batch local** a una **plataforma de automatización financiera** modular, donde la matriz FBL1N es el núcleo de datos compartido por múltiples informes e integraciones.

### 11.2 Diagrama objetivo

```
                    ┌─────────────────────────────────┐
                    │         FUENTES DE DATOS         │
                    │  SAP GUI  ·  Excel manual  · API │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │       CAPA DE INGESTA              │
                    │   Loaders  ·  Validators  ·  ETL   │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │     MATRIZ EMPRESARIAL (CORE)      │
                    │   Detalle transaccional unificado  │
                    │   + Catálogos parametrizables      │
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼─────────┐ ┌────────▼────────┐ ┌──────────▼──────────┐
    │  Informe Margen   │ │  Informe [N]    │ │  Informe [N+1]      │
    │  (pivots, filtros)│ │  (futuro)       │ │  (futuro)           │
    └─────────┬─────────┘ └────────┬────────┘ └──────────┬──────────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │       CAPA DE SALIDA             │
                    │  Excel · Power BI · Email · Cloud│
                    └─────────────────────────────────┘
```

### 11.3 Principios de la arquitectura objetivo

| Principio | Descripción |
|---|---|
| Matriz como core | Toda transformación parte de la matriz de detalle; los informes no duplican lógica |
| Parametrización externa | Reglas de negocio en catálogos/config, no en código |
| Módulos independientes | Cada informe es un módulo autocontenido que consume la matriz |
| Integraciones desacopladas | SAP, Power BI, Outlook son adaptadores, no parte del core |
| Trazabilidad total | Logs, versionado de archivos, historial de ejecuciones |
| Testeable | Unit tests + integration tests + tests con datos reales anonimizados |

### 11.4 Evolución de capas

| Capa | Hoy | Objetivo |
|---|---|---|
| Ingesta | Excel manual | SAP GUI automático + fallback manual |
| Core | Matriz en memoria (Pandas) | Matriz + persistencia opcional (Parquet/CSV) |
| Informes | Informe Margen (CLP) | Múltiples informes modulares |
| Salida | Excel local | Excel + Power BI + Email + Cloud |
| Operación | Ejecución manual | Scheduler + monitoreo + alertas |
| Configuración | `config.py` + Excel | `config.py` + YAML + `.env` + Excel |

---

## 12. Roadmap dividido por Sprint

### Sprint 0 — Estabilización y base documental

**Objetivo:** Consolidar la base existente y dejar el proyecto reproducible y documentado.

| ID | Entregable | Prioridad |
|---|---|---|
| S0-01 | Documento ARCHITECTURE.md | Alta |
| S0-02 | Completar `requirements.txt` con versiones fijadas | Alta |
| S0-03 | Completar README.md con instrucciones de instalación y ejecución | Alta |
| S0-04 | Script `run.ps1` funcional | Media |
| S0-05 | Validación de columnas SAP obligatorias | Media |
| S0-06 | Unificar criterio de parsing de fechas | Media |
| S0-07 | Alinear `sociedad_nombre` vacío cuando no hay match | Media |
| S0-08 | Decidir destino de `Settings`, `RegistroFBL1N` y carpetas vacías | Baja |

**Criterio de aceptación:** Proyecto ejecutable desde cero siguiendo README; tests pasan; documentación completa.

---

### Sprint 1 — Informe Margen: vista analítica CLP

**Objetivo:** Completar la primera vista analítica del Informe Margen.

| ID | Entregable | Prioridad |
|---|---|---|
| S1-01 | Filtro por moneda CLP en pivot | ✅ Implementado |
| S1-02 | Exportación hoja analítica en Excel | ✅ Implementado |
| S1-03 | Definir regla de negocio "No Combustible" con el área usuaria | Alta |
| S1-04 | Implementar exclusión de combustible en pivot | Alta |
| S1-05 | Renombrar hoja Excel según regla final acordada | Media |
| S1-06 | Tests de PivotService y flujo CLP | Media |
| S1-07 | Validar resultados con archivo real (~70k registros) | Alta |

**Criterio de aceptación:** Vista CLP sin combustible coincide con tabla dinámica manual de referencia.

**Dependencia de negocio:** Definición explícita de qué conceptos/textos constituyen "combustible".

---

### Sprint 2 — Calidad y robustez del pipeline

**Objetivo:** Fortalecer validaciones, tests y rendimiento.

| ID | Entregable | Prioridad |
|---|---|---|
| S2-01 | Tests unitarios para detección parcial de conceptos | Alta |
| S2-02 | Tests de integración con datos anonimizados | Alta |
| S2-03 | Vectorizar operaciones críticas de MatrizService | Media |
| S2-04 | Optimizar exportación Excel | Media |
| S2-05 | Consolidar `normalize_column()` en utilidad compartida | Baja |
| S2-06 | Manejo de errores con excepciones personalizadas | Media |
| S2-07 | Rotación y archivado de logs | Baja |

**Criterio de aceptación:** Cobertura de tests > 80% en servicios core; pipeline procesa 70k registros en tiempo aceptable.

---

### Sprint 3 — Segundo informe y parametrización avanzada

**Objetivo:** Demostrar que la arquitectura modular escala a nuevos informes.

| ID | Entregable | Prioridad |
|---|---|---|
| S3-01 | Integrar `Settings` con YAML o eliminar | Media |
| S3-02 | Parametrizar reglas de pivot via configuración | Alta |
| S3-03 | Agregar segundo informe (a definir con negocio) | Alta |
| S3-04 | Soporte plantilla Excel (`plantilla_reporte.xlsx`) | Media |
| S3-05 | Documentar proceso de alta de conceptos/monedas/sociedades | Media |

**Criterio de aceptación:** Nuevo informe se agrega sin modificar servicios existentes.

---

### Sprint 4 — Integración Power BI (en ajustes)

| ID | Entregable | Prioridad |
|---|---|---|
| S4-01 | Especificación y checklist del dashboard (paquete académico de referencia) | Alta |
| S4-02 | Modelo en estrella documentado para Power BI | Alta |
| S4-03 | Construcción del PBIX con datos y assets **autorizados por la organización de despliegue** (fuera de este repo) | Media |

**Criterio de aceptación Capstone:** la documentación describe el alcance; Power BI no se declara como automatización diaria terminada.

---

### Sprint 5 — Automatización de ingesta SAP

**Objetivo:** Eliminar la descarga manual del FBL1N.

| ID | Entregable | Prioridad |
|---|---|---|
| S5-01 | Evaluación técnica SAP GUI Scripting vs alternativas | Alta |
| S5-02 | Módulo de ingesta SAP | Alta |
| S5-03 | Fallback a Excel manual si SAP no disponible | Media |
| S5-04 | Scheduler de ejecución periódica | Media |

**Criterio de aceptación:** Pipeline se ejecuta sin intervención manual desde SAP hasta Excel de salida.

---

### Sprint 6 — Distribución y operación

**Objetivo:** Automatizar entrega y monitoreo del reporte.

| ID | Entregable | Prioridad |
|---|---|---|
| S6-01 | Envío automático por Outlook | Alta |
| S6-02 | Publicación en OneDrive / SharePoint | Alta |
| S6-03 | Alertas por conceptos no identificados | Media |
| S6-04 | Monitoreo de ejecuciones y errores | Media |

**Criterio de aceptación:** Reporte generado, publicado y notificado sin intervención humana.

---

### Resumen visual del roadmap

```
Sprint 0 ─── Estabilización + Documentación
    │
Sprint 1 ─── Informe Margen CLP (No Combustible)
    │
Sprint 2 ─── Calidad, tests y rendimiento
    │
Sprint 3 ─── Segundo informe + parametrización
    │
Sprint 4 ─── Power BI
    │
Sprint 5 ─── SAP GUI automático
    │
Sprint 6 ─── Distribución (Outlook + Cloud)
```

---

## Apéndice A — Glosario

| Término | Definición |
|---|---|
| FBL1N | Transacción SAP de partidas de proveedores |
| Matriz | Tabla de detalle con una fila por transacción, enriquecida con catálogos |
| Catálogo | Archivo Excel maestro (sociedades, monedas, conceptos) |
| Alias interno | Nombre técnico normalizado convive con el nombre SAP original |
| Pivot / Vista analítica | Tabla cruzada agregada derivada de la matriz |
| Informe Margen | Primer módulo de negocio; genera vista CLP |

## Apéndice B — Referencias

| Documento | Ubicación | Contenido |
|---|---|---|
| Business Matrix v1 | `docs/business_matrix_v1.md` | Especificación funcional completa de la matriz |
| README | `README.md` | Guía rápida del proyecto |
| Logs | `logs/app.log` | Historial de ejecuciones |

---

*Este documento describe el estado del sistema a Julio 2026. Debe actualizarse al cierre de cada Sprint.*
