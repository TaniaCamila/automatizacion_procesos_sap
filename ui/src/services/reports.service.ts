import { reportsAdapter } from "../adapters/reports.adapter";

/** Report use-cases. Data-source selection remains inside the adapter. */
export const reportsService = {
  getMargin: () => reportsAdapter.getMargin(),
};
