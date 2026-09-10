import type { ReactNode } from "react";
import { Surface } from "./Surface";
import styles from "./Panel.module.css";

interface PanelProps {
  children: ReactNode;
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

/** Standard data/content panel with an optional header. */
export function Panel({
  children,
  title,
  description,
  actions,
  className = "",
}: PanelProps) {
  return (
    <Surface as="section" className={`${styles.panel} ${className}`}>
      {title || description || actions ? (
        <header className={styles.header}>
          <div>
            {title ? <h2 className={styles.title}>{title}</h2> : null}
            {description ? (
              <p className={styles.description}>{description}</p>
            ) : null}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </header>
      ) : null}
      <div className={styles.body}>{children}</div>
    </Surface>
  );
}
