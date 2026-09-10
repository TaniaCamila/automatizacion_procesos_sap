# BUSINESS-17 — Business Rules Registry

**Producto:** Automatización FBL1N — Informe Margen (CBO Operations Analytics)
**Tipo:** Documentación funcional definitiva
**Estado:** Vigente (post BUSINESS-16B)
**Última actualización:** 2026-07-23
**Alcance:** Registro documental de reglas implementadas y validadas (BUSINESS-01 … BUSINESS-16B). Este documento no introduce cambios funcionales.

---

## 1. Objetivo del sistema

El proyecto automatiza de punta a punta la generación del **Informe Margen** a partir del extracto SAP **FBL1N** (partidas de acreedores).

**Problema que resuelve**

- Elaboración manual y propensa a error del informe de margen.
- Clasificación inconsistente de conceptos de pago entre Excel, Dashboard y Power BI.
- Dependencia de desarrollo para altas/cambios de conceptos de negocio.

**Resultado esperado**

1. Leer `FBL1N.xlsx`.
2. Clasificar cada registro contra el catálogo administrable (`CONCEPTOS_ADMIN.xlsx`).
3. Construir la **MATRIZ_FBL1N** con la clasificación persistida (fuente única de verdad).
4. Generar vistas analíticas (Pivot CLP, `TD_CLP_NO_COM`, `TD_CLP_COM_2026`, resumen, no clasificados).
5. Producir el modelo Power BI (`PIVOT_MARGEN_*.xlsx`: `PIVOT`, `TD_CLP_NO_COM`, `TD_CLP_COM_2026`, `KPIS`, `METADATA`).
6. Exponer resultados vía API de solo lectura (FastAPI) y frontend React; dejar preparada la publicación a SharePoint / Power BI.

Negocio administra las reglas de clasificación en un único Excel (`CONCEPTOS_ADMIN.xlsx`), sin tocar código.

---

## 2. Arquitectura funcional

```
SAP (FBL1N)
        │
        ▼
Extracción          ExcelLoader → FBL1N.xlsx (data/input/)
        │
        ▼
Normalización       FBL1NProcessor + validación estructural
        │
        ▼
Clasificación       concept_classifier + MatrizService
                    (longest match, BUSINESS-12B/16/16B)
        │
        ▼
MATRIZ              MATRIZ_FBL1N_*.xlsx  ← FUENTE ÚNICA DE VERDAD
                    + TD_CLP_NO_COM / TD_CLP_COM_2026
                    + RESUMEN_CONCEPTOS / NO_CLASIFICADOS
        │
        ▼
Reportes            CONCEPT_AUDIT_*.xlsx
                    PIVOT_MARGEN_*.xlsx (PIVOT, TD, KPIS, METADATA)
        │
        ▼
Power BI            Consume PIVOT_MARGEN (tablas planas, sin reclasificar)
        │
        ▼
SharePoint          Capa de integración (health check; upload real pendiente)
```

### Componentes implementados

| Componente | Responsabilidad |
|---|---|
| `concept_classifier` | Catálogo ADMIN, detección, normalización, grupo / tipo / currency_group |
| `conceptos_sync_service` | Sincronización ADMIN → CONCEPTOS (BUSINESS-12A) |
| `MatrizService` | Persistencia única de la clasificación en la MATRIZ |
| `InformeMargenModule` | Orquestación del informe y dinámicas TD |
| `PivotReportService` | Modelo Power BI leyendo solo la MATRIZ |
| `ConceptAuditService` | Auditoría de conceptos |
| `ProcessOrchestrator` | Flujo end-to-end (matriz → auditoría → pivot → SharePoint health) |
| `FunctionalValidationService` | Centro de Validación Funcional (7 checks) |
| `OutputArtifactService` | Lectura del último artefacto sin recalcular |
| FastAPI + Frontend | Consumo operacional de solo lectura |

---

## 3. Principio de fuente única de verdad

**La MATRIZ_FBL1N es la única fuente de verdad del sistema.**

| Principio | Implicación |
|---|---|
| Clasificación única | Toda clasificación ocurre **únicamente** durante la generación de la MATRIZ (`MatrizService.create_matrix`). |
| Reportes sin reclasificar | Ningún reporte vuelve a clasificar conceptos ni consulta `concept_classifier` / catálogos. |
| Consumo exclusivo | Pivot, Dashboard, APIs, Power BI y SharePoint consumen **exclusivamente** columnas/artefactos derivados de la MATRIZ. |

### Columnas del modelo persistido (BUSINESS-13A)

