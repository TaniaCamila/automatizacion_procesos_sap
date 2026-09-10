/** Runtime API configuration. URLs are supplied only through Vite env. */
export const API_BASE_URL = (
  import.meta.env.VITE_API_URL ?? ""
).replace(/\/+$/, "");

/** Margin Excel reads can exceed 10s; keep UI waiting for real API. */
export const API_TIMEOUT_MS = 120_000;
