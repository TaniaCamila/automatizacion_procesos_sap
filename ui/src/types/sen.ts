import type {
  DataGridColumn,
  FilterField,
  InfoPanelItem,
} from "./data-display";

export type SenKpiIcon = "records" | "classified" | "coverage" | "concepts";

export interface SenKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: SenKpiIcon;
}

export interface SenMetric {
  id: string;
  label: string;
  value: string;
  detail?: string;
}

export interface SenDistributionItem {
  id: string;
  label: string;
  value: number;
  displayValue: string;
}

export interface SenTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface SenData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: SenKpi[];
  filters: FilterField[];
  table: SenTable;
  executive: {
    summary: SenMetric[];
    topConcepts: SenMetric[];
    distribution: SenDistributionItem[];
    alerts: InfoPanelItem[];
    lastUpdate: string;
  };
}