| Columna | Contenido |
|---|---|
| `concepto_detectado` | Concepto oficial detectado (normalizado; p. ej. `EDP_[`) |
| `concepto` | Concepto estándar del clasificador de negocio |
| `grupo` | Grupo según `CONCEPTOS_ADMIN.xlsx` |
| `currency_group` | `USD` / `NO_USD` |
| `tipo` | `COM` / `NO_COM` |

```
CONCEPTOS_ADMIN.xlsx
        │  (única lectura de reglas)
        ▼
   Clasificación  ──►  MATRIZ_FBL1N  ──►  Reportes / API / Power BI / SharePoint
                         (persistido)         (solo lectura)
```

---

## 4. Flujo completo de procesamiento

Flujo end-to-end (`ProcessOrchestrator`, BUSINESS-08):

```
0. Sincronizar catálogo     CONCEPTOS_ADMIN.xlsx → CONCEPTOS.xlsx   (BUSINESS-12A)
   Cargar ADMIN en memoria  (única lectura de reglas de clasificación)
        │
1. create_matrix            InformeMargenModule.run()
   ├─ Catálogos (sociedades, monedas, conceptos)
   ├─ Extracción y procesamiento de FBL1N.xlsx
   ├─ Construcción MATRIZ (clasificación única por registro)
   ├─ Dinámicas TD_CLP_NO_COM / TD_CLP_COM_2026 (tipo persistido)
   ├─ RESUMEN_CONCEPTOS / NO_CLASIFICADOS
   └─ Export MATRIZ_FBL1N_YYYYMMDD_HHMMSS.xlsx
        │
2. generate_concept_audit   CONCEPT_AUDIT_YYYYMMDD_HHMMSS.xlsx
        │
3. generate_pivot           PIVOT_MARGEN_YYYYMMDD_HHMMSS.xlsx
   └─ Lee SOLO la MATRIZ → PIVOT + TD + KPIS + METADATA
        │
4. sharepoint_health_check  Verificación de configuración (sin upload real)
        │
        ▼
Validación funcional (BUSINESS-14) → 7 checks sobre artefactos
        │
        ▼
Consumo: FastAPI / Frontend / Power BI (sin recálculo)
```

| Etapa | Entrada | Salida | Responsable |
|---|---|---|---|
| 0. Sincronización | `CONCEPTOS_ADMIN.xlsx` | `CONCEPTOS.xlsx` | `conceptos_sync_service` |
| 1. Matriz | `FBL1N.xlsx` + catálogos | `MATRIZ_FBL1N_*.xlsx` | `InformeMargenModule` / `MatrizService` |
| 2. Auditoría | MATRIZ | `CONCEPT_AUDIT_*.xlsx` | `ConceptAuditService` |
| 3. Power BI | MATRIZ | `PIVOT_MARGEN_*.xlsx` | `PivotReportService` |
| 4. SharePoint | Configuración | Health check | `SharePointService` |
| Validación | Artefactos | Reporte 7/7 | `FunctionalValidationService` |

---

## 5. Catálogo de conceptos

### CONCEPTOS_ADMIN.xlsx — fuente administrable

Ubicación: `data/resources/CONCEPTOS_ADMIN.xlsx`

Único punto de administración de negocio. No requiere cambios de código para altas, bajas o ajustes de patrones.

| Columna | Descripción |
|---|---|
| `Concepto encontrado` | Patrón a buscar en el texto SAP (longest match) |
| `Concepto estándar` | Nombre canónico persistido en la MATRIZ |
| `Grupo` | Agrupación de negocio |
| `Tipo` | `COM` o `NO_COM` |
| `Activo` | Solo filas activas participan |

Ejemplo vigente (BUSINESS-16B):

| Concepto encontrado | Concepto estándar | Grupo | Tipo | Activo |
|---|---|---|---|---|
| `EDP_[` | `EDP_[` | `EDP` | `NO_COM` | `SI` |

### CONCEPTOS.xlsx — catálogo derivado

Ubicación: `data/resources/CONCEPTOS.xlsx`

Artefacto **derivado**. Se sincroniza automáticamente desde el ADMIN al inicio del proceso (BUSINESS-12A).

```
CONCEPTOS_ADMIN.xlsx  ──(sync unidireccional)──►  CONCEPTOS.xlsx
        ▲                                              │
   Solo negocio edita                    Pipeline / MatrizService
```

- Dirección única: ADMIN → CONCEPTOS. Nunca al revés.
- Altas y actualizaciones en cada ejecución del orquestador.
- Registros legacy ausentes en ADMIN se preservan (no se borran).
- Residuales legacy (p. ej. clave `EDP_`) se normalizan a `EDP_[` en persistencia (BUSINESS-16B).

