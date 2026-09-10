import { getSystemStatus } from "../api/system";
import { servicesMock } from "../data/servicesMock";
import { logger } from "../logger/logger";
import type { ServiceStatus } from "../types/system";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const servicesAdapter = {
  async getStatus(): Promise<ServiceStatus[]> {
    const source = getDataSource();
    logger.debug("Loading system status", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(servicesMock);
      case "api":
        return unwrapApiResult(await getSystemStatus());
    }
  },
};
