import type { ServiceStatus } from "../types/system";

/** Simulated integration statuses — no real connections. */
export const servicesMock: ServiceStatus[] = [
  {
    id: "sap",
    name: "SAP",
    health: "not_configured",
    detail: "Fuente de datos FBL1N — integración pendiente",
  },
  {
    id: "python",
    name: "Python",
    health: "operational",
    detail: "Motor de procesamiento disponible (sin enlace UI)",
  },
  {
    id: "powerbi",
    name: "Power BI",
    health: "not_configured",
    detail: "Visualización analítica — pendiente",
  },
  {
    id: "onedrive",
    name: "OneDrive",
    health: "not_configured",
    detail: "Almacenamiento en la nube — pendiente",
  },
  {
    id: "sharepoint",
    name: "SharePoint",
    health: "not_configured",
    detail: "Publicación corporativa — pendiente",
  },
  {
    id: "outlook",
    name: "Outlook",
    health: "not_configured",
    detail: "Distribución por correo — pendiente",
  },
];