---

## 6. Reglas funcionales vigentes

| # | Regla | Definición | Dónde vive |
|---|---|---|---|
| R-01 | Exclusión Pivot CLP | Si `concepto_detectado == PEA_[DEDC]` y el texto contiene `USD`, se excluye **solo** del Pivot CLP. La MATRIZ no se altera. | `InformeMargenModule.apply_clp_pivot_exclusions` |
| R-02 | Detección longest-match | Ante varias coincidencias gana el patrón más largo; empates alfabéticos. | `concept_classifier.search`, `MatrizService._detect_concept` |
| R-03 | Detección restringida EDP | El patrón legacy `EDP_` solo coincide si el texto contiene `EDP_[`. Con el catálogo oficial `EDP_[`, el propio patrón exige `[`. | `concept_classifier.pattern_matches` (BUSINESS-16) |
| R-04 | Concepto oficial EDP | El concepto persistido y visible es exactamente `EDP_[`. No debe existir `EDP_` en MATRIZ ni reportes. | Catálogo ADMIN + `to_standard` (BUSINESS-16B) |
| R-05 | Normalización a Concepto estándar | Artefactos solo contienen Conceptos estándar; variantes alias se resuelven vía ADMIN. | `concept_classifier.to_standard` (BUSINESS-12B) |
| R-06 | Clasificación de moneda | `currency_group = USD` si moneda = USD; resto → `NO_USD`. | `concept_classifier.currency_group` |
| R-07 | Tipo COM / NO_COM | `Tipo` del ADMIN normalizado a `COM` / `NO_COM`. | `concept_classifier._normalize_tipo` |
| R-08 | Segmentación de dinámicas | `tipo == COM` → `TD_CLP_COM_2026`; **todo lo demás** → `TD_CLP_NO_COM`. Suma de ambas = total CLP de la MATRIZ (tras R-01). | `InformeMargenModule._filter_by_matrix_tipo` (BUSINESS-15A) |
| R-09 | Estructura de dinámicas | `Concepto de Pago` \| `Enero` … `Diciembre` \| `Total`. `Concepto de Pago` = `concepto_detectado` normalizado. | Módulo margen / `PivotReportService` |
| R-10 | Filtro CLP | Dinámicas TD y Pivot CLP: solo `moneda_del_documento == CLP`. | `PivotService`, `PivotReportService` |
| R-11 | Reportes sin reclasificar | Reportes leen solo columnas persistidas de la MATRIZ. | BUSINESS-13A |
| R-12 | Sincronización de catálogo | ADMIN → CONCEPTOS antes del pipeline. | `conceptos_sync_service` (BUSINESS-12A) |
| R-13 | Conceptos activos | Solo filas con `Activo` afirmativo y encontrado/estándar no vacíos. | `concept_classifier.load` |
| R-14 | Estado de clasificación | Detectado → `Identificado`; sin match → `No identificado` (`NO_CLASIFICADOS`). | `MatrizService._enrich_concepts` |
| R-15 | Modelo Power BI | `PIVOT_MARGEN`: `PIVOT`, `TD_CLP_NO_COM`, `TD_CLP_COM_2026`, `KPIS`, `METADATA` (año objetivo 2026). | `PivotReportService` |
| R-16 | Lectura sin recálculo | API / Dashboard / validación leen el último artefacto. | `OutputArtifactService` |
| R-17 | Validación previa | 7 checks del Centro de Validación antes de publicar. | `FunctionalValidationService` (BUSINESS-14) |

---

## 7. Historial BUSINESS

