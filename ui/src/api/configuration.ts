import type { ConfigurationData } from "../types/config";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export interface ConfigurationEntry {
  key: string;
  value: string;
  updatedAt: string | null;
}

/** Legacy configuration port kept for future granular endpoints. */
export interface ConfigurationApi {
  list(options?: RequestOptions): Promise<ApiResult<ConfigurationEntry[]>>;
}

export function getConfiguration(
  options?: RequestOptions,
): Promise<ApiResult<ConfigurationData>> {
  return apiClient.get<ConfigurationData>("/configuration", options);
}
