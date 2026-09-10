import type {
  DataGridColumn,
  FilterField,
  InfoPanelItem,
} from "./data-display";

export type MarginKpiIcon = "income" | "margin" | "average" | "records";

export interface MarginKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: MarginKpiIcon;
}

export interface MarginMetric {
  id: string;
  label: string;
  value: string;
  detail?: string;
}

export interface MarginDistributionItem {
  id: string;
  label: string;
  value: number;
  displayValue: string;
}

export interface MarginTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface MarginMockData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: MarginKpi[];
  filters: FilterField[];
  transactions: MarginTable;
  executive: {
    summary: MarginMetric[];
    topConcepts: MarginMetric[];
    alerts: InfoPanelItem[];
    distribution: MarginDistributionItem[];
    lastUpdate: string;
  };
  activity: MarginTable;
  exports: MarginTable;
}