| Hito | Objetivo | Resultado |
|---|---|---|
| BUSINESS-01 | Excluir `PEA_[DEDC]` + texto con `USD` del Pivot CLP | Exclusión solo en Pivot CLP; MATRIZ intacta |
| BUSINESS-02 | Clasificador de conceptos (grupo / concepto / currency_group) | `concept_classifier` reutilizable |
| BUSINESS-03 | Integrar clasificador al pipeline | Columnas de negocio persistidas en la MATRIZ |
| BUSINESS-04 | Auditoría de conceptos | `CONCEPT_AUDIT_*.xlsx` |
| BUSINESS-05 | Tabla dinámica Excel automática | `PIVOT_MARGEN_*.xlsx` |
| BUSINESS-06 | Optimizar generación del Pivot | Streaming calamine, métricas tiempo/memoria |
| BUSINESS-07 | Infraestructura SharePoint | Health check; sin conexiones reales |
| BUSINESS-08 | Orquestador end-to-end | Matriz → auditoría → pivot → SharePoint health |
| BUSINESS-09 | Modelo Power BI | Hojas `KPIS` y `METADATA` |
| BUSINESS-10 | Ampliar catálogo | Nuevos conceptos vía ADMIN sin código |
| BUSINESS-11 / 11A | Concepto de Pago en la dinámica | `concepto_detectado` como fila visible |
| BUSINESS-12A | Sync ADMIN → CONCEPTOS | Negocio administra solo el ADMIN |
| BUSINESS-12B | Normalización a Concepto estándar | Sin variantes alias en artefactos |
| BUSINESS-13 | Dinámicas COM / NO_COM | `TD_CLP_NO_COM` y `TD_CLP_COM_2026` |
| BUSINESS-13A | Modelo de datos definitivo | MATRIZ = fuente oficial; reportes no reclasifican |
| BUSINESS-14 | Centro de Validación Funcional | 7 checks automáticos |
| BUSINESS-15 | Dinámicas en PIVOT_MARGEN | `PIVOT` + TD + `KPIS` + `METADATA` |
| BUSINESS-15A | Corrección TD_CLP_NO_COM | NO_COM = todo lo que no sea COM; suma = MATRIZ |
| BUSINESS-16 | Detección restringida EDP | Solo textos con patrón `EDP_[` |
| BUSINESS-16B | Concepto oficial `EDP_[` | Catálogo + persistencia + reportes muestran `EDP_[`; no existe `EDP_` |

---

## 8. Cambios aprobados por negocio

Tabla cronológica. No deben alterarse sin nueva aprobación formal.

| BUSINESS | Cambio | Estado |
|----------|---------|--------|
| BUSINESS-01 | Excluir `PEA_[DEDC]` + `USD` únicamente del Pivot CLP | Aprobado |
| BUSINESS-02 | Clasificación con grupo, concepto y `currency_group` | Aprobado |
| BUSINESS-03 | Persistir clasificación en la MATRIZ | Aprobado |
| BUSINESS-04 | Reporte de auditoría de conceptos | Aprobado |
| BUSINESS-05 | Generación automática de tabla dinámica Excel | Aprobado |
| BUSINESS-06 | Optimización del Pivot | Aprobado |
| BUSINESS-07 | Infraestructura SharePoint (health check) | Aprobado |
| BUSINESS-08 | Orquestador del proceso completo | Aprobado |
| BUSINESS-09 | Modelo Power BI (`KPIS`, `METADATA`) | Aprobado |
| BUSINESS-10 | Ampliación del catálogo administrable | Aprobado |
| BUSINESS-11 / 11A | Exponer `Concepto de Pago` en la dinámica | Aprobado |
| BUSINESS-12A | Sincronización ADMIN → CONCEPTOS | Aprobado |
| BUSINESS-12B | Normalización a Concepto estándar | Aprobado |
| BUSINESS-13 | Dinámicas `TD_CLP_NO_COM` / `TD_CLP_COM_2026` | Aprobado |
| BUSINESS-13A | MATRIZ como fuente oficial | Aprobado |
| BUSINESS-14 | Centro de Validación Funcional | Aprobado |
| BUSINESS-15 | Dinámicas Power BI en `PIVOT_MARGEN` | Aprobado |
| BUSINESS-15A | `TD_CLP_NO_COM` contiene todo lo que no sea COM | Aprobado |
| BUSINESS-16 | EDP solo se detecta con el patrón `EDP_[` | Aprobado |
| BUSINESS-16B | Concepto oficial persistido y visible: `EDP_[` (reemplaza `EDP_`) | Aprobado |

---

## 9. Decisiones de diseño

### Por qué la MATRIZ es la única fuente de verdad

La clasificación es costosa y sensitiva a reglas de negocio. Materializarla una vez en `MATRIZ_FBL1N` garantiza que Pivot, Dashboard, Power BI y SharePoint muestren el mismo resultado auditable por corrida (archivo con timestamp).

### Por qué los reportes no contienen reglas

Si un Excel de salida o un mapper de API reclasifica, aparecen divergencias entre canales. Las reglas viven en el clasificador y en la construcción de la MATRIZ; los reportes solo filtran y agregan columnas ya persistidas.

### Por qué el catálogo es administrable

Negocio cambia conceptos sin despliegues. `CONCEPTOS_ADMIN.xlsx` es la fuente de reglas; `CONCEPTOS.xlsx` se sincroniza automáticamente.

### Por qué la clasificación ocurre una sola vez

Repetir detección en cada reporte multiplica tiempo, memoria y riesgo de inconsistencia. Un solo recorrido en `MatrizService` persiste `concepto_detectado`, `concepto`, `grupo`, `currency_group` y `tipo`.

