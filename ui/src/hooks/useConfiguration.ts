import { configurationService } from "../services/configuration.service";
import { useAsyncData } from "./useAsyncData";

export function useConfiguration() {
  return useAsyncData(
    configurationService.getConfiguration,
    "Configuración",
  );
}
