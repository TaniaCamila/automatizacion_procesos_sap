import {
  Activity,
  AlertTriangle,
  FileBarChart2,
  Gauge,
  LayoutGrid,
  Timer,
} from "lucide-react";
import type { ReactNode } from "react";
import { PageScaffold } from "../components/layout/PageScaffold";
import {
  Badge,
  DataGrid,
  EmptyDataState,
  ErrorState,
  InfoPanel,
  KPICard,
  LoadingState,
  ModuleCard,
  Panel,
  Section,
} from "../components/ui";
import { getModuleById } from "../config/modules";
import { useAuth } from "../hooks/useAuth";
import { useDashboard } from "../hooks/useDashboard";
import type { DashboardAlertTag, DashboardKpiIcon } from "../types/dashboard";
import styles from "./Dashboard.module.css";

const KPI_ICONS: Record<DashboardKpiIcon, ReactNode> = {
  processes: <Activity size={20} strokeWidth={1.7} aria-hidden />,
  reports: <FileBarChart2 size={20} strokeWidth={1.7} aria-hidden />,
  avgTime: <Timer size={20} strokeWidth={1.7} aria-hidden />,
  modules: <LayoutGrid size={20} strokeWidth={1.7} aria-hidden />,
  errors: <AlertTriangle size={20} strokeWidth={1.7} aria-hidden />,
  availability: <Gauge size={20} strokeWidth={1.7} aria-hidden />,
};

const ALERT_TAGS: Record<
  DashboardAlertTag,
  { label: string; variant: "warning" | "info" | "neutral" | "success" }
> = {
  warning: { label: "Advertencia", variant: "warning" },
  change: { label: "Cambio", variant: "info" },
  pending: { label: "Pendiente", variant: "neutral" },
  scheduled: { label: "Programado", variant: "success" },
};

/** Dashboard Ejecutivo — métricas reales desde /api/dashboard. */
export function DashboardPage() {
  const { user, hasPermission } = useAuth();
  const { data, loading, error, refresh } = useDashboard();

  if (loading) {
    return (
      <PageScaffold title="Dashboard Ejecutivo">
        <LoadingState label="Consolidando estado de la plataforma…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="Dashboard Ejecutivo">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="Dashboard Ejecutivo">
        <EmptyDataState message="No hay datos ejecutivos disponibles." />
      </PageScaffold>
    );
  }

  const modules = data.moduleDetails.flatMap((detail) => {
    const module = getModuleById(detail.moduleId);
    return module && hasPermission(module.requiredPermission)
      ? [{ module, detail }]
      : [];
  });

  const topConceptRows = data.activity.rows.slice(0, 5);

  return (
    <PageScaffold
      title="Dashboard Ejecutivo"
      subtitle="Centro de monitoreo operativo."
      description="Vista consolidada de cobertura y conceptos del último Informe Margen."
      meta={[
        { label: "Última ejecución", value: data.header.lastExecution },
        { label: "Usuario", value: user.displayName },
        { label: "Estado del proceso", value: data.header.status },
      ]}
    >
      <Section
        id="dashboard-kpis"
        title="Indicadores ejecutivos"
        description="Totales y cobertura calculados desde RESUMEN_CONCEPTOS."
      >
        <div className={styles.kpiGrid}>
          {data.kpis.map((kpi) => (
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

      {modules.length > 0 ? (
        <Section
          id="dashboard-modules"
          title="Estado de módulos"
          description="Contexto operativo de los módulos activos."
        >
          <div className={styles.modulesGrid}>
            {modules.map(({ module, detail }) => (
              <ModuleCard
                key={module.id}
                module={module}
                details={[
                  { label: "Última ejecución", value: detail.lastExecution },
                  { label: "Cobertura / disponibilidad", value: detail.availability },
                  { label: "Responsable", value: detail.owner },
                  { label: "Versión", value: detail.version },
                ]}
              />
            ))}
          </div>
        </Section>
      ) : null}

      <div className={styles.contentGrid}>
        <div className={styles.mainColumn}>
          <Section
            id="dashboard-top-concepts"
            title="Top 5 conceptos"
            description="Conceptos con mayor cantidad de registros clasificados."
          >
            <DataGrid
              columns={data.activity.columns}
              rows={topConceptRows}
              caption="Top 5 conceptos del último artefacto"
            />
          </Section>

          <Section
            id="dashboard-distribution"
            title="Distribución por concepto"
            description="Participación de cada concepto sobre el total de registros."
          >
            <DataGrid
              columns={data.activity.columns}
              rows={data.activity.rows}
              caption="Distribución completa por concepto"
            />
          </Section>
        </div>

        <aside className={styles.sideColumn} aria-label="Alertas e información">
          <Panel
            title="Alertas"
            description="Avisos operacionales de la plataforma."
          >
            <div className={styles.panelBody}>
              <ul className={styles.alertList}>
                {data.alerts.map((alert) => (
                  <li key={alert.id} className={styles.alertItem}>
                    <div className={styles.alertHead}>
                      <Badge variant={ALERT_TAGS[alert.tag].variant}>
                        {ALERT_TAGS[alert.tag].label}
                      </Badge>
                      <span className={styles.alertTime}>{alert.time}</span>
                    </div>
                    <h3 className={styles.alertTitle}>{alert.title}</h3>
                    <p className={styles.alertDetail}>{alert.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          </Panel>

          <InfoPanel
            title="Información de la plataforma"
            items={data.information}
          />
        </aside>
      </div>
    </PageScaffold>
  );
}
