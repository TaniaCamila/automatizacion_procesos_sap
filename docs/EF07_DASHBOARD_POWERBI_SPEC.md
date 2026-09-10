# EF-07 — Diseño funcional Dashboard Power BI

**Proyecto:** Automatización FBL1N Tesorería
**Estado:** DISEÑO FUNCIONAL CONGELADO (sin PBIX, sin DAX, sin cambio de modelo)
**Fecha:** 2026-07-29
**Revisión:** R2 — Portada INICIO; R1 — Detalle Operacional, segmentadores globales, navegación, paleta

---

## 1. Alcance y restricciones

| Regla | Aplicación |
|---|---|
| Fuente única | `MODELO_POWERBI.xlsx` (derivado de `MATRIZ_OPERACIONAL_TESORERIA` ← FBL1N) |
| Fuente prohibida | Archivo Solicitud de Pago Extranjero (no es origen del dashboard) |
| Regla de negocio | Proceso válido = Referencia Derivada con cadena `KR31CLP → Cambio de Moneda → PA25USD` |
| Fuera de alcance EF-07 | `.pbix`, medidas DAX, modificación de modelo, modificación de módulos existentes |
| Continuidad operativa | Replicar la lógica de análisis de Tesorería y PivotTables históricas (EF-05) |

---

## 2. Fuente de datos (solo lectura)

**Archivo:** `data/output/MODELO_POWERBI.xlsx`

| Tabla | Rol | Campos |
|---|---|---|
| `FACT_PAGOS` | Hechos (1 fila = 1 proceso SAP) | SOCIEDAD, ACREEDOR, PROVISION_CONTABLE, NOMBRE_BENEFICIARIO, REFERENCIA_DERIVADA, VARIANTE, MONEDA, MONTO_USD, FECHA_PA25USD, MES_PAGO, AÑO_PAGO |
| `DIM_SOCIEDAD` | Dimensión | SOCIEDAD |
| `DIM_PROVEEDOR` | Dimensión | ACREEDOR, NOMBRE_BENEFICIARIO |
| `DIM_FECHA` | Dimensión calendario (desde FECHA_PA25USD) | FECHA, MES, AÑO, MES_NOMBRE, TRIMESTRE |
| `DIM_MONEDA` | Dimensión | MONEDA |

**Nota de diseño:** El modelo de datos no se modifica en EF-07. Campos de auditoría presentes en la matriz operacional pero no en FACT (`ESTADO_PROCESO`, `OBSERVACION`, `DOCUMENTO_PA25USD`, etc.) quedan fuera del dashboard hasta una extensión futura del modelo (no EF-07).

---

## 3. Relaciones del modelo (diseño)

Relaciones propuestas para consumo en Power BI (definición funcional; implementación en EF-08):

| Desde (Many) | Hacia (One) | Clave | Cardinalidad | Filtro cruzado |
|---|---|---|---|---|
| `FACT_PAGOS[SOCIEDAD]` | `DIM_SOCIEDAD[SOCIEDAD]` | SOCIEDAD | N:1 | Single (DIM → FACT) |
| `FACT_PAGOS[ACREEDOR]` | `DIM_PROVEEDOR[ACREEDOR]` | ACREEDOR | N:1 | Single (DIM → FACT) |
| `FACT_PAGOS[FECHA_PA25USD]` | `DIM_FECHA[FECHA]` | FECHA | N:1 | Single (DIM → FACT) |
| `FACT_PAGOS[MONEDA]` | `DIM_MONEDA[MONEDA]` | MONEDA | N:1 | Single (DIM → FACT) |

**Campos de análisis en FACT (sin dimensión propia en modelo actual):**

- `PROVISION_CONTABLE` → Concepto / Provisión Contable
- `REFERENCIA_DERIVADA` → Referencia
- `VARIANTE` → KN / KR / KN+KR
- `MES_PAGO`, `AÑO_PAGO` → atributos temporales de pago (complementan `DIM_FECHA`)

