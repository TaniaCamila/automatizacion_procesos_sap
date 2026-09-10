# INT-08 — Arquitectura de integración Power BI + SharePoint

**Producto:** CBO Operations Analytics
**Estado:** Diseño (sin implementación de conexiones reales)
**Alcance:** Documento de arquitectura desacoplada. No modifica pipeline, API, frontend ni módulos existentes.

---

## 1. Arquitectura actual

Hoy el sistema es **local-first** y está organizado en capas independientes:

```
SAP / FBL1N.xlsx (input)
        │
        ▼
Pipeline Python (src/main.py → Informe Margen)
        │
        ├─ Clasificación Excel (CONCEPTOS.xlsx)
        ├─ BUSINESS-02/03 (concept_classifier → grupo / concepto / currency_group)
        ├─ BUSINESS-01 (exclusión Pivot CLP)
        └─ BUSINESS-04 (ConceptAuditService, bajo demanda)
        │
        ▼
Artefactos en data/output/
        ├─ MATRIZ_FBL1N_YYYYMMDD_HHMMSS.xlsx
        └─ CONCEPT_AUDIT_YYYYMMDD_HHMMSS.xlsx
        │
        ├──────────────────────┐
        ▼                      ▼
FastAPI (lectura)         Consumo manual
Route → Mapper → Schema   (Excel / archivos)
        │
        ▼
Frontend React (Page → Hook → Adapter → API)
  Margen · Dashboard · Tesorería · SEN · IMG
```

### Características actuales

| Capa | Rol | Estado |
|------|-----|--------|
| Pipeline | Genera matriz y hojas analíticas | Operativo |
| `OutputArtifactService` | Lee el último artefacto sin recalcular | Operativo |
| FastAPI | Contratos GET de solo lectura | Operativo |
| Frontend | Visualización operacional | Operativo |
| Concept audit | Servicio desacoplado de auditoría | Operativo (no cableado al orquestador) |
| Power BI | — | No integrado |
| SharePoint | — | No integrado |

### Principio vigente

Los endpoints **no** reejecutan FBL1N. Consumen el artefacto más reciente. Esa separación debe preservarse al incorporar Power BI y SharePoint.

---

## 2. Arquitectura objetivo

Se introduce una **capa de integración (Integration Layer)** entre los artefactos generados y los destinos externos, sin acoplar Power BI ni SharePoint al pipeline ni a los mappers existentes.

```
                    ┌─────────────────────────────────────┐
                    │     Orquestador de ejecución         │
                    │  (único flujo end-to-end futuro)     │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   Pipeline FBL1N           Integration Layer         Observabilidad
   (sin cambios de          (nueva, desacoplada)      (logs / estado)
    contrato interno)
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              Artifact Store   Power BI Port   SharePoint Port
              (data/output)    (interface)     (interface)
                    │
                    ▼
                 FastAPI / UI  (sin cambios de contrato)
```

### Principios de diseño

1. **Desacoplamiento:** el pipeline solo produce archivos; no conoce Power BI ni SharePoint.
2. **Puertos e implementaciones:** interfaces estables; adapters reales se agregan después.
3. **Un solo orquestador:** un flujo ejecuta pipeline → auditoría → publicación → refresco.
4. **Idempotencia:** republicar el mismo artefacto no debe corromper datasets.
5. **Sin efectos en contratos API/UI:** la integración es lateral, no invade mappers existentes.

---

## 3. Flujo completo

Flujo objetivo (orquestado):

```
FBL1N (SAP / Excel input)
        ↓
Pipeline Python
        ↓
MATRIZ_FBL1N (+ hojas + CONCEPT_AUDIT)
        ↓
Power BI  (dataset / semantic model refresh)
        ↓
SharePoint  (publicación de archivos y/o enlace a reporte)
```

### Detalle por etapa

| # | Etapa | Entrada | Salida | Responsable futuro |
|---|-------|---------|--------|--------------------|
| 1 | Ingesta FBL1N | Archivo SAP | DataFrame procesado | Pipeline actual |
| 2 | Pipeline | FBL1N + catálogos | `MATRIZ_FBL1N_*.xlsx` | `InformeMargenModule` |
| 3 | Auditoría | Matriz clasificada | `CONCEPT_AUDIT_*.xlsx` | `ConceptAuditService` |
| 4 | Publicación artefactos | Rutas locales | URLs / IDs SharePoint | `SharePointPublisher` |
| 5 | Actualización analítica | Dataset Power BI | Refresh job status | `PowerBIRefresher` |
| 6 | Notificación / estado | Resultados 4–5 | Log + opcional API status | Orquestador |

