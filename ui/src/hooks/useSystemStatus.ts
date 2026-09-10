import { systemService } from "../services/system.service";
import { useAsyncData } from "./useAsyncData";

export function useSystemStatus() {
  return useAsyncData(systemService.getStatus, "Estado del sistema");
}
