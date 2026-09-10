export interface DataGridColumn {
  key: string;
  header: string;
  align?: "left" | "right";
}

export interface FilterOption {
  label: string;
  value: string;
}

export interface FilterField {
  id: string;
  label: string;
  type?: "select" | "date" | "text";
  placeholder?: string;
  options?: FilterOption[];
  defaultValue?: string;
}

export type InfoPanelItemType =
  | "info"
  | "alert"
  | "change"
  | "roadmap"
  | "sprint"
  | "news"
  | "admin";

export interface InfoPanelItem {
  id: string;
  title: string;
  description: string;
  type: InfoPanelItemType;
  date?: string;
}
