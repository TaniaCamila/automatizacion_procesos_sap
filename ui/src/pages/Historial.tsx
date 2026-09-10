import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileSpreadsheet,
  RefreshCw,
  Rows3,
  Timer,
} from "lucide-react";
import type { ReactNode } from "react";
import { PageScaffold } from "../components/layout/PageScaffold";
import {
  Button,
  DataGrid,
  EmptyDataState,
  ErrorState,
  FilterBar,
  InfoPanel,
  KPICard,
  LoadingState,
  Panel,
  Section,
} from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useHistory } from "../hooks/useHistory";
import type { HistoryKpiIcon } from "../types/history";
import styles from "./Historial.module.css";

const KPI_ICONS: Record<HistoryKpiIcon, ReactNode> = {
  executions: <Activity size={20} strokeWidth={1.7} aria-hidden />,
  lastRun: <Clock3 size={20} strokeWidth={1.7} aria-hidden />,
  avgTime: <Timer size={20} strokeWidth={1.7} aria-hidden />,
  errors: <AlertTriangle size={20} strokeWidth={1.7} aria-hidden />,
  success: <CheckCircle2 size={20} strokeWidth={1.7} aria-hidden />,
  records: <Rows3 size={20} strokeWidth={1.7} aria-hidden />,
};

/** Historial Operativo — visor de ejecuciones de la plataforma (mock). */
export function HistorialPage() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useHistory();

  if (loading) {
    return (
      <PageScaffold title="Historial Operativo">
        <LoadingState label="Cargando historial…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="Historial Operativo">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="Historial Operativo">
        <EmptyDataState message="No existen ejecuciones para mostrar." />
      </PageScaffold>
    );
  }

  const historyPageMock = data;

  const filterActions = (
    <>
      <Button
        variant="secondary"
        size="sm"
        title="Actualizar datos"
        onClick={() => void refresh()}
      >
        <RefreshCw size={15} aria-hidden />
        Actualizar
      </Button>
      <Button variant="primary" size="sm" title="Exportación simulada">
        <FileSpreadsheet size={15} aria-hidden />
        Exportar
      </Button>
    </>
  );

  return (
    <PageScaffold
      title="Historial Operativo"
      subtitle="Seguimiento de todas las ejecuciones de la plataforma."
      description="Permite revisar la actividad, detectar incidencias y consultar los resultados de cada proceso."
      meta={[
        { label: "Última ejecución", value: historyPageMock.header.lastExecution },
        { label: "Usuario", value: user.displayName },
        { label: "Estado", value: historyPageMock.header.status },
      ]}
    >
      <Section
        id="history-kpis"
        title="Indicadores operacionales"
        description="Resumen simulado de la actividad reciente de la plataforma."
      >
        <div className={styles.kpiGrid}>
          {historyPageMock.kpis.map((kpi) => (
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
        id="history-filters"
        title="Filtros de seguimiento"
        description="Criterios simulados para acotar el registro de ejecuciones."
      >
        <FilterBar
          fields={historyPageMock.filters}
          actions={filterActions}
          disabled={false}
        />
      </Section>

      <div className={styles.contentGrid}>
        <div className={styles.mainColumn}>
          <Section
            id="history-executions"
            title="Registro de ejecuciones"
            description="Detalle simulado de cada proceso ejecutado en la plataforma."
          >
            <DataGrid
              columns={historyPageMock.executions.columns}
              rows={historyPageMock.executions.rows}
              caption="Registro de ejecuciones de la plataforma"
            />
          </Section>
        </div>

        <aside className={styles.sideColumn} aria-label="Resumen operacional">
          <Panel
            title="Actividad reciente"
            description="Últimos eventos registrados."
          >
            <div className={styles.panelBody}>
              <ul className={styles.activityList}>
                {historyPageMock.recentActivity.map((item) => (
                  <li key={item.id} className={styles.activityItem}>
                    <span className={styles.activityTime}>{item.time}</span>
                    <h3 className={styles.activityTitle}>{item.title}</h3>
                    <p className={styles.activityDetail}>{item.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          </Panel>

          <Panel
            title="Estado de la plataforma"
            description="Contexto técnico de la última ejecución."
          >
            <div className={styles.panelBody}>
              <dl className={styles.platformList}>
                {historyPageMock.platform.map((metric) => (
                  <div key={metric.id} className={styles.platformItem}>
                    <dt className={styles.platformLabel}>{metric.label}</dt>
                    <dd className={styles.platformValue}>{metric.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Panel>

          <InfoPanel
            title="Información del módulo"
            items={historyPageMock.information}
          />
        </aside>
      </div>
    </PageScaffold>
  );
}
