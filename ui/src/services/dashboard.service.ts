import { dashboardAdapter } from "../adapters/dashboard.adapter";

export const dashboardService = {
  getDashboard: () => dashboardAdapter.getDashboard(),
};
