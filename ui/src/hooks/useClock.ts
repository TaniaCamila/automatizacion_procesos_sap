import { useEffect, useState } from "react";

function formatParts(date: Date) {
  const dateLabel = new Intl.DateTimeFormat("es-CL", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);

  const timeLabel = new Intl.DateTimeFormat("es-CL", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);

  return { dateLabel, timeLabel };
}

/** Live clock for TopBar / Home — UI only. */
export function useClock(intervalMs = 1000, enabled = true) {
  const [now, setNow] = useState(() => formatParts(new Date()));

  useEffect(() => {
    if (!enabled) return;

    const id = window.setInterval(() => {
      setNow(formatParts(new Date()));
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs]);

  return now;
}
