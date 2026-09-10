import type { DataGridColumn, InfoPanelItem } from "./data-display";

export type DashboardKpiIcon =
  | "processes"
  | "reports"
  | "avgTime"
  | "modules"
  | "errors"
  | "availability";

export interface DashboardKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: DashboardKpiIcon;
}

/** Executive details attached to a registry module (mock, UI only). */
export interface DashboardModuleDetail {
  moduleId: string;
  lastExecution: string;
  availability: string;
  owner: string;
  version: string;
}

export interface DashboardTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export type DashboardAlertTag = "warning" | "change" | "pending" | "scheduled";

export interface DashboardAlert {
  id: string;
  tag: DashboardAlertTag;
  title: string;
  detail: string;
  time: string;
}

export interface DashboardMockData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: DashboardKpi[];
  moduleDetails: DashboardModuleDetail[];
  activity: DashboardTable;
  alerts: DashboardAlert[];
  information: InfoPanelItem[];
}
