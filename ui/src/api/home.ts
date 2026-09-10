import type { HomeMockData } from "../types/home";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getHome(
  options?: RequestOptions,
): Promise<ApiResult<HomeMockData>> {
  return apiClient.get<HomeMockData>("/home", options);
}
