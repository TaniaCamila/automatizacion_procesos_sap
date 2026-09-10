import type { AuthUser } from "../types/auth";

export const mockUser: AuthUser = {
  id: "cbo-analyst-01",
  displayName: "Operaciones Comerciales",
  email: "operaciones.cobo@example.local",
  role: "analyst",
  permissions: [
    "home.view",
    "reports.margen.view",
    "reports.tesoreria.view",
    "reports.sen.view",
    "reports.img.view",
    "dashboard.view",
    "configuration.view",
    "history.view",
  ],
};