### Variante de publicación

Power BI puede conectarse a:

- **Opción A (recomendada inicialmente):** Excel en SharePoint/OneDrive como fuente del dataset.
- **Opción B:** Gateway + carpeta/red o Dataflow sobre el mismo archivo.
- **Opción C (posterior):** modelo importado vía API (push / Fabric) — fuera del alcance inmediato.

El diseño de interfaces debe permitir A → B → C sin reescribir el pipeline.

---

## 4. Componentes necesarios

### Ya existentes (reutilizar, no modificar)

- Pipeline / `MatrizService` / clasificador / auditoría
- `OutputArtifactService` (descubrimiento del artefacto vigente)
- FastAPI + Frontend (consumo operacional interno)

### Nuevos (a crear en fases posteriores)

| Componente | Responsabilidad |
|------------|-----------------|
| `IntegrationOrchestrator` | Ejecutar el flujo completo en orden y con control de errores |
| `ArtifactRegistry` | Resolver “último artefacto válido” y metadatos (nombre, hash, mtime) |
| `PowerBIPort` (interface) | Contrato de refresco / estado de dataset |
| `SharePointPort` (interface) | Contrato de upload / replace / obtener URL |
| `PowerBIService` | Adapter Microsoft Fabric / Power BI REST |
| `SharePointService` | Adapter Microsoft Graph / SharePoint REST |
| `IntegrationConfig` | Tenant, site, library, dataset_id, workspace_id (secretos fuera del repo) |
| `IntegrationStatus` | Resultado tipado por etapa (ok / skipped / failed) |

### Ubicación sugerida (futura)

```
src/integration/
  __init__.py
  orchestrator.py
  ports/
    power_bi.py
  ports/
    sharepoint.py
  services/
    power_bi_service.py
    sharepoint_service.py
  config.py
  models.py
```

Ningún archivo de esta carpeta debe importarse desde mappers de Margen/Dashboard/Tesorería/SEN/IMG.

---

## 5. Interfaces futuras

Contratos conceptuales (sin implementación en INT-08):

### `SharePointPort`

```text
upload_file(local_path, remote_folder, overwrite=True) -> PublishedArtifact
  - published_url
  - item_id
  - etag / version

replace_latest(local_path, naming_policy) -> PublishedArtifact
get_item_metadata(item_id) -> ArtifactMetadata
```

### `PowerBIPort`

```text
trigger_refresh(dataset_id) -> RefreshHandle
get_refresh_status(handle) -> RefreshStatus  # Unknown | Running | Succeeded | Failed
wait_until_complete(handle, timeout_s) -> RefreshStatus
```

### `IntegrationOrchestrator`

```text
run(options) -> IntegrationRunResult
  steps:
    1. ensure_pipeline_artifacts (opcional: invocar pipeline o asumir ya generado)
    2. ensure_concept_audit
    3. publish_to_sharepoint(MATRIZ, CONCEPT_AUDIT)
    4. refresh_power_bi
    5. summarize
```

### Políticas de nombres

- Conservar timestamp en archivo histórico.
- Opcional: publicar además un alias estable (`MATRIZ_FBL1N_LATEST.xlsx`) para que Power BI no dependa del nombre con fecha.

---

## 6. Servicios que se deberán implementar

| Servicio | Dependencias | Notas |
|----------|--------------|-------|
| `SharePointService` | Microsoft Graph, app registration, site/drive IDs | Auth client credentials o delegated según política IT |
| `PowerBIService` | Power BI REST / Fabric, capacity, dataset | Requiere permisos `Dataset.ReadWrite.All` (o equivalente) |
| `ArtifactRegistry` | `OutputArtifactService` | Capa fina; no duplicar lectura de Excel |
| `IntegrationOrchestrator` | Puertos + registry + (opcional) pipeline | Punto único de ejecución |
| `SecretProvider` | Key Vault / env / Windows Credential | Nunca hardcodear tokens |
| `IntegrationNotifier` (opcional) | Teams / correo | Aviso de éxito o fallo de refresh |

### Qué no implementar todavía

- Llamadas reales a Graph / Power BI
- Credenciales en el repositorio
- Cambios en rutas FastAPI existentes
- Embed de Power BI en el frontend React (puede ser fase posterior)

---

