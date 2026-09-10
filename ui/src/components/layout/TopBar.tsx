import { APP_NAME, APP_SUBTITLE } from "../../config/modules";
import { useClock } from "../../hooks/useClock";
import { useAuth } from "../../hooks/useAuth";
import styles from "./TopBar.module.css";

export function TopBar() {
  const { dateLabel, timeLabel } = useClock();
  const { user } = useAuth();

  return (
    <header className={styles.topbar}>
      <div className={styles.branding}>
        <span className={styles.title}>{APP_NAME}</span>
        <p className={styles.subtitle}>{APP_SUBTITLE}</p>
      </div>

      <div className={styles.meta}>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Fecha</span>
          <span className={styles.metaValue}>{dateLabel}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Hora</span>
          <span className={styles.metaValue}>{timeLabel}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>Usuario</span>
          <span className={styles.metaValue}>{user.displayName}</span>
        </div>
      </div>
    </header>
  );
}
