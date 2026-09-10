import type { LucideIcon } from "lucide-react";

export type ModuleStatus = "active" | "in_development";
export type ModuleCategory = "core" | "reports" | "system";
export type ModulePage =
  | "home"
  | "margen"
  | "tesoreria"
  | "sen"
  | "img"
  | "dashboard"
  | "coming-soon"
  | "configuration"
  | "history";

export interface ModuleDefinition {
  id: string;
  name: string;
  description: string;
  path: string;
  status: ModuleStatus;
  category: ModuleCategory;
  page: ModulePage;
  icon: LucideIcon;
  order: number;
  showInSidebar: boolean;
  showOnHome: boolean;
  requiredPermission?: string;
}
