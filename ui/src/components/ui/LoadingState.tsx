import styles from "./LoadingState.module.css";

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = "Cargando…" }: LoadingStateProps) {
  return (
    <div className={styles.wrap} role="status" aria-live="polite">
      <div className={styles.spinner} aria-hidden />
      <p className={styles.label}>{label}</p>
    </div>
  );
}
