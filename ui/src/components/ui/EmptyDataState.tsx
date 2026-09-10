import { Inbox } from "lucide-react";
import { EmptyState } from "./EmptyState";

interface EmptyDataStateProps {
  title?: string;
  message?: string;
}

export function EmptyDataState({
  title = "Sin datos disponibles",
  message = "No hay información para mostrar en este momento.",
}: EmptyDataStateProps) {
  return (
    <EmptyState
      title={title}
      description={message}
      icon={<Inbox size={24} aria-hidden />}
    />
  );
}
