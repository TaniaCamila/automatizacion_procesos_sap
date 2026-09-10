import {
  CircleDollarSign,
  FileSpreadsheet,
  Percent,
  RefreshCw,
  RotateCcw,
  Rows3,
  TrendingUp,
} from "lucide-react";
import type { ReactNode } from "react";
import { PageScaffold } from "../components/layout/PageScaffold";
import {
  Button,
  Card,
  DataGrid,
  EmptyDataState,
  ErrorState,
  FilterBar,
  InfoPanel,
  KPICard,
  LoadingState,
  Panel,
  Section,
  SplitView,
} from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useMargin } from "../hooks/useMargin";
import type { MarginKpiIcon } from "../types/margin";
import styles from "./Margen.module.css";

const KPI_ICONS: Record<MarginKpiIcon, ReactNode> = {
  income: <CircleDollarSign size={20} strokeWidth={1.7} aria-hidden />,
  margin: <TrendingUp size={20} strokeWidth={1.7} aria-hidden />,
  average: <Percent size={20} strokeWidth={1.7} aria-hidden />,
  records: <Rows3 size={20} strokeWidth={1.7} aria-hidden />,
};

export function MargenPage() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useMargin();

  if (loading) {
    return (
      <PageScaffold title="Informe Margen">
        <LoadingState label="Cargando Informe Margen…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="Informe Margen">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="Informe Margen">
        <EmptyDataState message="El informe no contiene datos disponibles." />
      </PageScaffold>
    );
  }

  const marginMock = data;

  const headerMeta = (
    <Card as="aside" padding="sm" className={styles.headerMeta}>
      <dl className={styles.headerMetaList} aria-label="Estado del informe">
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Última ejecución</dt>
          <dd className={styles.headerMetaValue}>
            {marginMock.header.lastExecution}
          </dd>
        </div>
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Usuario</dt>
          <dd className={styles.headerMetaValue}>{user.displayName}</dd>
        </div>
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Estado del informe</dt>
          <dd className={styles.headerMetaValue}>
            <span className={styles.statusDot} aria-hidden />
            {marginMock.header.status}
          </dd>
        </div>
      </dl>
    </Card>
  );

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
      <Button variant="ghost" size="sm" title="Acción simulada">
        <RotateCcw size={15} aria-hidden />
        Limpiar
      </Button>
      <Button variant="primary" size="sm" title="Exportación simulada">
        <FileSpreadsheet size={15} aria-hidden />
        Exportar Excel
      </Button>
    </>
  );

  return (
    <PageScaffold
      title="Informe Margen"
      subtitle="Análisis operacional de márgenes comerciales."
      description="Permite analizar los márgenes obtenidos desde la matriz FBL1N consolidada."
      actions={headerMeta}
    >
      <Section
        id="margin-kpis"
        title="Indicadores del informe"
        description="Vista ejecutiva de la última ejecución simulada."
      >
        <div className={styles.kpiGrid}>
          {marginMock.kpis.map((kpi) => (
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
        id="margin-filters"
        title="Filtros de análisis"
        description="Criterios simulados preparados para una futura fuente de datos."
      >
        <FilterBar
          fields={marginMock.filters}
          actions={filterActions}
          disabled={false}
        />
      </Section>

      <Section
        id="margin-analysis"
        title="Análisis operacional"
        description="Detalle transaccional y resumen ejecutivo del informe."
      >
        <SplitView
          leftRatio={60}
          left={
            <Panel className={styles.reportPanel}>
              <div className={styles.paneContent}>
                <header className={styles.paneHeader}>
                  <h3 className={styles.paneTitle}>Detalle de márgenes</h3>
                  <p className={styles.paneDescription}>
                    Registros consolidados de la matriz simulada.
                  </p>
                </header>
                <DataGrid
                  columns={marginMock.transactions.columns}
                  rows={marginMock.transactions.rows}
                  caption="Detalle de márgenes comerciales"
                />
              </div>
            </Panel>
          }
          right={
            <Panel className={styles.reportPanel}>
              <div className={styles.paneContent}>
                <header className={styles.paneHeader}>
                  <h3 className={styles.paneTitle}>Panel ejecutivo</h3>
                  <p className={styles.paneDescription}>
                    Síntesis operacional de los datos visibles.
                  </p>
                </header>

                <div className={styles.executiveStack}>
                  <Card as="section" padding="md">
                    <h4 className={styles.cardTitle}>Resumen</h4>
                    <ul className={styles.summaryGrid}>
                      {marginMock.executive.summary.map((metric) => (
                        <li key={metric.id} className={styles.metricItem}>
                          <span className={styles.metricLabel}>
                            {metric.label}
                          </span>
                          <strong className={styles.metricValue}>
                            {metric.value}
                          </strong>
                          {metric.detail ? (
                            <span className={styles.metricDetail}>
                              {metric.detail}
                            </span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </Card>

                  <Card as="section" padding="md">
                    <h4 className={styles.cardTitle}>Top conceptos</h4>
                    <ol className={styles.conceptList}>
                      {marginMock.executive.topConcepts.map((concept) => (
                        <li key={concept.id} className={styles.conceptItem}>
                          <span className={styles.conceptName}>
                            {concept.label}
                          </span>
                          <span className={styles.conceptValue}>
                            {concept.value}
                            {concept.detail ? (
                              <span className={styles.conceptDetail}>
                                {concept.detail}
                              </span>
                            ) : null}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </Card>

                  <InfoPanel
                    title="Alertas"
                    items={marginMock.executive.alerts}
                    headingLevel="h4"
                  />

                  <Card as="section" padding="md">
                    <h4 className={styles.cardTitle}>
                      Distribución simulada
                    </h4>
                    <ul className={styles.distributionList}>
                      {marginMock.executive.distribution.map((item) => (
                        <li key={item.id}>
                          <div className={styles.distributionHead}>
                            <span className={styles.distributionLabel}>
                              {item.label}
                            </span>
                            <span className={styles.distributionValue}>
                              {item.displayValue}
                            </span>
                          </div>
                          <div
                            className={styles.distributionTrack}
                            role="img"
                            aria-label={`${item.label}: ${item.displayValue}`}
                          >
                            <div
                              className={styles.distributionFill}
                              style={{ width: `${item.value}%` }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </Card>

                  <Card as="section" padding="md">
                    <div className={styles.updateLine}>
                      <h4 className={styles.cardTitle}>
                        Última actualización
                      </h4>
                      <time
                        className={styles.updateValue}
                        dateTime="2026-07-17T18:20:00"
                      >
                        {marginMock.executive.lastUpdate}
                      </time>
                    </div>
                  </Card>
                </div>
              </div>
            </Panel>
          }
        />
      </Section>

      <div className={styles.bottomGrid}>
        <Section
          id="margin-activity"
          title="Actividad reciente del informe"
          description="Eventos simulados asociados a la operación."
        >
          <DataGrid
            columns={marginMock.activity.columns}
            rows={marginMock.activity.rows}
            caption="Actividad reciente del Informe Margen"
          />
        </Section>

        <Section
          id="margin-exports"
          title="Historial de exportaciones"
          description="Archivos mock preparados para la integración futura."
        >
          <DataGrid
            columns={marginMock.exports.columns}
            rows={marginMock.exports.rows}
            caption="Historial de exportaciones del Informe Margen"
          />
        </Section>
      </div>
    </PageScaffold>
  );
}