## 7. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Acoplar refresh al pipeline | Fallos de red rompen la generación local | Orquestador externo; pipeline sigue siendo usable offline |
| Dataset Power BI apunta a path con timestamp | Reportes quedan stale | Alias `LATEST` + refresh explícito |
| Credenciales en código o `.env` commitado | Seguridad | Key Vault / secret store; rotación |
| Refresh concurrente del mismo dataset | Colisiones / errores 429 | Cola / lock / “skip if running” |
| Archivo Excel bloqueado al publicar | Upload incompleto | Copiar a temp + upload + verify size/hash |
| Cambio de esquema de MATRIZ | Rompe modelo Power BI | Contrato de columnas versionado; pruebas de esquema |
| Permisos SharePoint insuficientes | Publicación falla en prod | Checklist de permisos en fase de spike |
| Doble fuente de verdad (API vs PBI) | Inconsistencias de negocio | Misma matriz como origen; documentar latencia de refresh |
| Timeout en archivos grandes (~17 MB) | Fallo intermitente | Retry con backoff; upload por sesión si aplica |

---

## 8. Recomendaciones

1. **Mantener el pipeline puro.** Genera artefactos; no llama a Microsoft APIs.
2. **Usar puertos (interfaces) primero.** Implementar adapters mock para tests sin red.
3. **Publicar alias estable en SharePoint** además del archivo con timestamp.
4. **Power BI en modo Import + refresh programado/manual vía API**, no DirectQuery sobre Excel local.
5. **Un orquestador CLI** (`python -m src.integration.run`) antes de exponer botones en UI.
6. **No alterar contratos API** de Margen/Dashboard/Tesorería/SEN/IMG para esta integración.
7. **Observabilidad:** cada corrida debe dejar log estructurado con IDs de refresh e item de SharePoint.
8. **Validar esquema** de columnas críticas (`concepto_detectado`, `grupo`, `concepto`, `currency_group`) antes de publicar.
9. **Separar ambientes** (DEV/QA/PROD) con distintos site/library/dataset.
10. **Spike técnico corto** (1–2 días) de auth Graph + un upload + un refresh antes del desarrollo completo.

---

## 9. Roadmap por fases

### Fase 0 — Diseño (INT-08) ✅

- Documento de arquitectura
- Acuerdos de desacoplamiento
- Sin código de conexión

### Fase 1 — Cimientos locales

- Carpeta `src/integration/` con puertos e implementaciones **mock**
- `ArtifactRegistry` sobre `OutputArtifactService`
- Orquestador que ejecute: detectar latest → generar audit (si falta) → “publish mock” → “refresh mock”
- Tests unitarios sin red

### Fase 2 — SharePoint real

- App registration + permisos
- `SharePointService` (upload/replace + URL)
- Publicación de `MATRIZ_FBL1N` y `CONCEPT_AUDIT`
- Política `LATEST` + histórico con timestamp

### Fase 3 — Power BI real

- Conectar dataset al archivo publicado (o Dataflow)
- `PowerBIService.trigger_refresh` + polling de estado
- Manejo de fallos y reintentos
- Verificación de que el reporte muestra datos del artefacto vigente

### Fase 4 — Orquestación unificada

- Un comando / job que ejecute pipeline → audit → SharePoint → Power BI
- Códigos de salida y reporte de corrida
- Opcional: tarea programada (Task Scheduler / Azure Automation)

### Fase 5 — Experiencia operacional (opcional)

- Estado de integración en API **nueva** (`/api/integration/status`) sin tocar módulos actuales
- Indicador en UI (página dedicada, no modificar páginas existentes)
- Notificaciones de fallo

### Fase 6 — Endurecimiento

- Key Vault, ambientes, monitoreo, alertas
- Pruebas de carga con matrices reales
- Runbooks de incidentes (refresh stuck, permisos, archivo corrupto)

---

## Apéndice — Límites explícitos de INT-08

| Acción | INT-08 |
|--------|--------|
| Crear `docs/INTEGRATION_ARCHITECTURE.md` | Sí |
| Implementar servicios Graph / Power BI | No |
| Modificar pipeline / API / frontend | No |
| Modificar Margen / Dashboard / Tesorería / SEN / IMG | No |
| Conexiones reales a Microsoft 365 | No |

---

## Resumen ejecutivo

La integración Power BI + SharePoint debe vivir en una **capa lateral desacoplada** que consume los artefactos ya producidos (`MATRIZ_FBL1N`, `CONCEPT_AUDIT`), los publica y dispara el refresco analítico, orquestados en un único flujo futuro. El pipeline, la API y el frontend permanecen como están; las conexiones reales se introducen por fases mediante interfaces (`PowerBIPort`, `SharePointPort`) e implementaciones reemplazables.
