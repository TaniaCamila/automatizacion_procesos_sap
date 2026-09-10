# Checklist construcción DASHBOARD_TESORERIA.pbix

- Paquete generado: 2026-07-29 15:07:50
- Última carga MODELO_POWERBI.xlsx: 2026-07-29 14:35:01
- Dashboard: Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)

## A. Datos (fuente única)
- [ ] Abrir Power BI Desktop
- [ ] Obtener datos → Excel → `data/output/MODELO_POWERBI.xlsx`
- [ ] Importar: FACT_PAGOS, DIM_SOCIEDAD, DIM_PROVEEDOR, DIM_FECHA, DIM_MONEDA
- [ ] NO importar Archivo Solicitud Pago Extranjero
- [ ] NO modificar el archivo Excel fuente

## B. Modelo
- [ ] Crear relaciones N:1 según `modelo/relationships.json`
- [ ] Crear tabla vacía `_Medidas`
- [ ] Implementar medidas DAX según `medidas/ESTRUCTURA_MEDIDAS.md` (fase posterior)

## C. Tema y recursos
- [ ] Ver → Temas → Examinar → `tema/theme_tesoreria.json`
- [ ] Usar `recursos/logo_corporativo.svg` en portada (o logo oficial)

## D. Páginas (ver `paginas/ORGANIZACION_PAGINAS.md`)
- [ ] P00 INICIO (portada)
- [ ] P01 Resumen Ejecutivo
- [ ] P02 Análisis por Proveedor
- [ ] P03 Análisis por Concepto
- [ ] P04 Análisis por Sociedad
- [ ] P05 Análisis por Referencia
- [ ] P06 Temporalidad de Pagos
- [ ] P07 Detalle Operacional

## E. Portada P00
- [ ] Logo corporativo
- [ ] Nombre: Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)
- [ ] Fecha de actualización: 2026-07-29 15:07:50
- [ ] Última carga de datos: 2026-07-29 14:35:01
- [ ] Botón **Ingresar al Dashboard** → P01

## F. Segmentadores globales (P01–P07, sincronizados)
- [ ] Sociedad
- [ ] Año
- [ ] Mes
- [ ] Proveedor
- [ ] Variante

## G. Navegación
- [ ] Botón CTA en P00
- [ ] Barra de botones en P01–P07

## H. Guardar PBIX
- [ ] Guardar como `data/output/DASHBOARD_TESORERIA.pbix`

## Referencias
- docs/EF07_DASHBOARD_POWERBI_SPEC.md (congelado)
- docs/EF08_PBIX_CONSTRUCTION.md
