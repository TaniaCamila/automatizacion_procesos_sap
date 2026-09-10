import { senService } from "../services/sen.service";
import { useAsyncData } from "./useAsyncData";

export function useSen() {
  return useAsyncData(senService.getSen, "SEN");
}
