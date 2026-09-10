# DESIGN.md — Diseño UX/UI Corporativo (Aprobado)

**Producto:** Operations Analytics — Automatización de Procesos SAP
**Proyecto base:** Operations Analytics — Automatización de Procesos SAP
**Documento:** Diseño de experiencia e interfaz
**Versión:** 2.2 (alineada a UI actual / Capstone)
**Fecha:** Septiembre 2026
**Referencias:** [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/business_matrix_v1.md](docs/business_matrix_v1.md) · registro UI `ui/src/config/modules.ts` (solo lectura)

---

## Decisiones aprobadas (v2.2)

1. Nombre de la aplicación: **Operations Analytics — Automatización de Procesos SAP** (alineado a README y a la UI).
2. Módulos de informes en la UI actual (`modules.ts`): **Inicio**, **Informe Margen**, **Tesorería**, **SEN**, **IMG**, **Dashboard Ejecutivo**, **Configuración** e **Historial** aparecen como **activos** en el registro de navegación.
3. **Power BI** se mantiene como componente **en ajustes** (especificación y material de referencia); no forma parte de la automatización diaria completamente terminada.
4. Incluir **panel de estado del sistema** en Home.
5. Incluir **actividad reciente** preparada para futuras integraciones.
6. Distribución Vista analítica: **58% tabular / 42% visual**.
7. El diseño **no incluye reglas de negocio** (filtros de moneda, exclusiones, etc.). Esas reglas se definen e implementan en sprints de backend/negocio.

---

## Tabla de contenidos

