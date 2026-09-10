import type { ReactNode } from "react";
import { Card } from "./Card";
import styles from "./KPICard.module.css";

interface KPICardProps {
  label: string;
  value: string;
  hint?: string;
  icon?: ReactNode;
}

/** Generic KPI tile — reusable across any report module. */
export function KPICard({ label, value, hint, icon }: KPICardProps) {
  return (
    <Card as="article" className={styles.card} padding="lg">
      <div className={styles.top}>
        <p className={styles.label}>{label}</p>
        {icon ? <span className={styles.icon}>{icon}</span> : null}
      </div>
      <p className={styles.value}>{value}</p>
      {hint ? <p className={styles.hint}>{hint}</p> : null}
    </Card>
  );
}
