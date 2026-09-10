import type { FilterField, InfoPanelItem } from "./data-display";
import type { CatalogsMockData } from "./catalog";
import type { ParameterItem } from "./parameter";

export interface ConfigHeader {
  catalogVersion: string;
  lastSync: string;
  status: string;
}

export interface ConfigMockData {
  header: ConfigHeader;
  filters: FilterField[];
  information: InfoPanelItem[];
}

export interface ConfigurationData {
  config: ConfigMockData;
  catalogs: CatalogsMockData;
  parameters: ParameterItem[];
}
