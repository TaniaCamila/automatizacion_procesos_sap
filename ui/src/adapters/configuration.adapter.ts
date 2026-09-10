import { getConfiguration } from "../api/configuration";
import { catalogsMock } from "../data/catalogsMock";
import { configMock } from "../data/configMock";
import { parametersMock } from "../data/parametersMock";
import { logger } from "../logger/logger";
import type { ConfigurationData } from "../types/config";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const configurationAdapter = {
  async getConfiguration(): Promise<ConfigurationData> {
    const source = getDataSource();
    logger.debug("Loading configuration center", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay({
          config: configMock,
          catalogs: catalogsMock,
          parameters: parametersMock,
        });
      case "api":
        return unwrapApiResult(await getConfiguration());
    }
  },
};
