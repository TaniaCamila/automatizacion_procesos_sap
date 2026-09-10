import type { ReactNode } from "react";
import styles from "./Badge.module.css";

type BadgeVariant = "active" | "in_development" | "success" | "warning" | "neutral" | "info";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
}

export function Badge({ children, variant = "neutral" }: BadgeProps) {
  return <span className={`${styles.badge} ${styles[variant]}`}>{children}</span>;
}
