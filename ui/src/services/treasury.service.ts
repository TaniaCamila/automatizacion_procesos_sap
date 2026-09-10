import { treasuryAdapter } from "../adapters/treasury.adapter";

export const treasuryService = {
  getTreasury: () => treasuryAdapter.getTreasury(),
};
