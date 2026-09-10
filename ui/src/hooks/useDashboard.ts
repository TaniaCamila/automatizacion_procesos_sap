import { dashboardService } from "../services/dashboard.service";
import { useAsyncData } from "./useAsyncData";

export function useDashboard() {
  return useAsyncData(dashboardService.getDashboard, "Dashboard Ejecutivo");
}
