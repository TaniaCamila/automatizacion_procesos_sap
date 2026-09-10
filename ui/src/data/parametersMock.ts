import type { ParameterItem } from "../types/parameter";

/** Parámetros generales — typed UI mock, no business logic. */
export const parametersMock: ParameterItem[] = [
  {
    id: "fbl1n-path",
    label: "Ruta FBL1N",
    value: "\\\\corp\\operaciones\\fbl1n\\entrada",
    description: "Directorio simulado de la matriz FBL1N consolidada.",
    kind: "path",
  },
  {
    id: "output-path",
    label: "Ruta Output",
    value: "\\\\corp\\operaciones\\informes\\salida",
    description: "Destino simulado de los informes generados.",
    kind: "path",
  },
  {
    id: "excel-format",
    label: "Formato Excel",
    value: ".xlsx (Open XML)",
    description: "Formato de exportación configurado para los informes.",
    kind: "format",
  },
  {
    id: "language",
    label: "Idioma",
    value: "Español (Chile)",
    description: "Idioma de la plataforma y de los reportes exportados.",
    kind: "language",
  },
  {
    id: "timezone",
    label: "Zona horaria",
    value: "América/Santiago (UTC-4)",
    description: "Zona horaria de referencia para ejecuciones y registros.",
    kind: "timezone",
  },
  {
    id: "operator",
    label: "Usuario operador",
    value: "Operaciones CBO",
    description: "Cuenta operativa simulada para procesos programados.",
    kind: "user",
  },
];
