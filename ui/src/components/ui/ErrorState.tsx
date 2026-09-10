import { AlertCircle } from "lucide-react";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

interface ErrorStateProps {
  message?: string;
  onRetry: () => void | Promise<void>;
}

export function ErrorState({
  message = "No fue posible cargar la información.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div role="alert" aria-live="assertive">
      <EmptyState
        title="Error al cargar datos"
        description={message}
        icon={<AlertCircle size={24} aria-hidden />}
        action={
          <Button variant="primary" onClick={() => void onRetry()}>
            Reintentar
          </Button>
        }
      />
    </div>
  );
}
