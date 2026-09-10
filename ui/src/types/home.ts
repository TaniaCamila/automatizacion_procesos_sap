import type { DataGridColumn, InfoPanelItem } from "./data-display";

export type HomeKpiIcon = "reports" | "clock" | "timer" | "status";

export interface HomeKpi {
  id: string;
  label: string;
  value: string;
  hint?: string;
  icon: HomeKpiIcon;
}

export interface HomeWelcome {
  title: string;
  subtitle: string;
  description: string;
  lastUpdate: string;
}

export interface HomeTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface HomeMockData {
  welcome: HomeWelcome;
  kpis: HomeKpi[];
  activity: HomeTable;
  executions: HomeTable;
  information: InfoPanelItem[];
}
