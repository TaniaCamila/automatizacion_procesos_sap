type LogContext = Record<string, unknown>;

interface RequestLogContext extends LogContext {
  method: string;
  url: string;
  requestId: string;
}

function write(
  level: "info" | "warn" | "error" | "debug",
  message: string,
  context?: LogContext,
) {
  const args = context ? [message, context] : [message];
  console[level](...args);
}

/** Frontend observability boundary. Replace this implementation, not callers. */
export const logger = {
  info: (message: string, context?: LogContext) =>
    write("info", message, context),
  warn: (message: string, context?: LogContext) =>
    write("warn", message, context),
  error: (message: string, context?: LogContext) =>
    write("error", message, context),
  debug: (message: string, context?: LogContext) =>
    write("debug", message, context),
  requestStarted: (context: RequestLogContext) =>
    write("info", "API request started", context),
  requestCompleted: (
    context: RequestLogContext & { status: number; durationMs: number },
  ) => write("info", "API request completed", context),
  requestFailed: (
    context: RequestLogContext & {
      durationMs: number;
      error: string;
      status?: number;
    },
  ) => write("error", "API request failed", context),
};
