import type { ImgData } from "../types/img";
import { apiClient } from "./client";
import type { ApiResult, RequestOptions } from "./client";

export function getImg(
  options?: RequestOptions,
): Promise<ApiResult<ImgData>> {
  return apiClient.get<ImgData>("/img", options);
}
