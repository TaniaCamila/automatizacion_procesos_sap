import { getMargin } from "../api/reports";
import { marginMock } from "../data/marginMock";
import { logger } from "../logger/logger";
import type { MarginMockData } from "../types/margin";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const reportsAdapter = {
  async getMargin(): Promise<MarginMockData> {
    const source = getDataSource();
    logger.debug("Loading margin report", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(marginMock);
      case "api":
        return unwrapApiResult(await getMargin());
    }
  },
};
