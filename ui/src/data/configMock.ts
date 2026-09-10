import type { ConfigMockData } from "../types/config";

/** Configuración — typed UI mock, no business logic. */
export const configMock = {
  header: {
    catalogVersion: "v2026.07-03",
    lastSync: "17/07/2026 · 18:20",
    status: "Sincronizado",
  },
  filters: [
    {
      id: "search",
      label: "Buscar",
      type: "text",
      placeholder: "Código, nombre o descripción",
    },
    {
      id: "status",
      label: "Estado",
      type: "select",
      placeholder: "Todos los estados",
      options: [
        { label: "Activo", value: "active" },
        { label: "Inactivo", value: "inactive" },
        { label: "En revisión", value: "review" },
      ],
    },
    {
      id: "type",
      label: "Tipo",
      type: "select",
      placeholder: "Todos los catálogos",
      options: [
        { label: "Sociedades", value: "companies" },
        { label: "Monedas", value: "currencies" },
        { label: "Conceptos", value: "concepts" },
        { label: "Parámetros", value: "parameters" },
      ],
    },
  ],
  information: [
    {
      id: "version",
      title: "Versión del catálogo",
      description: "Catálogo corporativo v2026.07-03 publicado por Operaciones.",
      type: "info",
      date: "17/07/2026",
    },
    {
      id: "next-sync",
      title: "Próxima sincronización",
      description:
        "Programada para el 24/07/2026 a las 08:00 (simulada, sin integración real).",
      type: "sprint",
      date: "24/07/2026",
    },
    {
      id: "observations",
      title: "Observaciones",
      description:
        "Dos conceptos permanecen en revisión funcional antes de su activación.",
      type: "alert",
      date: "Esta semana",
    },
    {
      id: "roadmap",
      title: "Roadmap",
      description:
        "La edición de catálogos se habilitará al integrar el backend de configuración.",
      type: "roadmap",
    },
  ],
} satisfies ConfigMockData;
