import type { ServiceStatus } from "../../types/system";
import { Card } from "./Card";
import styles from "./StatusCard.module.css";

interface StatusCardProps {
  service: ServiceStatus;
}

const HEALTH_LABEL: Record<ServiceStatus["health"], string> = {
  operational: "Operativo",
  degraded: "Degradado",
  offline: "Fuera de línea",
  not_configured: "No configurado",
};

/** Generic integration/service status card. */
export function StatusCard({ service }: StatusCardProps) {
  return (
    <Card as="article" className={styles.card} padding="md">
      <div className={styles.row}>
        <span className={`${styles.dot} ${styles[service.health]}`} aria-hidden />
        <h3 className={styles.name}>{service.name}</h3>
        <span className={styles.health}>{HEALTH_LABEL[service.health]}</span>
      </div>
      <p className={styles.detail}>{service.detail}</p>
    </Card>
  );
}
