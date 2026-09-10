import type {
  DataGridColumn,
  FilterField,
  InfoPanelItem,
} from "./data-display";

export type ImgKpiIcon = "records" | "classified" | "coverage" | "concepts";

export interface ImgKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: ImgKpiIcon;
}

export interface ImgMetric {
  id: string;
  label: string;
  value: string;
  detail?: string;
}

export interface ImgDistributionItem {
  id: string;
  label: string;
  value: number;
  displayValue: string;
}

export interface ImgTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface ImgData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: ImgKpi[];
  filters: FilterField[];
  table: ImgTable;
  executive: {
    summary: ImgMetric[];
    topConcepts: ImgMetric[];
    distribution: ImgDistributionItem[];
    alerts: InfoPanelItem[];
    lastUpdate: string;
  };
}
