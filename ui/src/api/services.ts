import type { ServiceStatus } from "../types/system";
import type { ApiResult, RequestOptions } from "./client";

/** Future integrations-health backend port. Contract only. */
export interface ServicesApi {
  getStatus(options?: RequestOptions): Promise<ApiResult<ServiceStatus[]>>;
}
