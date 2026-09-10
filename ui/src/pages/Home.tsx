import {
  Activity,
  CheckCircle2,
  Clock3,
  FileBarChart2,
  Timer,
} from "lucide-react";
import type { ReactNode } from "react";
import { getHomeModules } from "../config/modules";
import { PageScaffold } from "../components/layout/PageScaffold";
import { DataGrid } from "../components/ui/DataGrid";
import { EmptyDataState } from "../components/ui/EmptyDataState";
import { ErrorState } from "../components/ui/ErrorState";
import { InfoPanel } from "../components/ui/InfoPanel";
import { KPICard } from "../components/ui/KPICard";
import { LoadingState } from "../components/ui/LoadingState";
import { ModuleCard } from "../components/ui/ModuleCard";
import { Section } from "../components/ui/Section";
import { StatusCard } from "../components/ui/StatusCard";
import { useAuth } from "../hooks/useAuth";
import { useHome } from "../hooks/useHome";
import { useSystemStatus } from "../hooks/useSystemStatus";
import type { HomeKpiIcon } from "../types/home";
import styles from "./Home.module.css";

const KPI_ICONS: Record<HomeKpiIcon, ReactNode> = {
  reports: <FileBarChart2 size={18} strokeWidth={1.75} />,
  clock: <Clock3 size={18} strokeWidth={1.75} />,
  timer: <Timer size={18} strokeWidth={1.75} />,
  status: <CheckCircle2 size={18} strokeWidth={1.75} />,
};

/**
 * Executive operations Home — composition only.
 * Module names come exclusively from the unified module registry.
 */
export function HomePage() {
  const { user, hasPermission } = useAuth();
  const homeQuery = useHome();
  const systemQuery = useSystemStatus();

  const refresh = async () => {
    await Promise.all([homeQuery.refresh(), systemQuery.refresh()]);
  };

  if (homeQuery.loading || systemQuery.loading) {
    return (
      <PageScaffold title="CBO Operations Analytics">
        <LoadingState label="Cargando centro de operaciones…" />
      </PageScaffold>
    );
  }

  const error = homeQuery.error ?? systemQuery.error;
  if (error) {
    return (
      <PageScaffold title="CBO Operations Analytics">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!homeQuery.data || !systemQuery.data) {
    return (
      <PageScaffold title="CBO Operations Analytics">
        <EmptyDataState message="No hay información operativa disponible." />
      </PageScaffold>
    );
  }

  const {
    welcome: homeWelcome,
    kpis: homeKpis,
    activity,
    executions,
    information: infoPanelItems,
  } = homeQuery.data;
  const activityColumns = activity.columns;
  const activityRows = activity.rows;
  const executionColumns = executions.columns;
  const executionRows = executions.rows;
  const servicesMock = systemQuery.data;
  const modules = getHomeModules().filter((module) =>
    hasPermission(module.requiredPermission),
  );

  return (
    <PageScaffold
      title={homeWelcome.title}
      subtitle={homeWelcome.subtitle}
      description={homeWelcome.description}
      showClock
      lastUpdate={homeWelcome.lastUpdate}
      meta={[{ label: "Usuario", value: user.displayName }]}
    >
        <Section
          id="home-kpis"
          title="Indicadores principales"
          description="Resumen operativo de la plataforma (datos simulados)."
        >
          <div className={styles.kpiGrid}>
            {homeKpis.map((kpi) => (
              <KPICard
                key={kpi.id}
                label={kpi.label}
                value={kpi.value}
                hint={kpi.hint}
                icon={KPI_ICONS[kpi.icon]}
              />
            ))}
          </div>
        </Section>

        <Section
          id="home-services"
          title="Estado de servicios"
          description="Estado actual de los servicios y componentes del sistema."
        >
          <div className={styles.servicesGrid}>
            {servicesMock.map((service) => (
              <StatusCard key={service.id} service={service} />
            ))}
          </div>
        </Section>

        <Section
          id="home-modules"
          title="Módulos del sistema"
          description="Informes y capacidades disponibles. Solo los módulos activos permiten operación completa."
        >
          <div className={styles.modulesGrid}>
            {modules.map((module) => (
              <ModuleCard key={module.id} module={module} />
            ))}
          </div>
        </Section>

        <div className={styles.tablesRow}>
          <Section
            id="home-activity"
            title="Actividad reciente"
            description="Eventos operativos simulados de la plataforma."
            className={styles.tableBlock}
          >
            <DataGrid
              columns={activityColumns}
              rows={activityRows}
              caption="Últimos eventos"
            />
          </Section>
          <Section
            id="home-history"
            title="Historial de ejecuciones"
            description="Ejecuciones simuladas de informes."
            className={styles.tableBlock}
          >
            <DataGrid
              columns={executionColumns}
              rows={executionRows}
              caption="Ejecuciones"
            />
          </Section>
        </div>

        <Section
          id="home-information"
          title="Panel de información"
          description="Comunicados y seguimiento del producto."
        >
          <InfoPanel title="Información de la plataforma" items={infoPanelItems} />
        </Section>

        <p className={styles.footnote}>
          <Activity size={14} strokeWidth={1.75} aria-hidden />
          Centro de operaciones CBO — datos mock · sin conexión a backend en UI-02
        </p>
    </PageScaffold>
  );
}
