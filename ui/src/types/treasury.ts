import type {
  DataGridColumn,
  FilterField,
  InfoPanelItem,
} from "./data-display";

export type TreasuryKpiIcon = "flow" | "classified" | "coverage" | "concepts";

export interface TreasuryKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: TreasuryKpiIcon;
}

export interface TreasuryMetric {
  id: string;
  label: string;
  value: string;
  detail?: string;
}

export interface TreasuryDistributionItem {
  id: string;
  label: string;
  value: number;
  displayValue: string;
}

export interface TreasuryTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface TreasuryData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: TreasuryKpi[];
  filters: FilterField[];
  table: TreasuryTable;
  executive: {
    summary: TreasuryMetric[];
    topConcepts: TreasuryMetric[];
    distribution: TreasuryDistributionItem[];
    alerts: InfoPanelItem[];
    lastUpdate: string;
  };
}
