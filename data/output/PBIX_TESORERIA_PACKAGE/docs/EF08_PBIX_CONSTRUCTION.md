# EF-08 — Construcción del archivo PBIX

**Proyecto:** Automatización FBL1N Tesorería
**Dashboard:** Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)
**Diseño:** `docs/EF07_DASHBOARD_POWERBI_SPEC.md` (congelado R2)
**Estado:** PREPARACIÓN DE PAQUETE — sin `.pbix` final, sin DAX implementado

---

## Objetivo

Preparar la estructura completa del proyecto Power BI para ensamblar posteriormente `DASHBOARD_TESORERIA.pbix`.

## Entradas

| Artefacto | Uso |
|---|---|
| `data/output/MODELO_POWERBI.xlsx` | Fuente única (solo lectura) |
| `docs/EF07_DASHBOARD_POWERBI_SPEC.md` | Diseño funcional congelado |
| `assets/branding/theme_tesoreria.json` | Tema corporativo |
| `assets/branding/logo_corporativo.svg` | Logo portada |

## Salidas (esta fase)

| Artefacto | Descripción |
|---|---|
| `data/output/PBIX_TESORERIA_PACKAGE/` | Estructura completa del proyecto Power BI |

**Fuera de esta fase:** `DASHBOARD_TESORERIA.pbix` · fórmulas DAX · apertura de Power BI Desktop

## Módulos afectados

| Módulo | Acción |
|---|---|
| `src/modules/pbix_tesoreria/` | Nuevo (solo preparación) |
| Pipeline / EF-01…EF-07 / MODELO_POWERBI / MATRIZ_OPERACIONAL | Sin cambios |

## Contenido del paquete

- `tema/` — tema corporativo
- `recursos/` — logo y assets
- `docs/` — documentación de construcción
- `paginas/` — organización P00–P07
- `medidas/` — estructura de medidas (sin DAX)
- `modelo/` — relaciones + puntero a fuente
- `checklist/` — checklist de construcción del PBIX

## Qué falta para el PBIX final

1. Abrir Power BI Desktop.
2. Importar `MODELO_POWERBI.xlsx` (FACT + DIMs).
3. Crear relaciones.
4. Implementar medidas DAX.
5. Aplicar tema y logo.
6. Construir páginas P00–P07, segmentadores y navegación.
7. Guardar `data/output/DASHBOARD_TESORERIA.pbix`.

Detalle: `PBIX_TESORERIA_PACKAGE/checklist/CHECKLIST_CONSTRUCCION_PBIX.md`
