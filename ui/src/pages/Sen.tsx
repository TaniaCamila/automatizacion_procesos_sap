import {
  BadgeDollarSign,
  Percent,
  RefreshCw,
  Rows3,
  Zap,
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
import { useSen } from "../hooks/useSen";
import type { SenKpiIcon } from "../types/sen";
import styles from "./Sen.module.css";

const KPI_ICONS: Record<SenKpiIcon, ReactNode> = {
  records: <Zap size={20} strokeWidth={1.7} aria-hidden />,
  classified: <BadgeDollarSign size={20} strokeWidth={1.7} aria-hidden />,
  coverage: <Percent size={20} strokeWidth={1.7} aria-hidden />,
  concepts: <Rows3 size={20} strokeWidth={1.7} aria-hidden />,
};

export function SenPage() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useSen();

  if (loading) {
    return (
      <PageScaffold title="SEN">
        <LoadingState label="Cargando SEN…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="SEN">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="SEN">
        <EmptyDataState message="No hay datos SEN disponibles." />
      </PageScaffold>
    );
  }

  const headerMeta = (
    <Card as="aside" padding="sm" className={styles.headerMeta}>
      <dl className={styles.headerMetaList} aria-label="Estado SEN">
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Última ejecución</dt>
          <dd className={styles.headerMetaValue}>{data.header.lastExecution}</dd>
        </div>
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Usuario</dt>
          <dd className={styles.headerMetaValue}>{user.displayName}</dd>
        </div>
        <div className={styles.headerMetaItem}>
          <dt className={styles.headerMetaLabel}>Estado</dt>
          <dd className={styles.headerMetaValue}>
            <span className={styles.statusDot} aria-hidden />
            {data.header.status}
          </dd>
        </div>
      </dl>
    </Card>
  );

  const filterActions = (
    <Button
      variant="secondary"
      size="sm"
      title="Actualizar datos"
      onClick={() => void refresh()}
    >
      <RefreshCw size={15} aria-hidden />
      Actualizar
    </Button>
  );

  return (
    <PageScaffold
      title="SEN"
      subtitle="Sistema Eléctrico Nacional."
      description="Indicadores y conceptos SEN a partir del último artefacto FBL1N."
      actions={headerMeta}
    >
      <Section
        id="sen-kpis"
        title="Indicadores SEN"
        description="Totales y cobertura desde RESUMEN_CONCEPTOS."
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

      <Section
        id="sen-filters"
        title="Filtros de análisis"
        description="Conceptos detectados en el artefacto actual."
      >
        <FilterBar
          fields={data.filters}
          actions={filterActions}
          disabled={false}
        />
      </Section>

      <Section
        id="sen-analysis"
        title="Análisis SEN"
        description="Detalle por concepto e indicadores ejecutivos."
      >
        <SplitView
          leftRatio={60}
          left={
            <Panel className={styles.reportPanel}>
              <div className={styles.paneContent}>
                <header className={styles.paneHeader}>
                  <h3 className={styles.paneTitle}>
                    <Zap size={18} aria-hidden /> Detalle por concepto
                  </h3>
                  <p className={styles.paneDescription}>
                    Distribución completa de conceptos clasificados.
                  </p>
                </header>
                <DataGrid
                  columns={data.table.columns}
                  rows={data.table.rows}
                  caption="Conceptos SEN"
                />
              </div>
            </Panel>
          }
          right={
            <Panel className={styles.reportPanel}>
              <div className={styles.paneContent}>
                <header className={styles.paneHeader}>
                  <h3 className={styles.paneTitle}>Indicadores</h3>
                  <p className={styles.paneDescription}>
                    Síntesis operacional de los conceptos visibles.
                  </p>
                </header>

                <div className={styles.executiveStack}>
                  <Card as="section" padding="md">
                    <h4 className={styles.cardTitle}>Resumen</h4>
                    <ul className={styles.summaryGrid}>
                      {data.executive.summary.map((metric) => (
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
                      {data.executive.topConcepts.map((concept) => (
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
                    items={data.executive.alerts}
                    headingLevel="h4"
                  />

                  <Card as="section" padding="md">
                    <h4 className={styles.cardTitle}>Distribución</h4>
                    <ul className={styles.distributionList}>
                      {data.executive.distribution.map((item) => (
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
                              style={{
                                width: `${Math.min(item.value, 100)}%`,
                              }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </Card>

                  <Card as="section" padding="md">
                    <div className={styles.updateLine}>
                      <h4 className={styles.cardTitle}>Última actualización</h4>
                      <time className={styles.updateValue}>
                        {data.executive.lastUpdate}
                      </time>
                    </div>
                  </Card>
                </div>
              </div>
            </Panel>
          }
        />
      </Section>
    </PageScaffold>
  );
}
