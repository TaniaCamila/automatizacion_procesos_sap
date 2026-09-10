import { historyService } from "../services/history.service";
import { useAsyncData } from "./useAsyncData";

export function useHistory() {
  return useAsyncData(historyService.getHistory, "Historial Operativo");
}
