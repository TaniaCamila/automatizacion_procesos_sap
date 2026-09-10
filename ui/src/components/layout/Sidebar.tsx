import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  APP_NAME,
  APP_VERSION,
  CATEGORY_LABELS,
  getNavigationModules,
} from "../../config/modules";
import { useAuth } from "../../hooks/useAuth";
import type { ModuleCategory, ModuleDefinition } from "../../types/module";
import { Badge } from "../ui/Badge";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

function NavLinkItem({
  module,
  collapsed,
}: {
  module: ModuleDefinition;
  collapsed: boolean;
}) {
  const inDev = module.status === "in_development";
  const Icon = module.icon;

  return (
    <NavLink
      to={module.path}
      end={module.path === "/"}
      className={({ isActive }) =>
        `${styles.link} ${isActive ? styles.active : ""} ${inDev ? styles.dev : ""}`
      }
      aria-label={`${module.name}${inDev ? ", en desarrollo" : ""}`}
      data-tooltip={collapsed ? module.name : undefined}
    >
      <Icon className={styles.linkIcon} size={20} strokeWidth={1.6} aria-hidden />
      {!collapsed ? (
        <>
          <span className={styles.linkLabel}>{module.name}</span>
          {inDev ? <Badge variant="in_development">En desarrollo</Badge> : null}
        </>
      ) : null}
    </NavLink>
  );
}

function NavGroup({
  category,
  modules,
  collapsed,
}: {
  category: ModuleCategory;
  modules: ModuleDefinition[];
  collapsed: boolean;
}) {
  if (modules.length === 0) return null;

  return (
    <div className={styles.group}>
      {!collapsed ? (
        <p className={styles.groupLabel}>{CATEGORY_LABELS[category]}</p>
      ) : (
        <div className={styles.groupDivider} aria-hidden />
      )}
      <div className={styles.groupChildren}>
        {modules.map((module) => (
          <NavLinkItem
            key={module.id}
            module={module}
            collapsed={collapsed}
          />
        ))}
      </div>
    </div>
  );
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, hasPermission } = useAuth();
  const [query, setQuery] = useState("");

  const modules = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("es");
    return getNavigationModules().filter(
      (module) =>
        hasPermission(module.requiredPermission) &&
        (!normalizedQuery ||
          module.name.toLocaleLowerCase("es").includes(normalizedQuery)),
    );
  }, [hasPermission, query]);

  const home = modules.filter((module) => module.id === "home");
  const reports = modules.filter((module) => module.category === "reports");
  const core = modules.filter(
    (module) => module.category === "core" && module.id !== "home",
  );
  const system = modules.filter((module) => module.category === "system");

  return (
    <aside
      className={`${styles.sidebar} ${collapsed ? styles.collapsed : ""}`}
      aria-label="Navegación principal"
    >
      <div className={styles.brand}>
        <div className={styles.mark} aria-hidden>
          CBO
        </div>
        {!collapsed ? (
          <div className={styles.brandText}>
            <span className={styles.brandName}>{APP_NAME}</span>
          </div>
        ) : null}
      </div>

      {!collapsed ? (
        <label className={styles.search}>
          <Search size={16} strokeWidth={1.7} aria-hidden />
          <span className="sr-only">Buscar módulo</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar módulo"
          />
        </label>
      ) : null}

      <nav className={styles.nav}>
        {home.map((module) => (
          <NavLinkItem
            key={module.id}
            module={module}
            collapsed={collapsed}
          />
        ))}
        <NavGroup category="reports" modules={reports} collapsed={collapsed} />
        {core.map((module) => (
          <NavLinkItem
            key={module.id}
            module={module}
            collapsed={collapsed}
          />
        ))}
        <NavGroup category="system" modules={system} collapsed={collapsed} />
      </nav>

      <footer className={styles.footer}>
        {!collapsed ? (
          <div className={styles.footerMeta}>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Usuario</span>
              <span className={styles.metaValue}>{user.displayName}</span>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Rol</span>
              <span className={styles.metaValue}>{user.role}</span>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Versión</span>
              <span className={styles.metaValue}>{APP_VERSION}</span>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Estado</span>
              <span className={styles.metaValue}>
                <span className={styles.statusDot} aria-hidden />
                UI Sprint 03
              </span>
            </div>
          </div>
        ) : null}
        <button
          type="button"
          className={styles.toggle}
          onClick={onToggle}
          aria-label={collapsed ? "Expandir navegación" : "Colapsar navegación"}
          data-tooltip={collapsed ? "Expandir navegación" : undefined}
        >
          {collapsed ? (
            <ChevronRight size={18} aria-hidden />
          ) : (
            <>
              <ChevronLeft size={18} aria-hidden />
              <span>Colapsar</span>
            </>
          )}
        </button>
      </footer>
    </aside>
  );
}