**Integridad esperada:** toda fila de FACT debe resolver SOCIEDAD, ACREEDOR y MONEDA contra DIMs. FECHA_PA25USD puede estar vacía en procesos sin PA25USD (relación opcional / blank).

---

## 4. Continuidad con análisis histórico Tesorería (EF-05)

El dashboard debe cubrir los mismos ejes que las PivotTables nativas:

| Pivot histórica | Ejes | Métrica | Página dashboard equivalente |
|---|---|---|---|
| `TD_CONCEPTO_PROVEEDOR` | Proveedor → Acreedor → Mes Pago | Suma MONTO_USD | P02 Proveedor |
| `TD_PROVISION` | Provisión Contable → Mes Pago | Suma MONTO_USD | P03 Concepto |
| `TD_SOCIEDAD` | Sociedad → Mes Pago | Suma MONTO_USD + Conteo procesos | P04 Sociedad |
| `TD_REFERENCIAS` | Referencia Derivada (+ filtros Sociedad, Variante) | Suma MONTO_USD | P05 Referencias |

---

## 5. Estructura de páginas

| ID | Página | Propósito |
|---|---|---|
| P00 | INICIO | Portada del reporte (entrada al dashboard) |
| P01 | Resumen Ejecutivo | Vista gerencial: volumen, monto, cobertura y composición |
| P02 | Análisis por Proveedor | Réplica operativa de TD_CONCEPTO_PROVEEDOR |
| P03 | Análisis por Concepto | Réplica operativa de TD_PROVISION (PROVISION_CONTABLE) |
| P04 | Análisis por Sociedad | Réplica operativa de TD_SOCIEDAD |
| P05 | Análisis por Referencia | Réplica operativa de TD_REFERENCIAS + detalle documental |
| P06 | Temporalidad de Pagos | Evolución por Mes/Año de pago y calendario PA25USD |
| P07 | Detalle Operacional | Tabla completa de procesos SAP (FACT_PAGOS) |

### 5.1 P00 — INICIO (portada)

Página inicial del reporte. No contiene visuales analíticos ni segmentadores globales.

| Elemento | Contenido |
|---|---|
| Logo corporativo | Imagen institucional (`assets/branding/logo_corporativo.png`; placeholder hasta disponer del archivo oficial) |
| Nombre del Dashboard | **Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)** |
| Fecha de actualización | Fecha/hora de generación del reporte / artefacto PBIX |
| Última carga de datos | Fecha/hora de modificación de `MODELO_POWERBI.xlsx` (fuente) |
| CTA | Botón **Ingresar al Dashboard** → navega a P01 Resumen Ejecutivo |

**Layout portada:** fondo corporativo (azul primario / gris claro); logo centrado o superior; título debajo; metadatos de fecha; botón CTA en verde primario o azul secundario.

---

## 6. Navegación entre páginas (botones)

Navegación controlada por **botones de acción** (Page navigation), no solo por el menú nativo de Power BI.

| Elemento | Ubicación | Comportamiento |
|---|---|---|
| Portada P00 | Centro | Único botón: **Ingresar al Dashboard** → P01 |
| Barra de navegación | Superior o lateral fija en P01–P07 | Botones: Resumen · Proveedor · Concepto · Sociedad · Referencia · Temporalidad · Detalle · (opcional) Inicio |
| Botón activo | Página actual | Estilo resaltado (azul primario) |
| Botones inactivos | Resto de páginas | Estilo secundario (gris / azul oscuro) |
| Destino | Cada botón | Navega a la página correspondiente (P00–P07) |
| Consistencia | P01–P07 | Misma posición, mismo orden, mismas etiquetas |

**Orden de botones (P01–P07):** Resumen → Proveedor → Concepto → Sociedad → Referencia → Temporalidad → Detalle
**Acceso a portada:** botón opcional "Inicio" en la barra, o solo vía apertura del reporte.

---

## 7. Paleta visual corporativa

Evitar la paleta por defecto de Power BI. Tema corporativo basado en azules, verdes y grises.

