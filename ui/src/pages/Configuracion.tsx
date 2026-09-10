import {
  Clock3,
  FileSpreadsheet,
  FolderOpen,
  Languages,
  RefreshCw,
  UserCircle2,
} from "lucide-react";
import type { ReactNode } from "react";
import { PageScaffold } from "../components/layout/PageScaffold";
import {
  Badge,
  Button,
  Card,
  DataGrid,
  EmptyDataState,
  ErrorState,
  FilterBar,
  InfoPanel,
  LoadingState,
  Panel,
  Section,
} from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useConfiguration } from "../hooks/useConfiguration";
import type { ParameterKind } from "../types/parameter";
import styles from "./Configuracion.module.css";

const PARAMETER_ICONS: Record<ParameterKind, ReactNode> = {
  path: <FolderOpen size={18} strokeWidth={1.7} aria-hidden />,
  format: <FileSpreadsheet size={18} strokeWidth={1.7} aria-hidden />,
  language: <Languages size={18} strokeWidth={1.7} aria-hidden />,
  timezone: <Clock3 size={18} strokeWidth={1.7} aria-hidden />,
  user: <UserCircle2 size={18} strokeWidth={1.7} aria-hidden />,
};

/** Configuración — centro administrativo de catálogos y parámetros (mock). */
export function ConfiguracionPage() {
  const { user } = useAuth();
  const { data, loading, error, refresh } = useConfiguration();

  if (loading) {
    return (
      <PageScaffold title="Configuración">
        <LoadingState label="Cargando configuración…" />
      </PageScaffold>
    );
  }

  if (error) {
    return (
      <PageScaffold title="Configuración">
        <ErrorState message={error.message} onRetry={refresh} />
      </PageScaffold>
    );
  }

  if (!data) {
    return (
      <PageScaffold title="Configuración">
        <EmptyDataState message="No hay catálogos configurados." />
      </PageScaffold>
    );
  }

  const {
    config: configMock,
    catalogs: catalogsMock,
    parameters: parametersMock,
  } = data;

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
      title="Configuración"
      subtitle="Centro de administración de la plataforma."
      description="Gestión de sociedades, monedas, conceptos y parámetros generales sobre catálogos simulados."
      meta={[
        { label: "Versión del catálogo", value: configMock.header.catalogVersion },
        { label: "Última sincronización", value: configMock.header.lastSync },
        { label: "Estado", value: configMock.header.status },
        { label: "Usuario", value: user.displayName },
      ]}
    >
      <Section
        id="config-filters"
        title="Filtros de administración"
        description="Criterios simulados para explorar los catálogos corporativos."
      >
        <FilterBar
          fields={configMock.filters}
          actions={filterActions}
          disabled={false}
        />
      </Section>

      <div className={styles.contentGrid}>
        <div className={styles.mainColumn}>
          <Section
            id="config-companies"
            title="Sociedades"
            description="Sociedades habilitadas para el procesamiento de informes."
          >
            <DataGrid
              columns={catalogsMock.companies.columns}
              rows={catalogsMock.companies.rows}
              caption="Catálogo de sociedades"
            />
          </Section>

          <Section
            id="config-currencies"
            title="Monedas"
            description="Monedas reconocidas por la plataforma y su volumen asociado."
          >
            <DataGrid
              columns={catalogsMock.currencies.columns}
              rows={catalogsMock.currencies.rows}
              caption="Catálogo de monedas"
            />
          </Section>

          <Section
            id="config-concepts"
            title="Conceptos"
            description="Conceptos operacionales utilizados por los informes."
          >
            <Panel
              title="Catálogo de conceptos"
              description="Búsqueda disponible desde los filtros superiores."
              actions={
                <div className={styles.catalogMeta}>
                  <Badge variant="info">{catalogsMock.concepts.total}</Badge>
                  <Badge variant="success">{catalogsMock.concepts.status}</Badge>
                  <span className={styles.metaText}>
                    Actualizado el {catalogsMock.concepts.updatedAt}
                  </span>
                </div>
              }
            >
              <DataGrid
                columns={catalogsMock.concepts.table.columns}
                rows={catalogsMock.concepts.table.rows}
                caption="Catálogo de conceptos"
              />
            </Panel>
          </Section>

          <Section
            id="config-parameters"
            title="Parámetros generales"
            description="Valores de operación de la plataforma (solo lectura, simulados)."
          >
            <ul className={styles.parametersGrid}>
              {parametersMock.map((parameter) => (
                <li key={parameter.id}>
                  <Card as="article" padding="md" className={styles.parameterCard}>
                    <div className={styles.parameterTop}>
                      <h3 className={styles.parameterLabel}>{parameter.label}</h3>
                      <span className={styles.parameterIcon}>
                        {PARAMETER_ICONS[parameter.kind]}
                      </span>
                    </div>
                    <p className={styles.parameterValue}>{parameter.value}</p>
                    <p className={styles.parameterDescription}>
                      {parameter.description}
                    </p>
                  </Card>
                </li>
              ))}
            </ul>
          </Section>

          <Section
            id="config-status"
            title="Estado de catálogos"
            description="Sincronización simulada de cada catálogo administrativo."
          >
            <ul className={styles.statusGrid}>
              {catalogsMock.status.map((catalog) => (
                <li key={catalog.id}>
                  <Card as="article" padding="md" className={styles.statusCard}>
                    <div className={styles.statusHead}>
                      <h3 className={styles.statusName}>{catalog.name}</h3>
                      <Badge variant={catalog.variant}>{catalog.status}</Badge>
                    </div>
                    <dl className={styles.statusList}>
                      <div className={styles.statusItem}>
                        <dt className={styles.statusLabel}>
                          Última sincronización
                        </dt>
                        <dd className={styles.statusValue}>{catalog.lastSync}</dd>
                      </div>
                      <div className={styles.statusItem}>
                        <dt className={styles.statusLabel}>Registros</dt>
                        <dd className={styles.statusValue}>{catalog.records}</dd>
                      </div>
                    </dl>
                  </Card>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <aside className={styles.sideColumn} aria-label="Información del catálogo">
          <InfoPanel
            title="Información del catálogo"
            items={configMock.information}
          />
        </aside>
      </div>
    </PageScaffold>
  );
}