1. [Objetivo del diseño](#1-objetivo-del-diseño)
2. [Perfil de los usuarios](#2-perfil-de-los-usuarios)
3. [Flujo completo de navegación](#3-flujo-completo-de-navegación)
4. [Mapa de pantallas](#4-mapa-de-pantallas)
5. [Wireframe — Pantalla principal](#5-wireframe--pantalla-principal)
6. [Wireframe — Informe Margen](#6-wireframe--informe-margen)
7. [Distribución de paneles](#7-distribución-de-paneles)
8. [Barra superior](#8-barra-superior)
9. [Menú lateral / navegación](#9-menú-lateral--navegación)
10. [Tarjetas de módulos](#10-tarjetas-de-módulos)
11. [Vista integrada Excel](#11-vista-integrada-excel)
12. [Vista integrada Power BI](#12-vista-integrada-power-bi)
13. [Diseño responsive](#13-diseño-responsive)
14. [Paleta de colores corporativa](#14-paleta-de-colores-corporativa)
15. [Tipografía](#15-tipografía)
16. [Iconografía recomendada](#16-iconografía-recomendada)
17. [Componentes reutilizables](#17-componentes-reutilizables)
18. [Reglas de diseño](#18-reglas-de-diseño)
19. [Experiencia de usuario](#19-experiencia-de-usuario)
20. [Justificación de cada decisión](#20-justificación-de-cada-decisión)

---

## 1. Objetivo del diseño

Diseñar la interfaz de **Operations Analytics — Automatización de Procesos SAP** como software empresarial moderno para Operaciones Comerciales, capaz de:

- Centralizar el acceso a informes derivados de datos SAP.
- Presentar **Informe Margen** como primer módulo productivo.
- Integrar lectura tabular y lectura visual en una sola experiencia.
- Escalar a Tesorería, IMG, SEN y Dashboard sin rediseñar la estructura.
- Transmitir confianza corporativa: claridad, trazabilidad y jerarquía visual.

El diseño describe **pantallas, navegación y componentes**. No define reglas de filtrado ni lógica de negocio.

---

## 2. Perfil de los usuarios

| Persona | Objetivo | Necesidades UX |
|---|---|---|
| Analista financiero | Validar y exportar informes | Tablas densas, exportación, navegación clara |
| Controller / Jefe de área | Ver estado y resúmenes | KPIs, Home, acceso rápido a Margen |
| Administrador de proceso | Supervisar ejecución futura | Estado del sistema, actividad reciente |

Uso principal: **escritorio ≥ 1280px**.

---

## 3. Flujo completo de navegación

```
Inicio (Home)
 │
 ├── Informes
 │    ├── Informe Margen     ← activo
 │    ├── Dashboard          ← próximamente
 │    ├── IMG                ← próximamente
 │    ├── Tesorería          ← próximamente
 │    └── SEN                ← próximamente
 │
 ├── Datos (placeholders UI)
 │    ├── Matriz FBL1N
 │    ├── Catálogos
 │    └── Ejecutar pipeline
 │
 └── Sistema
      └── Configuración
```

Flujo día a día (UI): Home → Informe Margen → Vista analítica → (exportación futura).

---

## 4. Mapa de pantallas

| ID | Pantalla | Estado UI actual |
|---|---|---|
| SCR-01 | Home / Inicio | Activo en registro UI |
| SCR-02 | Informe Margen | Activo |
| SCR-03 | Tesorería | Activo en registro UI |
| SCR-04 | SEN | Activo en registro UI |
| SCR-05 | IMG | Activo en registro UI |
| SCR-06 | Dashboard Ejecutivo | Activo en registro UI |
| SCR-07 | Configuración / Historial | Activos en registro UI |
| SCR-08 | Integración Power BI (visualizaciones) | En ajustes (fuera del flujo diario) |

---

## 5. Wireframe — Pantalla principal

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR · Operations Analytics — Automatización de Procesos SAP › Inicio                                      │
├──────────────┬───────────────────────────────────────────────────────────────┤
│ SIDEBAR      │  Bienvenida                                                   │
│              │                                                               │
│ ● Inicio     │  [KPI] [KPI] [KPI] [KPI]                                      │
│              │                                                               │
│ INFORMES     │  ACCIONES RÁPIDAS                                             │
│   Margen ●   │  [ Abrir Informe Margen ]                                     │
│   Dashboard  │                                                               │
│   IMG        │  MÓDULOS (registro UI actual: activos)                        │
│   Tesorería  │  [Margen] [Dashboard] [IMG] [Tesorería] [SEN]                 │
│   SEN        │  Power BI: en ajustes (no automatizado en el flujo diario)  │
│ SISTEMA      │                                                               │
│   Config.    │                                                               │
│   Historial  │                                                               │
│              │                                                               │
│ DATOS        │  ┌─ ACTIVIDAD RECIENTE ─────┐  ┌─ ESTADO DEL SISTEMA ──────┐ │
│   Matriz     │  │ Preparado para logs de   │  │ Input · Catálogos · Output│ │
│   Catálogos  │  │ pipeline e integraciones │  │ Integraciones (futuro)    │ │
│   Pipeline   │  └──────────────────────────┘  └───────────────────────────┘ │
│              │                                                               │
│ Config       │                                                               │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

---

## 6. Wireframe — Informe Margen

```
│ Informe Margen                                                               │
│ Tabs: [ Resumen ] [ Vista analítica ] [ Detalle ] [ Exportaciones ]          │
│                                                                              │
│ Filter Bar (genérica, sin reglas de negocio hardcodeadas)                    │
│                                                                              │
│ ┌─ Vista tabular 58% ─────────────┬─ Vista visual 42% ─────────────────────┐ │
│ │ Tabla / pivot (mock Sprint 1)   │ Gráficos (mock Sprint 1)               │ │
│ └─────────────────────────────────┴────────────────────────────────────────┘ │
```

---

## 7. Distribución de paneles

| Zona | Valor |
|---|---|
| Top bar | 56px |
| Sidebar | 240px / 64px colapsada |
| Split Vista analítica | **58% tabular / 42% visual** |
| Mínimo panel izquierdo | 480px |
| Mínimo panel derecho | 360px |

---

## 8. Barra superior

`[ Toggle ] [ Breadcrumb ] —— [ Buscar ] [ Notificaciones ] [ Usuario ]`

Fondo `primary-900`, altura 56px, branding en sidebar.

---

## 9. Menú lateral / navegación

- Informes según registro UI (`modules.ts`): **Margen**, **Tesorería**, **SEN**, **IMG** y **Dashboard** como entradas activas de navegación.
- Sistema: **Configuración** e **Historial**.
- Grupos: Informes · Plataforma · Administración.
- Ítem activo: barra izquierda + fondo `primary-800`.
- Power BI no se presenta como módulo diario cerrado; permanece **en ajustes**.

---

## 10. Tarjetas de módulos

Variantes alineadas al registro actual: módulos de informe/plataforma **activos** en navegación. Power BI se comunica como trabajo **en ajustes**, no como “Próximamente” genérico que contradiga la UI.

---

## 11. Vista integrada Excel

Panel nativo tabular (no clon de Microsoft Excel). Toolbar + grid + footer con metadatos. En Sprint 1: datos mock / vacío estructurado.

---

## 12. Vista integrada Power BI

Panel de visualización preparado para integración. En el estado Capstone, Power BI permanece **en ajustes** (especificación bajo `data/output/PBIX_TESORERIA_PACKAGE/`); no se asume embed productivo ni automatización diaria completada.

---

## 13. Diseño responsive

Desktop-first (≥1280px). Tablet: paneles apilados o tabs. Mobile: fase futura.

---

## 14. Paleta de colores corporativa

| Token | Hex |
|---|---|
| `primary-900` | `#0A1628` |
| `primary-800` | `#0F2744` |
| `primary-600` | `#1E4976` |
| `primary-500` | `#2563A8` |
| `primary-100` | `#E8F0FA` |
| `neutral-50` | `#F8FAFC` |
| `neutral-200` | `#E2E8F0` |
| `neutral-800` | `#1E293B` |
| `success-500` | `#059669` |
| `warning-500` | `#D97706` |
| `error-500` | `#DC2626` |
| Acento gráfico | `#0891B2` |

---

## 15. Tipografía

- UI: **Inter** (+ Segoe UI, system-ui).
- Datos: **JetBrains Mono** (+ Consolas).
- Escala: display 28 · heading 22/18/14 · body 14/12 · KPI 24.

---

## 16. Iconografía recomendada

Lucide Icons (outline). Margen=`TrendingUp`, Dashboard=`PieChart`, IMG=`Receipt`, Tesorería=`Landmark`, SEN=`Zap`.

---

## 17. Componentes reutilizables

AppShell · SidebarNav · TopBar · Breadcrumb · KPICard · ModuleCard · FilterBar · SplitView · DataTable · ChartPanel · PageHeader · ModuleTabs · StatusPanel · ActivityFeed · EmptyState · Badge · Toast

---

## 18. Reglas de diseño

1. Un solo ítem activo en sidebar.
2. Sin reglas de negocio en la UI de diseño (filtros genéricos / placeholders).
3. La navegación refleja el registro UI vigente; Power BI se documenta como **en ajustes**.
4. Mostrar metadatos (timestamp, fuente) cuando haya datos.
5. Densidad alta en tablas; media en Home.
6. WCAG 2.1 AA (contraste, focus, color no exclusivo).

---

## 19. Experiencia de usuario

- Home comunica estado y acceso a los informes registrados.
- Margen es el flujo analítico de referencia; el resto de módulos de informe están en el registro UI.
- Power BI no debe presentarse como automatización diaria terminada mientras esté en ajustes.
- Actividad reciente y estado del sistema anticipan integraciones futuras.

---

## 20. Justificación de cada decisión

| Decisión | Justificación |
|---|---|
| Nombre Operations Analytics — Automatización de Procesos SAP | Identidad única alineada a README y UI |
| Módulos activos según `modules.ts` | Evita contradicción doc ↔ configuración actual |
| Power BI en ajustes | Refleja el estado real Capstone sin sobreprometer |
| Panel estado del sistema | Transparencia operativa |
| Actividad reciente | Extensible a pipeline, SAP, Outlook, etc. |
| Split 58/42 | Prioriza lectura tabular del analista |
| Sin reglas de negocio en diseño | Separa UX de lógica; reglas en sprints de negocio |
| Shell modular | Nuevos módulos = registro de navegación + página |

---

## Sprint 1 — Alcance UI (histórico) y estado Capstone

**Historial Sprint 1:** shell, Home, Informe Margen (tabs + split), placeholders de configuración.
**Estado Capstone actual:** el registro UI incluye además Tesorería, SEN, IMG, Dashboard, Configuración e Historial como entradas activas.
**Power BI:** en ajustes (especificación académica; sin automatización diaria completa).
**Fuera del alcance del diseño UI:** SAP GUI, Outlook, SharePoint/OneDrive productivos y el procesamiento FBL1N (pertenecen al pipeline Python / operación diaria).

*Documento alineado al nombre canónico y al registro UI vigente.*