| Rol | Uso | Hex |
|---|---|---|
| Azul primario | Botón activo, títulos, KPIs principales, serie principal de gráficos | `#0B3A6E` |
| Azul secundario | Barras/columnas secundarias, bordes, iconografía | `#1F6AA5` |
| Azul claro | Fondos suaves de tarjetas, hover, resaltados | `#D6E6F5` |
| Verde primario | Indicadores positivos (cobertura, estados OK) | `#1B7A4E` |
| Verde claro | Fondos de estado positivo, acentos menores | `#D9F0E4` |
| Gris oscuro | Texto principal, ejes, encabezados de tabla | `#2F343A` |
| Gris medio | Texto secundario, bordes, botones inactivos | `#6B7280` |
| Gris claro | Fondos de página / paneles | `#F3F4F6` |
| Blanco | Fondo de visuales y tarjetas | `#FFFFFF` |
| Alerta (uso restringido) | Procesos sin PA25USD / excepciones | `#B45309` |

**Aplicación:**

- Fondo de página: gris claro `#F3F4F6`
- Tarjetas KPI: blanco + borde azul claro
- Valores KPI: azul primario; excepciones (sin PA25USD): alerta
- Gráficos categóricos: secuencia azul primario → azul secundario → verde primario → gris medio
- Tablas/matrices: encabezado azul primario, texto gris oscuro, filas alternas gris claro
- Botones navegación: activo azul primario; inactivo gris medio sobre blanco

---

## 8. KPIs propuestos (definición funcional — sin DAX)

| KPI | Definición de negocio | Base | Uso |
|---|---|---|---|
| Procesos SAP | Conteo de filas en FACT_PAGOS | FACT | P01, P04, P07 |
| Monto Total USD | Suma de MONTO_USD | FACT | Todas |
| Monto Promedio USD | Monto Total / Procesos | FACT | P01 |
| Procesos con PA25USD | Conteo donde FECHA_PA25USD no está vacío | FACT | P01 |
| Procesos sin PA25USD | Conteo donde FECHA_PA25USD está vacío | FACT | P01 |
| Cobertura PA25USD % | Procesos con PA25USD / Procesos SAP | FACT | P01 |
| Procesos por Variante | Conteo por VARIANTE (KN / KR / KN+KR) | FACT | P01 |
| Sociedades activas | Conteo distinto de SOCIEDAD | FACT / DIM | P01, P04 |
| Proveedores activos | Conteo distinto de ACREEDOR | FACT / DIM | P01, P02 |
| Conceptos activos | Conteo distinto de PROVISION_CONTABLE | FACT | P01, P03 |
| Referencias distintas | Conteo distinto de REFERENCIA_DERIVADA | FACT | P05 |

---

## 9. Visuales propuestos por página

### P00 — INICIO (portada)

| Zona | Visual | Contenido |
|---|---|---|
| Superior / centro | Imagen | Logo corporativo |
| Centro | Texto | Nombre del Dashboard |
| Bajo título | Texto / tarjeta | Fecha de actualización |
| Bajo título | Texto / tarjeta | Última carga de datos |
| Inferior centro | Botón de acción | **Ingresar al Dashboard** → P01 |

Sin gráficos analíticos. Sin segmentadores. Sin matrices.

### P01 — Resumen Ejecutivo

| Zona | Visual | Campos / KPI |
|---|---|---|
| Superior | Tarjetas KPI | Procesos SAP · Monto Total USD · Cobertura PA25USD % · Procesos sin PA25USD |
| Media izq. | Gráfico de barras | Monto USD por SOCIEDAD |
| Media der. | Gráfico de dona / barras | Procesos por VARIANTE |
| Inferior izq. | Gráfico de columnas | Monto USD por MES_PAGO (o MES_NOMBRE vía DIM_FECHA) |
| Inferior der. | Tabla resumen | Top 10 proveedores por Monto USD |

