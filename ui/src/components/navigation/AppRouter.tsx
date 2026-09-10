import {
  lazy,
  Suspense,
  type ComponentType,
  type LazyExoticComponent,
} from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { MODULE_REGISTRY } from "../../config/modules";
import { useAuth } from "../../hooks/useAuth";
import type { ModulePage } from "../../types/module";
import { Shell } from "../layout/Shell";
import { LoadingState } from "../ui/LoadingState";

const HomePage = lazy(() =>
  import("../../pages/Home").then((module) => ({ default: module.HomePage })),
);
const MargenPage = lazy(() =>
  import("../../pages/Margen").then((module) => ({
    default: module.MargenPage,
  })),
);
const DashboardPage = lazy(() =>
  import("../../pages/Dashboard").then((module) => ({
    default: module.DashboardPage,
  })),
);
const TesoreriaPage = lazy(() =>
  import("../../pages/Tesoreria").then((module) => ({
    default: module.TesoreriaPage,
  })),
);
const SenPage = lazy(() =>
  import("../../pages/Sen").then((module) => ({
    default: module.SenPage,
  })),
);
const ImgPage = lazy(() =>
  import("../../pages/Img").then((module) => ({
    default: module.ImgPage,
  })),
);
const ConfiguracionPage = lazy(() =>
  import("../../pages/Configuracion").then((module) => ({
    default: module.ConfiguracionPage,
  })),
);
const HistorialPage = lazy(() =>
  import("../../pages/Historial").then((module) => ({
    default: module.HistorialPage,
  })),
);
const ComingSoonPage = lazy(() =>
  import("../../pages/ComingSoon").then((module) => ({
    default: module.ComingSoonPage,
  })),
);

const PAGE_COMPONENTS: Record<
  ModulePage,
  LazyExoticComponent<ComponentType>
> = {
  home: HomePage,
  margen: MargenPage,
  tesoreria: TesoreriaPage,
  sen: SenPage,
  img: ImgPage,
  dashboard: DashboardPage,
  configuration: ConfiguracionPage,
  history: HistorialPage,
  "coming-soon": ComingSoonPage,
};

/** Central application router — pages mount into Shell outlet. */
export function AppRouter() {
  const { hasPermission } = useAuth();
  const routes = MODULE_REGISTRY.filter((module) =>
    hasPermission(module.requiredPermission),
  );

  return (
    <Routes>
      <Route element={<Shell />}>
        {routes.map((module) => {
          const Page = PAGE_COMPONENTS[module.page];
          const element = (
            <Suspense fallback={<LoadingState label="Cargando página…" />}>
              <Page />
            </Suspense>
          );

          return module.path === "/" ? (
            <Route key={module.id} index element={element} />
          ) : (
            <Route
              key={module.id}
              path={module.path.replace(/^\//, "")}
              element={element}
            />
          );
        })}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
