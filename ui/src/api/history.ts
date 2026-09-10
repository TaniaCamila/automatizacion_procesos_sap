import type { HistoryPageMockData, HistoryRow } from "../types/history";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

/** Future execution-history backend port. Contract only. */
export interface HistoryApi {
  list(options?: RequestOptions): Promise<ApiResult<HistoryRow[]>>;
}

export function getHistory(
  options?: RequestOptions,
): Promise<ApiResult<HistoryPageMockData>> {
  return apiClient.get<HistoryPageMockData>("/history", options);
}
