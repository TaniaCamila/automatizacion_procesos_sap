import type { ApiResult } from "../api/client";

export type DataSource = "mock" | "api";

/** Single switch for every frontend data adapter. */
export const DATA_SOURCE: DataSource = "api";

export function getDataSource(): DataSource {
  return DATA_SOURCE;
}

export function withSimulatedDelay<T>(
  data: T,
  delayMs = 400,
): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(data), delayMs);
  });
}

export function unwrapApiResult<T>(result: ApiResult<T>): T {
  if (result.ok) return result.data;
  throw result.error;
}
