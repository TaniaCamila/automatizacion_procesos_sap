import { senAdapter } from "../adapters/sen.adapter";

export const senService = {
  getSen: () => senAdapter.getSen(),
};
