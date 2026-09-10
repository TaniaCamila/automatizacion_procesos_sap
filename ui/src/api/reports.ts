import type { MarginMockData } from "../types/margin";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export interface ReportSummary {
  id: string;
  name: string;
  generatedAt: string | null;
  status: string;
}

/** Future backend port. No implementation or HTTP calls in UI-03. */
export interface ReportsApi {
  list(options?: RequestOptions): Promise<ApiResult<ReportSummary[]>>;
  getById(
    reportId: string,
    options?: RequestOptions,
  ): Promise<ApiResult<ReportSummary>>;
}

/** Informe Margen endpoint contract. */
export function getMargin(
  options?: RequestOptions,
): Promise<ApiResult<MarginMockData>> {
  return apiClient.get<MarginMockData>("/reports/margin", options);
}
