export type ServiceHealth =
  | "operational"
  | "degraded"
  | "offline"
  | "not_configured";

export interface ServiceStatus {
  id: string;
  name: string;
  health: ServiceHealth;
  detail: string;
}
