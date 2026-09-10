import { Link } from "react-router-dom";
import type { ModuleDefinition } from "../../types/module";
import { Badge } from "./Badge";
import { Card } from "./Card";
import styles from "./ModuleCard.module.css";

export interface ModuleCardDetail {
  label: string;
  value: string;
}

interface ModuleCardProps {
  module: ModuleDefinition;
  /** Optional executive details (e.g. last execution, owner, version). */
  details?: ModuleCardDetail[];
}

/** Generic module discovery card — not tied to a specific report. */
export function ModuleCard({ module, details }: ModuleCardProps) {
  const isActive = module.status === "active";
  const Icon = module.icon;

  return (
    <Link
      to={module.path}
      className={styles.link}
      aria-label={`${module.name}. ${isActive ? "Activo" : "En desarrollo"}`}
    >
      <Card
        as="article"
        padding="lg"
        className={`${styles.card} ${isActive ? styles.active : styles.dev}`}
      >
        <div className={styles.head}>
          <span className={styles.icon} aria-hidden>
            <Icon size={20} strokeWidth={1.7} />
          </span>
          <Badge variant={isActive ? "active" : "in_development"}>
            {isActive ? "Activo" : "En desarrollo"}
          </Badge>
        </div>
        <h3 className={styles.title}>{module.name}</h3>
        <p className={styles.description}>{module.description}</p>
        {details && details.length > 0 ? (
          <dl className={styles.details}>
            {details.map((detail) => (
              <div key={detail.label} className={styles.detailItem}>
                <dt className={styles.detailLabel}>{detail.label}</dt>
                <dd className={styles.detailValue}>{detail.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        <span className={styles.cta}>{isActive ? "Abrir" : "Ver estado"}</span>
      </Card>
    </Link>
  );
}
