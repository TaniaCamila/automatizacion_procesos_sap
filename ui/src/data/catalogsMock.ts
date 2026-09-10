import type { CatalogsMockData } from "../types/catalog";

/** Catálogos administrativos — typed UI mock, no business logic. */
export const catalogsMock = {
  companies: {
    columns: [
      { key: "code", header: "Código" },
      { key: "name", header: "Nombre" },
      { key: "status", header: "Estado" },
      { key: "updatedAt", header: "Última actualización" },
      { key: "actions", header: "Acciones" },
    ],
    rows: [
      {
        code: "1000",
        name: "Sociedad Norte",
        status: "Activa",
        updatedAt: "17/07/2026",
        actions: "Ver detalle (mock)",
      },
      {
        code: "2000",
        name: "Sociedad Centro",
        status: "Activa",
        updatedAt: "15/07/2026",
        actions: "Ver detalle (mock)",
      },
      {
        code: "3000",
        name: "Sociedad Sur",
        status: "Activa",
        updatedAt: "15/07/2026",
        actions: "Ver detalle (mock)",
      },
      {
        code: "4000",
        name: "Sociedad Filial",
        status: "Inactiva",
        updatedAt: "02/06/2026",
        actions: "Ver detalle (mock)",
      },
    ],
  },
  currencies: {
    columns: [
      { key: "code", header: "Código" },
      { key: "description", header: "Descripción" },
      { key: "status", header: "Estado" },
      { key: "records", header: "Cantidad de registros", align: "right" },
    ],
    rows: [
      {
        code: "CLP",
        description: "Peso chileno",
        status: "Activa",
        records: "58.214",
      },
      {
        code: "USD",
        description: "Dólar estadounidense",
        status: "Activa",
        records: "9.876",
      },
      {
        code: "EUR",
        description: "Euro",
        status: "Activa",
        records: "1.031",
      },
      {
        code: "UF",
        description: "Unidad de fomento",
        status: "En revisión",
        records: "70",
      },
    ],
  },
  concepts: {
    table: {
      columns: [
        { key: "code", header: "Código" },
        { key: "name", header: "Concepto" },
        { key: "status", header: "Estado" },
        { key: "updatedAt", header: "Fecha actualización" },
      ],
      rows: [
        {
          code: "C-100",
          name: "Concepto A",
          status: "Activo",
          updatedAt: "17/07/2026",
        },
        {
          code: "C-200",
          name: "Concepto B",
          status: "Activo",
          updatedAt: "16/07/2026",
        },
        {
          code: "C-300",
          name: "Concepto C",
          status: "Activo",
          updatedAt: "14/07/2026",
        },
        {
          code: "C-410",
          name: "Concepto D",
          status: "En revisión",
          updatedAt: "10/07/2026",
        },
        {
          code: "C-520",
          name: "Concepto E",
          status: "En revisión",
          updatedAt: "08/07/2026",
        },
      ],
    },
    total: "42 conceptos",
    status: "Catálogo vigente",
    updatedAt: "17/07/2026",
  },
  status: [
    {
      id: "companies",
      name: "Sociedades",
      status: "Sincronizado",
      variant: "success",
      lastSync: "17/07/2026 · 18:20",
      records: "4 registros",
    },
    {
      id: "currencies",
      name: "Monedas",
      status: "Sincronizado",
      variant: "success",
      lastSync: "17/07/2026 · 18:20",
      records: "4 registros",
    },
    {
      id: "concepts",
      name: "Conceptos",
      status: "Revisión pendiente",
      variant: "warning",
      lastSync: "17/07/2026 · 18:20",
      records: "42 registros",
    },
    {
      id: "parameters",
      name: "Parámetros",
      status: "Sincronizado",
      variant: "success",
      lastSync: "17/07/2026 · 18:20",
      records: "6 registros",
    },
  ],
} satisfies CatalogsMockData;
