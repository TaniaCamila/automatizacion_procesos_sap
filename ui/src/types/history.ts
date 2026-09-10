import type {
  DataGridColumn,
  FilterField,
  InfoPanelItem,
} from "./data-display";

export type ExecutionStatus = "success" | "failed" | "running" | "pending";

export interface HistoryRow {
  id: string;
  date: string;
  time: string;
  user: string;
  report: string;
  status: ExecutionStatus;
  outputFile: string | null;
  duration: string | null;
}

/* --- UI-06: operational history page (additive, keeps HistoryRow intact) --- */

export type HistoryKpiIcon =
  | "executions"
  | "lastRun"
  | "avgTime"
  | "errors"
  | "success"
  | "records";

export interface HistoryKpi {
  id: string;
  label: string;
  value: string;
  hint: string;
  icon: HistoryKpiIcon;
}

export interface HistoryTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface HistoryActivityItem {
  id: string;
  title: string;
  detail: string;
  time: string;
}

export interface HistoryPlatformMetric {
  id: string;
  label: string;
  value: string;
}

export interface HistoryPageMockData {
  header: {
    lastExecution: string;
    status: string;
  };
  kpis: HistoryKpi[];
  filters: FilterField[];
  executions: HistoryTable;
  recentActivity: HistoryActivityItem[];
  platform: HistoryPlatformMetric[];
  information: InfoPanelItem[];
}
