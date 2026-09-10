import { imgService } from "../services/img.service";
import { useAsyncData } from "./useAsyncData";

export function useImg() {
  return useAsyncData(imgService.getImg, "IMG");
}
