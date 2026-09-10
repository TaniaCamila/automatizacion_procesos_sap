import type { ReactNode } from "react";
import { useClock } from "../../hooks/useClock";
import { Surface } from "./Surface";
import styles from "./WelcomeHeader.module.css";

export interface WelcomeHeaderMetaItem {
  label: string;
  value: string;
}

interface WelcomeHeaderProps {
  title: string;
  subtitle?: string;
  description?: string;
  /** Static meta rows (usuario, última actualización, etc.). */
  meta?: WelcomeHeaderMetaItem[];
  lastUpdate?: string;
  /** When true, appends live Fecha / Hora using useClock. */
  showClock?: boolean;
  actions?: ReactNode;
}

/**
 * Reusable executive header for Home and future report modules.
 * No page-specific hardcoding — all content via props.
 */
export function WelcomeHeader({
  title,
  subtitle,
  description,
  meta = [],
  lastUpdate,
  showClock = false,
  actions,
}: WelcomeHeaderProps) {
  const { dateLabel, timeLabel } = useClock(1000, showClock);

  const rows: WelcomeHeaderMetaItem[] = [
    ...(showClock
      ? [
          { label: "Fecha", value: dateLabel },
          { label: "Hora", value: timeLabel },
        ]
      : []),
    ...meta,
    ...(lastUpdate ? [{ label: "Última actualización", value: lastUpdate }] : []),
  ];

  return (
    <Surface as="section" className={styles.header}>
      <div className={styles.main}>
        <div className={styles.text}>
          <h1 className={styles.title}>{title}</h1>
          {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>

      {rows.length > 0 ? (
        <dl className={styles.meta}>
          {rows.map((item) => (
            <div key={item.label} className={styles.metaItem}>
              <dt className={styles.metaLabel}>{item.label}</dt>
              <dd className={styles.metaValue}>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </Surface>
  );
}
