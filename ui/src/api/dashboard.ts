import type { DashboardMockData } from "../types/dashboard";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getDashboard(
  options?: RequestOptions,
): Promise<ApiResult<DashboardMockData>> {
  return apiClient.get<DashboardMockData>("/dashboard", options);
}
