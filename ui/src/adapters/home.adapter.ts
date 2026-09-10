import { getHome } from "../api/home";
import {
  activityColumns,
  activityRows,
  executionColumns,
  executionRows,
  homeKpis,
  homeWelcome,
  infoPanelItems,
} from "../data/homeMock";
import { logger } from "../logger/logger";
import type { HomeMockData } from "../types/home";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const homeAdapter = {
  async getHome(): Promise<HomeMockData> {
    const source = getDataSource();
    logger.debug("Loading operations home", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay({
          welcome: homeWelcome,
          kpis: homeKpis,
          activity: { columns: activityColumns, rows: activityRows },
          executions: { columns: executionColumns, rows: executionRows },
          information: infoPanelItems,
        });
      case "api":
        return unwrapApiResult(await getHome());
    }
  },
};
