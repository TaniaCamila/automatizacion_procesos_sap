import { historyAdapter } from "../adapters/history.adapter";

export const historyService = {
  getHistory: () => historyAdapter.getHistory(),
};
