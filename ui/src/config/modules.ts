import {
  CircleDollarSign,
  Clock3,
  Gauge,
  Home,
  Landmark,
  Settings,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { ModuleCategory, ModuleDefinition } from "../types/module";

export const APP_NAME = "CBO Operations Analytics";
export const APP_SUBTITLE = "Corporate Operations Reporting Platform";
export const APP_VERSION = "0.3.0-ui";

/** Single source of truth for routing, navigation, breadcrumbs and Home cards. */
export const MODULE_REGISTRY: ModuleDefinition[] = [
  {
    id: "home",
    name: "Inicio",
    description: "Centro de operaciones de la plataforma",
    path: "/",
    status: "active",
    category: "core",
    page: "home",
    icon: Home,
    order: 10,
    showInSidebar: true,
    showOnHome: false,
    requiredPermission: "home.view",
  },
  {
    id: "margen",
    name: "Informe Margen",
    description: "Análisis operativo de márgenes",
    path: "/informes/margen",
    status: "active",
    category: "reports",
    page: "margen",
    icon: TrendingUp,
    order: 20,
    showInSidebar: true,
    showOnHome: true,
    requiredPermission: "reports.margen.view",
  },
  {
    id: "tesoreria",
    name: "Tesorería",
    description: "Flujos y posición de tesorería",
    path: "/informes/tesoreria",
    status: "active",
    category: "reports",
    page: "tesoreria",
    icon: Landmark,
    order: 30,
    showInSidebar: true,
    showOnHome: true,
    requiredPermission: "reports.tesoreria.view",
  },
  {
    id: "sen",
    name: "SEN",
    description: "Informes del Sistema Eléctrico Nacional",
    path: "/informes/sen",
    status: "active",
    category: "reports",
    page: "sen",
    icon: Zap,
    order: 40,
    showInSidebar: true,
    showOnHome: true,
    requiredPermission: "reports.sen.view",
  },
  {
    id: "img",
    name: "IMG",
    description: "Informes de pagos IMG",
    path: "/informes/img",
    status: "active",
    category: "reports",
    page: "img",
    icon: CircleDollarSign,
    order: 50,
    showInSidebar: true,
    showOnHome: true,
    requiredPermission: "reports.img.view",
  },
  {
    id: "dashboard",
    name: "Dashboard Ejecutivo",
    description: "Vista consolidada de la plataforma",
    path: "/dashboard",
    status: "active",
    category: "core",
    page: "dashboard",
    icon: Gauge,
    order: 60,
    showInSidebar: true,
    showOnHome: true,
    requiredPermission: "dashboard.view",
  },
  {
    id: "configuration",
    name: "Configuración",
    description: "Administración funcional de la plataforma",
    path: "/configuracion",
    status: "active",
    category: "system",
    page: "configuration",
    icon: Settings,
    order: 70,
    showInSidebar: true,
    showOnHome: false,
    requiredPermission: "configuration.view",
  },
  {
    id: "history",
    name: "Historial",
    description: "Ejecuciones y actividad operacional",
    path: "/historial",
    status: "active",
    category: "system",
    page: "history",
    icon: Clock3,
    order: 80,
    showInSidebar: true,
    showOnHome: false,
    requiredPermission: "history.view",
  },
];

export const CATEGORY_LABELS: Record<ModuleCategory, string> = {
  core: "Plataforma",
  reports: "Informes",
  system: "Administración",
};

export function getModuleById(id: string) {
  return MODULE_REGISTRY.find((module) => module.id === id);
}

export function getModuleByPath(pathname: string) {
  return MODULE_REGISTRY.find((module) => module.path === pathname);
}

export function getNavigationModules() {
  return MODULE_REGISTRY.filter((module) => module.showInSidebar).sort(
    (a, b) => a.order - b.order,
  );
}

export function getHomeModules() {
  return MODULE_REGISTRY.filter((module) => module.showOnHome).sort(
    (a, b) => a.order - b.order,
  );
}
