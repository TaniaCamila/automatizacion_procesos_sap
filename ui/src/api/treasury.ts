import type { TreasuryData } from "../types/treasury";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getTreasury(
  options?: RequestOptions,
): Promise<ApiResult<TreasuryData>> {
  return apiClient.get<TreasuryData>("/treasury", options);
}
