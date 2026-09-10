import { configurationAdapter } from "../adapters/configuration.adapter";

export const configurationService = {
  getConfiguration: () => configurationAdapter.getConfiguration(),
};
