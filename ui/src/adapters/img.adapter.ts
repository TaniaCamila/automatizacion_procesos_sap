import { getImg } from "../api/img";
import { imgMock } from "../data/imgMock";
import { logger } from "../logger/logger";
import type { ImgData } from "../types/img";
import {
  getDataSource,
  unwrapApiResult,
  withSimulatedDelay,
} from "./data-source";

export const imgAdapter = {
  async getImg(): Promise<ImgData> {
    const source = getDataSource();
    logger.debug("Loading IMG report", { source });

    switch (source) {
      case "mock":
        return withSimulatedDelay(imgMock);
      case "api":
        return unwrapApiResult(await getImg());
    }
  },
};
