import type { TreasuryData } from "../types/treasury";

/** Mock Tesorería — usado solo si DATA_SOURCE=mock. */
export const treasuryMock: TreasuryData = {
  header: {
    lastExecution: "N/D",
    status: "Mock",
  },
  kpis: [
    {
      id: "position",
      label: "Registros en flujo",
      value: "N/D",
      hint: "Mock",
      icon: "flow",
    },
    {
      id: "classified",
      label: "Flujos clasificados",
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
      label: "Conceptos de flujo",
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
