import { getDashboard } from "../api/dashboard";
import { dashboardMock } from "../data/dashboardMock";
import { logger } from "../logger/logger";
import type { DashboardMockData } from "../types/dashboard";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const dashboardAdapter = {
  async getDashboard(): Promise<DashboardMockData> {
    const source = getDataSource();
    logger.debug("Loading executive dashboard", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(dashboardMock);
      case "api":
        return unwrapApiResult(await getDashboard());
    }
  },
};
