import {
  BadgeDollarSign,
  Landmark,
  Percent,
  RefreshCw,
  Rows3,
  WalletCards,
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
import { useTreasury } from "../hooks/useTreasury";
import type { TreasuryKpiIcon } from "../types/treasury";
import styles from "./Tesoreria.module.css";

const KPI_ICONS: Record<TreasuryKpiIcon, ReactNode> = {
  flow: <WalletCards size={20} strokeWidth={1.7} aria-hidden />,
  classified: <BadgeDollarSign size={20} strokeWidth={1.7} aria-hidden />,
  coverage: <Percent size={20} strokeWidth={1.7} aria-hidden />,
  concepts: <Rows3 size={20} strokeWidth={1.7} aria-hidden />,
};

export function TesoreriaPage() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useTreasury();

  if (loading) {
    return (
      <PageScaffold title="Tesorería">
        <LoadingState label="Cargando Tesorería…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="Tesorería">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="Tesorería">
        <EmptyDataState message="No hay datos de tesorería disponibles." />
      </PageScaffold>
    );
  }

  const headerMeta = (
    <Card as="aside" padding="sm" className={styles.headerMeta}>
      <dl className={styles.headerMetaList} aria-label="Estado de tesorería">
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
      title="Tesorería"
      subtitle="Flujos y posición de tesorería."
      description="Vista de cobertura y conceptos de flujo a partir del último artefacto FBL1N."
      actions={headerMeta}
    >
      <Section
        id="treasury-kpis"
        title="Indicadores de tesorería"
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
        id="treasury-filters"
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
        id="treasury-analysis"
        title="Análisis de flujos"
        description="Detalle por concepto y panel ejecutivo."
      >
        <SplitView
          leftRatio={60}
          left={
            <Panel className={styles.reportPanel}>
              <div className={styles.paneContent}>
                <header className={styles.paneHeader}>
                  <h3 className={styles.paneTitle}>
                    <Landmark size={18} aria-hidden /> Detalle por concepto
                  </h3>
                  <p className={styles.paneDescription}>
                    Distribución completa de conceptos clasificados.
                  </p>
                </header>
                <DataGrid
                  columns={data.table.columns}
                  rows={data.table.rows}
                  caption="Conceptos de flujo de tesorería"
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
                    Síntesis operacional de los flujos visibles.
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