### P02 — Análisis por Proveedor

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Monto Total USD · Proveedores activos · Procesos SAP |
| Principal | Matriz | Filas: NOMBRE_BENEFICIARIO → ACREEDOR → MES_PAGO · Valores: Suma MONTO_USD |
| Lateral | Barras horizontales | Top N proveedores por Monto USD |
| Inferior | Tabla detalle | ACREEDOR, NOMBRE_BENEFICIARIO, REFERENCIA_DERIVADA, MONTO_USD, MES_PAGO, SOCIEDAD |

### P03 — Análisis por Concepto (Provisión Contable)

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Monto Total USD · Conceptos activos · Procesos SAP |
| Principal | Matriz | Filas: PROVISION_CONTABLE → MES_PAGO · Valores: Suma MONTO_USD |
| Lateral | Barras | Monto USD por PROVISION_CONTABLE |
| Inferior | Tabla | PROVISION_CONTABLE, SOCIEDAD, ACREEDOR, MONTO_USD, MES_PAGO |

### P04 — Análisis por Sociedad

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Monto Total USD · Sociedades activas · Procesos SAP |
| Principal | Matriz | Filas: SOCIEDAD → MES_PAGO · Valores: Suma MONTO_USD, Conteo procesos |
| Lateral | Columnas apiladas | Monto USD por SOCIEDAD y MES_PAGO |
| Inferior | Tabla | SOCIEDAD, VARIANTE, REFERENCIA_DERIVADA, MONTO_USD |

### P05 — Análisis por Referencia

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Referencias distintas · Monto Total USD |
| Principal | Matriz / tabla | Filas: REFERENCIA_DERIVADA · Valores: Suma MONTO_USD · Conteo |
| Detalle | Tabla operacional | REFERENCIA_DERIVADA, SOCIEDAD, ACREEDOR, NOMBRE_BENEFICIARIO, PROVISION_CONTABLE, VARIANTE, MONEDA, MONTO_USD, FECHA_PA25USD, MES_PAGO |
| Contexto | Barras | Monto USD por VARIANTE (en el contexto filtrado) |

### P06 — Temporalidad de Pagos

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Monto Total USD · AÑO_PAGO seleccionado · Procesos del período |
| Principal | Línea / columnas | Monto USD por MES_PAGO o DIM_FECHA[MES_NOMBRE] |
| Secundario | Matriz | Filas: AÑO_PAGO → MES_PAGO · Valores: Suma MONTO_USD, Conteo procesos |
| Inferior | Tabla | FECHA_PA25USD, MES_PAGO, AÑO_PAGO, SOCIEDAD, MONTO_USD, REFERENCIA_DERIVADA |

### P07 — Detalle Operacional

| Zona | Visual | Campos |
|---|---|---|
| Superior | Tarjetas | Procesos SAP · Monto Total USD |
| Principal | Tabla completa | Todos los campos de FACT_PAGOS en una sola vista |

**Columnas de la tabla completa (orden operativo):**

1. SOCIEDAD
2. ACREEDOR
3. NOMBRE_BENEFICIARIO
4. PROVISION_CONTABLE
5. REFERENCIA_DERIVADA
6. VARIANTE
7. MONEDA
8. MONTO_USD
9. FECHA_PA25USD
10. MES_PAGO
11. AÑO_PAGO

**Comportamiento:** una fila = un proceso SAP; respeta segmentadores globales; permite ordenar y buscar; no agrega ni oculta procesos.

---

## 10. Filtros

### 10.1 Filtros de página (recomendados)

| Página | Filtro | Campo | Tipo |
|---|---|---|---|
| Todas | Excluir MONTO_USD en blanco (opcional operativo) | FACT[MONTO_USD] | Filtro de página |
| P05 | Complemento local si se requiere (Sociedad/Variante ya están en globales) | — | — |
| P06 | Enfocar años con datos (complementario al segmentador Año) | AÑO_PAGO / DIM_FECHA[AÑO] | Filtro de página |

### 10.2 Filtros de reporte (globales)

