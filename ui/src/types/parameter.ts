export type ParameterKind =
  | "path"
  | "format"
  | "language"
  | "timezone"
  | "user";

export interface ParameterItem {
  id: string;
  label: string;
  value: string;
  description: string;
  kind: ParameterKind;
}
