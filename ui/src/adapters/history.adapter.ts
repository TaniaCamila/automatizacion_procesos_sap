import { getHistory } from "../api/history";
import { historyPageMock } from "../data/historyMock";
import { logger } from "../logger/logger";
import type { HistoryPageMockData } from "../types/history";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const historyAdapter = {
  async getHistory(): Promise<HistoryPageMockData> {
    const source = getDataSource();
    logger.debug("Loading operational history", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(historyPageMock);
      case "api":
        return unwrapApiResult(await getHistory());
    }
  },
};
