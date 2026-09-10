import { homeService } from "../services/home.service";
import { useAsyncData } from "./useAsyncData";

export function useHome() {
  return useAsyncData(homeService.getHome, "Inicio");
}
