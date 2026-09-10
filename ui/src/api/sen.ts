import type { SenData } from "../types/sen";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getSen(
  options?: RequestOptions,
): Promise<ApiResult<SenData>> {
  return apiClient.get<SenData>("/sen", options);
}
