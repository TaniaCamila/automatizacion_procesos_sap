import { getTreasury } from "../api/treasury";
import { treasuryMock } from "../data/treasuryMock";
import { logger } from "../logger/logger";
import type { TreasuryData } from "../types/treasury";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const treasuryAdapter = {
  async getTreasury(): Promise<TreasuryData> {
    const source = getDataSource();
    logger.debug("Loading treasury report", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(treasuryMock);
      case "api":
        return unwrapApiResult(await getTreasury());
    }
  },
};
