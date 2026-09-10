import type { DataGridColumn, InfoPanelItem } from "../types/data-display";
import type { HomeKpi } from "../types/home";

/** Home dashboard mocks — UI only, no HTTP / backend. */

export const homeWelcome = {
  title: "CBO Operations Analytics",
  subtitle: "Corporate Operations Reporting Platform",
  description:
    "Centraliza la generación, análisis y distribución de los informes operacionales del área CBO utilizando una única fuente de datos SAP.",
  lastUpdate: "Simulado · 17 jul 2026 — 18:20",
};

export const homeKpis: HomeKpi[] = [
  {
    id: "reports",
    label: "Informes generados",
    value: "12",
    hint: "Ciclo simulado",
    icon: "reports",
  },
  {
    id: "last-run",
    label: "Última ejecución",
    value: "15/07",
    hint: "11:52 · mock",
    icon: "clock",
  },
  {
    id: "avg-time",
    label: "Tiempo promedio",
    value: "2.4 m",
    hint: "Procesamiento simulado",
    icon: "timer",
  },
  {
    id: "health",
    label: "Estado general",
    value: "Operativo",
    hint: "Plataforma UI",
    icon: "status",
  },
];

export const activityColumns: DataGridColumn[] = [
  { key: "date", header: "Fecha" },
  { key: "user", header: "Usuario" },
  { key: "process", header: "Proceso" },
  { key: "result", header: "Resultado" },
  { key: "duration", header: "Duración", align: "right" },
];

export const activityRows: Record<string, string>[] = [
  {
    date: "17/07/2026",
    user: "Operaciones CBO",
    process: "Inicialización UI",
    result: "Completado",
    duration: "—",
  },
  {
    date: "15/07/2026",
    user: "Analista",
    process: "Generación matriz (simulado)",
    result: "Completado",
    duration: "2m 36s",
  },
  {
    date: "15/07/2026",
    user: "Sistema",
    process: "Validación de catálogos (simulado)",
    result: "Completado",
    duration: "12s",
  },
  {
    date: "14/07/2026",
    user: "Controller",
    process: "Revisión de conceptos (simulado)",
    result: "Con observaciones",
    duration: "18m",
  },
];

export const executionColumns: DataGridColumn[] = [
  { key: "report", header: "Nombre del informe" },
  { key: "date", header: "Fecha" },
  { key: "time", header: "Hora" },
  { key: "status", header: "Estado" },
  { key: "duration", header: "Tiempo", align: "right" },
  { key: "user", header: "Usuario" },
];

export const executionRows: Record<string, string>[] = [
  {
    report: "Informe Margen",
    date: "15/07/2026",
    time: "11:52",
    status: "Éxito",
    duration: "2m 36s",
    user: "Analista",
  },
  {
    report: "Informe Margen",
    date: "14/07/2026",
    time: "17:43",
    status: "Error simulado",
    duration: "—",
    user: "Sistema",
  },
  {
    report: "Informe Margen",
    date: "10/07/2026",
    time: "09:15",
    status: "Éxito",
    duration: "2m 12s",
    user: "Analista",
  },
];

export const infoPanelItems: InfoPanelItem[] = [
  {
    id: "sprint",
    title: "Sprint actual",
    description: "UI-02 — Dashboard Ejecutivo (Home). Solo interfaz; datos mock.",
    type: "sprint",
    date: "Jul 2026",
  },
  {
    id: "version",
    title: "Versión",
    description: "CBO Operations Analytics UI 0.1.0 — infraestructura + Home.",
    type: "info",
    date: "0.1.0-ui",
  },
  {
    id: "next",
    title: "Próximas funcionalidades",
    description:
      "Vista del Informe Margen, configuración de catálogos e historial operativo enlazado.",
    type: "roadmap",
    date: "Próximos sprints",
  },
  {
    id: "changes",
    title: "Últimos cambios",
    description:
      "Shell corporativo, design tokens y centro de operaciones en Home. Backend Python intacto.",
    type: "change",
    date: "UI-01 / UI-02",
  },
];
