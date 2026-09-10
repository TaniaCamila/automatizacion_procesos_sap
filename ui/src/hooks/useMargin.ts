import { reportsService } from "../services/reports.service";
import { useAsyncData } from "./useAsyncData";

export function useMargin() {
  return useAsyncData(reportsService.getMargin, "Informe Margen");
}
