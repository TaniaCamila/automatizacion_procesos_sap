import { getSen } from "../api/sen";
import { senMock } from "../data/senMock";
import { logger } from "../logger/logger";
import type { SenData } from "../types/sen";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const senAdapter = {
  async getSen(): Promise<SenData> {
    const source = getDataSource();
    logger.debug("Loading SEN report", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(senMock);
      case "api":
        return unwrapApiResult(await getSen());
    }
  },
};
