import { servicesAdapter } from "../adapters/services.adapter";

export const systemService = {
  getStatus: () => servicesAdapter.getStatus(),
};
