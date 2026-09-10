import type { ServiceStatus } from "../types/system";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getSystemStatus(
  options?: RequestOptions,
): Promise<ApiResult<ServiceStatus[]>> {
  return apiClient.get<ServiceStatus[]>("/system/status", options);
}
