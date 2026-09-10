import { useCallback, useEffect, useRef, useState } from "react";
import { logger } from "../logger/logger";

export interface AsyncDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

function normalizeError(value: unknown): Error {
  return value instanceof Error
    ? value
    : new Error("Ocurrió un error inesperado al cargar los datos.");
}

/** Shared async state for adapter-backed page hooks. */
export function useAsyncData<T>(
  loader: () => Promise<T>,
  resourceName: string,
): AsyncDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const requestId = useRef(0);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);

    try {
      const nextData = await loader();
      if (mountedRef.current && currentRequest === requestId.current) {
        setData(nextData);
      }
    } catch (value) {
      const nextError = normalizeError(value);
      logger.error(`Failed to load ${resourceName}`, {
        message: nextError.message,
      });
      if (mountedRef.current && currentRequest === requestId.current) {
        setError(nextError);
      }
    } finally {
      if (mountedRef.current && currentRequest === requestId.current) {
        setLoading(false);
      }
    }
  }, [loader, resourceName]);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    return () => {
      mountedRef.current = false;
      requestId.current += 1;
    };
  }, [refresh]);

  return { data, loading, error, refresh };
}
