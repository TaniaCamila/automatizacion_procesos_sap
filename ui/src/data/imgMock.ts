import type { ImgData } from "../types/img";

/** Mock IMG — usado solo si DATA_SOURCE=mock. */
export const imgMock: ImgData = {
  header: {
    lastExecution: "N/D",
    status: "Mock",
  },
  kpis: [
    {
      id: "records",
      label: "Registros IMG",
      value: "N/D",
      hint: "Mock",
      icon: "records",
    },
    {
      id: "classified",
      label: "Pagos clasificados",
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
      label: "Conceptos IMG",
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
