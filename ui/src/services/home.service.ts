import { homeAdapter } from "../adapters/home.adapter";

export const homeService = {
  getHome: () => homeAdapter.getHome(),
};
