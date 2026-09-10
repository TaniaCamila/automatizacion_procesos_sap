import { logger } from "../logger/logger";
import { API_BASE_URL, API_TIMEOUT_MS } from "./config";

export class ApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly details?: unknown;

  constructor(
    message: string,
    options: { code?: string; status?: number; details?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code ?? "API_ERROR";
    this.status = options.status;
    this.details = options.details;
  }
}

export class NetworkError extends ApiError {
  constructor(message = "No fue posible conectar con el servidor.") {
    super(message, { code: "NETWORK_ERROR" });
    this.name = "NetworkError";
  }
}

export class TimeoutError extends ApiError {
  readonly timeoutMs: number;

  constructor(timeoutMs: number) {
    super(`La petición superó el tiempo límite de ${timeoutMs} ms.`, {
      code: "TIMEOUT_ERROR",
    });
    this.name = "TimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

export interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: HeadersInit;
}

export interface ApiClient {
  get<T>(path: string, options?: RequestOptions): Promise<ApiResult<T>>;
  post<TBody, TResponse>(
    path: string,
    body: TBody,
    options?: RequestOptions,
  ): Promise<ApiResult<TResponse>>;
}

interface HttpApiClientOptions {
  baseURL: string;
  timeoutMs?: number;
}

interface ErrorPayload {
  code?: string;
  message?: string;
  detail?: string;
}

let requestSequence = 0;

function buildUrl(baseURL: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseURL}${normalizedPath}`;
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text || undefined;
}

function responseError(response: Response, payload: unknown): ApiError {
  const body =
    typeof payload === "object" && payload !== null
      ? (payload as ErrorPayload)
      : undefined;

  return new ApiError(
    body?.message ??
      body?.detail ??
      `La API respondió con estado ${response.status}.`,
    {
      code: body?.code ?? "HTTP_ERROR",
      status: response.status,
      details: payload,
    },
  );
}

export class HttpApiClient implements ApiClient {
  private readonly baseURL: string;
  private readonly timeoutMs: number;

  constructor({ baseURL, timeoutMs = API_TIMEOUT_MS }: HttpApiClientOptions) {
    this.baseURL = baseURL.replace(/\/+$/, "");
    this.timeoutMs = timeoutMs;
  }

  get<T>(path: string, options?: RequestOptions): Promise<ApiResult<T>> {
    return this.request<T>("GET", path, undefined, options);
  }

  post<TBody, TResponse>(
    path: string,
    body: TBody,
    options?: RequestOptions,
  ): Promise<ApiResult<TResponse>> {
    return this.request<TResponse>("POST", path, body, options);
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    options: RequestOptions = {},
  ): Promise<ApiResult<T>> {
    const url = buildUrl(this.baseURL, path);
    const requestId = `api-${++requestSequence}`;
    const startedAt = performance.now();
    const timeoutMs = options.timeoutMs ?? this.timeoutMs;
    const controller = new AbortController();
    let timedOut = false;

    const abortFromCaller = () => controller.abort(options.signal?.reason);
    if (options.signal?.aborted) {
      abortFromCaller();
    } else {
      options.signal?.addEventListener("abort", abortFromCaller, {
        once: true,
      });
    }

    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    const logContext = { method, url, requestId };
    logger.requestStarted(logContext);

    try {
      const headers = new Headers(options.headers);
      if (!headers.has("Accept")) {
        headers.set("Accept", "application/json");
      }
      if (body !== undefined && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }

      const response = await fetch(url, {
        method,
        signal: controller.signal,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const payload = await parseResponse(response);

      if (!response.ok) {
        throw responseError(response, payload);
      }

      logger.requestCompleted({
        ...logContext,
        status: response.status,
        durationMs: Math.round(performance.now() - startedAt),
      });
      return { ok: true, data: payload as T };
    } catch (value) {
      let error: ApiError;

      if (timedOut) {
        error = new TimeoutError(timeoutMs);
      } else if (value instanceof ApiError) {
        error = value;
      } else if (options.signal?.aborted) {
        error = new ApiError("La petición fue cancelada.", {
          code: "REQUEST_ABORTED",
        });
      } else {
        error = new NetworkError(
          value instanceof Error ? value.message : undefined,
        );
      }

      logger.requestFailed({
        ...logContext,
        durationMs: Math.round(performance.now() - startedAt),
        error: error.message,
        status: error.status,
      });
      return { ok: false, error };
    } finally {
      window.clearTimeout(timeoutId);
      options.signal?.removeEventListener("abort", abortFromCaller);
    }
  }
}

export const apiClient: ApiClient = new HttpApiClient({
  baseURL: API_BASE_URL,
});