### Beneficios

| Beneficio | Efecto |
|---|---|
| Consistencia | Mismo concepto / grupo / tipo en todos los canales |
| Rendimiento | Sin reclasificar decenas de miles de filas por reporte |
| Trazabilidad | Cada MATRIZ con timestamp es auditable |
| Mantenibilidad | Reglas centralizadas; reportes sin lógica de negocio |

---

## 10. Lecciones de arquitectura

1. **Separación clasificación / persistencia / reportes**
   Clasificador detecta; MATRIZ persiste; reportes solo leen.

2. **Datos como reglas**
   Patrones y tipos viven en `CONCEPTOS_ADMIN.xlsx`, no hardcodeados en salidas Excel.

3. **Contratos estables de salida**
   Estructura de dinámicas (`Concepto de Pago` \| meses \| `Total`) y hojas Power BI se preservan entre releases.

4. **Validación como puerta de release**
   BUSINESS-14 (7/7 OK) es condición de aceptación, no un chequeo opcional.

5. **Integraciones laterales**
   SharePoint / Power BI / Outlook no invaden el pipeline: consumen artefactos ya generados (`docs/INTEGRATION_ARCHITECTURE.md`).

6. **Normalización explícita del nombre oficial**
   BUSINESS-16B alineó catálogo, persistencia y reportes: el concepto visible es `EDP_[`, no un alias interno.

---

## 11. Restricciones para futuros desarrollos

Obligatorias para cualquier BUSINESS futuro:

1. **Nunca reclasificar datos en reportes.** Prohibido invocar `concept_classifier` o leer catálogos desde Excel de salida, API, Dashboard o Power BI.
2. **Toda nueva regla debe implementarse en la MATRIZ.** Detección, tipificación y normalización se resuelven al construir la MATRIZ y se persisten como columnas.
3. **Toda nueva regla debe documentarse antes de desarrollarse.** Registrar BUSINESS-XX en este documento (definición, responsable, validación) antes de codificar.
4. **Mantener sincronizados `CONCEPTOS_ADMIN.xlsx` y `CONCEPTOS.xlsx`.** Negocio edita solo el ADMIN; el sync (BUSINESS-12A) debe ejecutarse al inicio del proceso.
5. **Mantener compatibilidad con Power BI.** Conservar hojas `PIVOT`, `TD_CLP_NO_COM`, `TD_CLP_COM_2026`, `KPIS`, `METADATA` y la estructura de dinámicas.

Complementarias:

- No alterar BUSINESS-01 … BUSINESS-16B sin aprobación de negocio y actualización de este registro.
- APIs y frontend siguen siendo de solo lectura sobre el último artefacto.
- Todo release debe pasar el Centro de Validación Funcional (7/7 OK).

---

## 12. Estado actual del proyecto

| BUSINESS | Descripción | Estado |
|---|---|---|
| BUSINESS-01 | Exclusión Pivot CLP (`PEA_[DEDC]` + USD) | Implementado |
| BUSINESS-02 | Clasificador de conceptos | Implementado |
| BUSINESS-03 | Integración al pipeline / MATRIZ | Implementado |
| BUSINESS-04 | Auditoría de conceptos | Implementado |
| BUSINESS-05 | Tabla dinámica Excel | Implementado |
| BUSINESS-06 | Optimización Pivot | Implementado |
| BUSINESS-07 | Infraestructura SharePoint | Implementado (health check) |
| BUSINESS-08 | Orquestador end-to-end | Implementado |
| BUSINESS-09 | Modelo Power BI (KPIS / METADATA) | Implementado |
| BUSINESS-10 | Ampliación de catálogo | Implementado |
| BUSINESS-11 / 11A | Concepto de Pago en dinámica | Implementado |
| BUSINESS-12A | Sync ADMIN → CONCEPTOS | Implementado |
| BUSINESS-12B | Normalización Concepto estándar | Implementado |
| BUSINESS-13 | Dinámicas COM / NO_COM | Implementado |
| BUSINESS-13A | MATRIZ fuente oficial | Implementado |
| BUSINESS-14 | Centro de Validación Funcional | Implementado |
| BUSINESS-15 | Dinámicas en PIVOT_MARGEN | Implementado |
| BUSINESS-15A | NO_COM = no COM | Implementado |
| BUSINESS-16 | Detección restringida EDP | Implementado |
| BUSINESS-16B | Concepto oficial `EDP_[` | Implementado |
| BUSINESS-17 | Business Rules Registry (este documento) | Documental |

---

*BUSINESS-17 es exclusivamente documental: no modifica código, pruebas ni configuración.*
