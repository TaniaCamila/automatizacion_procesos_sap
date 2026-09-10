# Estructura de medidas DAX — EF-08

**Estado:** ESTRUCTURA ÚNICAMENTE — fórmulas DAX no implementadas en esta fase.

Tabla sugerida en Power BI: `_Medidas`

| # | Medida | Descripción | Estado |
|---|---|---|---|
| 1 | Procesos SAP | Conteo de filas FACT_PAGOS | PENDIENTE_DAX |
| 2 | Monto Total USD | Suma MONTO_USD | PENDIENTE_DAX |
| 3 | Monto Promedio USD | Monto Total / Procesos SAP | PENDIENTE_DAX |
| 4 | Procesos con PA25USD | Conteo con FECHA_PA25USD no vacío | PENDIENTE_DAX |
| 5 | Procesos sin PA25USD | Conteo con FECHA_PA25USD vacío | PENDIENTE_DAX |
| 6 | Cobertura PA25USD % | Con PA25USD / Procesos SAP | PENDIENTE_DAX |
| 7 | Sociedades activas | Distinct SOCIEDAD | PENDIENTE_DAX |
| 8 | Proveedores activos | Distinct ACREEDOR | PENDIENTE_DAX |
| 9 | Conceptos activos | Distinct PROVISION_CONTABLE | PENDIENTE_DAX |
| 10 | Referencias distintas | Distinct REFERENCIA_DERIVADA | PENDIENTE_DAX |

## Notas

- No incluir fórmulas DAX hasta la fase de ensamblaje del PBIX.
- Las definiciones de negocio están en docs/EF07_DASHBOARD_POWERBI_SPEC.md § KPIs.
- Fuente de cálculo: únicamente FACT_PAGOS / DIMs de MODELO_POWERBI.xlsx.
