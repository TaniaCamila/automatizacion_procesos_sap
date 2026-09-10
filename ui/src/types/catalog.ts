import type { DataGridColumn } from "./data-display";

export interface CatalogTable {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
}

export interface ConceptsCatalog {
  table: CatalogTable;
  total: string;
  status: string;
  updatedAt: string;
}

export type CatalogStatusVariant = "success" | "warning" | "neutral" | "info";

export interface CatalogStatus {
  id: string;
  name: string;
  status: string;
  variant: CatalogStatusVariant;
  lastSync: string;
  records: string;
}

export interface CatalogsMockData {
  companies: CatalogTable;
  currencies: CatalogTable;
  concepts: ConceptsCatalog;
  status: CatalogStatus[];
}
