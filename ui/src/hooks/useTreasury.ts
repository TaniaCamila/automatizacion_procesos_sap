import { treasuryService } from "../services/treasury.service";
import { useAsyncData } from "./useAsyncData";

export function useTreasury() {
  return useAsyncData(treasuryService.getTreasury, "Tesorería");
}
