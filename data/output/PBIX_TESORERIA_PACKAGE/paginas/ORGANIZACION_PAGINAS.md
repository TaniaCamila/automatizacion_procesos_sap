# Organización de páginas — EF-07 / EF-08

| ID | Página | Rol | Segmentadores | Contenido |
|---|---|---|---|---|
| P00 | INICIO | portada | no | Logo · Nombre Dashboard · Fecha actualización · Última carga · Botón Ingresar → P01 |
| P01 | Resumen Ejecutivo | analitica | globales | KPIs · Monto por Sociedad · Variante · Mes · Top proveedores |
| P02 | Análisis por Proveedor | analitica | globales+Acreedor | Matriz Proveedor→Acreedor→Mes · Top N · Detalle |
| P03 | Análisis por Concepto | analitica | globales+Provision | Matriz PROVISION_CONTABLE→Mes · Barras · Tabla |
| P04 | Análisis por Sociedad | analitica | globales | Matriz Sociedad→Mes · Columnas · Tabla |
| P05 | Análisis por Referencia | analitica | globales+Referencia | Matriz REFERENCIA_DERIVADA · Tabla operacional · Variante |
| P06 | Temporalidad de Pagos | analitica | globales+Trimestre | Evolución Mes/Año · Matriz temporal · Tabla fechas |
| P07 | Detalle Operacional | analitica | globales | Tabla completa FACT_PAGOS (11 columnas) |

## Navegación

- P00: botón **Ingresar al Dashboard** → P01
- P01–P07: barra de botones Resumen · Proveedor · Concepto · Sociedad · Referencia · Temporalidad · Detalle
- Segmentadores globales (solo P01–P07): Sociedad · Año · Mes · Proveedor · Variante
