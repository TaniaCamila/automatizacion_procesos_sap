import { useLocation } from "react-router-dom";
import { getModuleByPath } from "../config/modules";
import { PageScaffold } from "../components/layout/PageScaffold";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge } from "../components/ui/Badge";

export function ComingSoonPage() {
  const { pathname } = useLocation();
  const module = getModuleByPath(pathname);
  const title = module?.name ?? "Módulo";

  return (
    <PageScaffold
      title={title}
      subtitle="Capacidad planificada"
      description={module?.description}
    >
      <EmptyState
        title="En desarrollo"
        description="Este módulo está en desarrollo. Formará parte de CBO Operations Analytics en una versión futura."
        action={<Badge variant="in_development">En desarrollo</Badge>}
      />
    </PageScaffold>
  );
}