No se definen filtros de reporte fijos en EF-07. El control global se realiza mediante **segmentadores sincronizados** (sección 11).

### 10.3 Reglas de filtrado de negocio

- No filtrar fuera procesos sin Solicitud de Pago Extranjero (esa fuente no participa).
- Procesos sin PA25USD permanecen visibles (KPI y detalle); no se eliminan.
- No inventar filtros SAP no presentes en FACT/DIM.

---

## 11. Segmentadores (slicers)

### 11.1 Barra global (sincronizada en páginas analíticas P01–P07)

| Segmentador | Campo | Origen | Interacción |
|---|---|---|---|
| Sociedad | SOCIEDAD | DIM_SOCIEDAD | Multi-selección |
| Año | AÑO_PAGO | FACT_PAGOS | Multi-selección |
| Mes | MES_PAGO | FACT_PAGOS | Multi-selección |
| Proveedor | NOMBRE_BENEFICIARIO (o ACREEDOR) | DIM_PROVEEDOR | Multi-selección + búsqueda |
| Variante | VARIANTE | FACT_PAGOS | Multi-selección |

**Nota:** La portada P00 no muestra segmentadores. Moneda no forma parte de la barra global; puede usarse solo como segmentador local si una página lo requiere en EF-08.

### 11.2 Segmentadores adicionales por página

| Página | Segmentador | Campo | Origen |
|---|---|---|---|
| P02 | Acreedor | ACREEDOR | DIM_PROVEEDOR |
| P03 | Concepto / Provisión | PROVISION_CONTABLE | FACT_PAGOS |
| P05 | Referencia | REFERENCIA_DERIVADA | FACT_PAGOS |
| P06 | Trimestre | TRIMESTRE | DIM_FECHA |

### 11.3 Comportamiento esperado

- Segmentadores globales sincronizados entre P01–P07 (no en P00).
- Selección múltiple por defecto.
- Búsqueda habilitada en Proveedor, Concepto y Referencia.
- Jerarquía temporal preferida: Año → Mes (no forzar jerarquía DAX en EF-07).

---

## 12. Mapeo de ejes de negocio → modelo

| Análisis Tesorería | Campo modelo | Tabla |
|---|---|---|
| Concepto (Provisión Contable) | PROVISION_CONTABLE | FACT_PAGOS |
| Proveedor | NOMBRE_BENEFICIARIO / ACREEDOR | FACT + DIM_PROVEEDOR |
| Sociedad | SOCIEDAD | FACT + DIM_SOCIEDAD |
| Mes de Pago | MES_PAGO (y DIM_FECHA) | FACT + DIM_FECHA |
| Monto USD | MONTO_USD | FACT_PAGOS |
| Referencia | REFERENCIA_DERIVADA | FACT_PAGOS |

---

## 13. Criterios de aceptación EF-07

- [x] Documento de diseño funcional entregado
- [x] Estructura de páginas definida (8 páginas: INICIO + 7 analíticas)
- [x] Portada INICIO con logo, nombre, fechas y botón Ingresar
- [x] Visuales propuestos por página
- [x] KPIs propuestos con definición de negocio (sin DAX)
- [x] Relaciones del modelo documentadas (sin alterar MODELO_POWERBI)
- [x] Filtros y segmentadores definidos
- [x] Segmentadores globales: Sociedad, Año, Mes, Proveedor, Variante
- [x] Navegación entre páginas mediante botones
- [x] Paleta visual corporativa (azules, verdes, grises)
- [x] Continuidad con PivotTables EF-05
- [x] Fuente única = MODELO_POWERBI.xlsx
- [x] Sin Solicitud Pago Extranjero como fuente
- [x] Sin `.pbix`, sin DAX, sin cambio de modelo
- [x] Diseño funcional CONGELADO

---

## 14. Siguiente etapa

**EF-08 — Construcción del archivo PBIX**
Consumirá este diseño (R2) para crear el `.pbix`, relaciones, visuales, botones de navegación, portada INICIO y tema corporativo. Las medidas DAX se implementarán allí.
