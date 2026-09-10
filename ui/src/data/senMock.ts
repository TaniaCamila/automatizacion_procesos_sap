import type { SenData } from "../types/sen";

/** Mock SEN — usado solo si DATA_SOURCE=mock. */
export const senMock: SenData = {
  header: {
    lastExecution: "N/D",
    status: "Mock",
  },
  kpis: [
    {
      id: "records",
      label: "Registros SEN",
      value: "N/D",
      hint: "Mock",
      icon: "records",
    },
    {
      id: "classified",
      label: "Conceptos clasificados",
      value: "N/D",
      hint: "Mock",
      icon: "classified",
    },
    {
      id: "coverage",
      label: "Cobertura",
      value: "N/D",
      hint: "Mock",
      icon: "coverage",
    },
    {
      id: "concepts",
      label: "Conceptos SEN",
      value: "N/D",
      hint: "Mock",
      icon: "concepts",
    },
  ],
  filters: [],
  table: {
    columns: [
      { key: "concept", header: "Concepto" },
      { key: "records", header: "Registros", align: "right" },
      { key: "share", header: "Participación", align: "right" },
      { key: "status", header: "Estado" },
    ],
    rows: [],
  },
  executive: {
    summary: [],
    topConcepts: [],
    distribution: [],
    alerts: [],
    lastUpdate: "N/D",
  },
};
