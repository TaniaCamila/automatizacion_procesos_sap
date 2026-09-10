import { Link, useLocation } from "react-router-dom";
import { getModuleByPath } from "../../config/modules";
import styles from "./Breadcrumb.module.css";

function resolveLabel(pathname: string): string {
  if (pathname === "/") return "Inicio";
  return getModuleByPath(pathname)?.name ?? "Página";
}

export function Breadcrumb() {
  const { pathname } = useLocation();
  const current = resolveLabel(pathname);

  return (
    <nav className={styles.crumb} aria-label="Breadcrumb">
      <Link to="/" className={styles.link}>
        Inicio
      </Link>
      {pathname !== "/" ? (
        <>
          <span className={styles.sep} aria-hidden>
            /
          </span>
          <span className={styles.current} aria-current="page">
            {current}
          </span>
        </>
      ) : null}
    </nav>
  );
}
