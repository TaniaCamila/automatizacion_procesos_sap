# Business Matrix v1

## 1. Objetivo de la matriz

La matriz empresarial es la representación detallada y estandarizada de las transacciones extraídas desde el archivo FBL1N. Su propósito es sustituir el proceso manual basado en tablas dinámicas de Excel y convertirse en la fuente única de verdad para análisis, reporting y futuras automatizaciones.

La matriz debe cumplir con las siguientes reglas de negocio:

- conservar los nombres originales del archivo SAP sin modificar su semántica
- trabajar a nivel transaccional, sin subtotales ni totales en la matriz base
- conservar todos los registros del archivo FBL1N sin eliminar duplicados ni transacciones
- no convertir importes entre monedas
- enriquecer cada registro con información de sociedades, monedas y conceptos
- permitir que Excel y Power BI consuman la misma matriz sin duplicar lógica

---

## 2. Alcance funcional

La matriz debe preparar la información para:

- Excel
- Power BI
- futuros procesos automáticos
- análisis de negocio continuo

La matriz no debe ser un reporte estático. Debe ser una tabla plana, limpia, normalizada y preparada para filtros, agregaciones y análisis.

---

## 3. Flujo completo de transformación de datos

El flujo de la matriz se define de la siguiente manera:

1. Lectura del archivo FBL1N
2. Validación estructural del archivo
3. Conservación de las columnas originales del SAP
4. Creación de aliases internos para uso técnico
5. Limpieza básica de textos y espacios
6. Normalización de tipos, especialmente para importes
7. Cruce con el catálogo de sociedades
8. Cruce con el catálogo de monedas
9. Detección de conceptos a partir del texto del documento
10. Marcación de concepto identificado o no identificado
11. Generación de columnas derivadas de período
12. Construcción de la matriz final de detalle

---

## 4. Estructura final de la matriz

La matriz final debe ser una tabla de detalle con una fila por transacción de FBL1N.

### 4.1 Columnas finales

| Columna | Origen | Tipo de dato | Regla de negocio aplicada | Justificación funcional |
|---|---|---|---|---|
| Texto cab.documento | FBL1N | Texto | Se conserva tal como llega desde SAP, con limpieza básica de espacios | Es la referencia textual original de la transacción y base para detección de conceptos |
| Importe en moneda doc. | FBL1N | Decimal | Se normaliza a valor numérico sin convertir moneda | Permite análisis financiero y agregaciones sin alterar la moneda original |
| Moneda del documento | FBL1N | Texto | Se conserva el código original y se limpia de espacios | Permite identificar la moneda de cada transacción y validar su existencia en el catálogo |
| Fecha compensación | FBL1N | Fecha | Se convierte al formato estándar de fecha | Permite análisis temporal y agrupación por período |
| Sociedad | FBL1N | Texto | Se conserva el código original y se limpia de espacios | Representa la asociación de la transacción con la sociedad origen |
| sociedad_nombre | SOCIEDADES | Texto | Se obtiene mediante lookup contra el catálogo maestro | Mejora la legibilidad del análisis y evita trabajar solo con códigos |
| moneda_valida | MONEDA | Booleano | Se marca como verdadero si la moneda existe en el catálogo maestro | Permite identificar monedas no controladas o no parametrizadas |
| concepto_detectado | CONCEPTOS | Texto | Se busca la nomenclatura definida en CONCEPTOS.xlsx dentro del campo Texto cab.documento | Permite clasificar la transacción por concepto sin modificar los datos originales |
| concepto_estado | CONCEPTOS | Texto | Se marca como Identificado o No identificado | Permite separar registros con concepto claro de aquellos que requieren revisión |
| mes_compensacion | FBL1N | Texto | Se transforma al formato AAAA-MM | Facilita agrupaciones mensuales y filtros temporales |
| anio_compensacion | FBL1N | Texto | Se extrae el año de la fecha de compensación | Facilita análisis por año y comparaciones temporales |

### 4.2 Alias internos recomendados

Los aliases internos son opcionales para procesamiento técnico y deben utilizarse únicamente para operaciones internas del pipeline. No reemplazan a las columnas originales SAP.

| Alias interno | Correspondencia | Uso |
|---|---|---|
| texto_cabdocumento | Texto cab.documento | procesamiento interno |
| importe_en_moneda_doc | Importe en moneda doc. | procesamiento interno |
| moneda_del_documento | Moneda del documento | procesamiento interno |
| fecha_compensacion | Fecha compensación | procesamiento interno |
| sociedad | Sociedad | procesamiento interno |

---

## 5. Reglas de negocio aplicadas

### 5.1 Conservación de datos SAP

Se debe preservar el valor original del campo proveniente de SAP. No se debe renombrar ni reescribir el significado original del dato.

### 5.2 Sin conversión de moneda

La matriz conserva siempre la moneda original del documento. No se deben transformar importes a otra moneda.

### 5.3 Sin eliminación de registros

Cada fila del archivo FBL1N representa una transacción válida y debe conservarse. No se deben eliminar transacciones ni fusionarlas durante la construcción de la matriz base.

### 5.4 Detección de conceptos

La detección de conceptos debe realizarse buscando la nomenclatura definida en CONCEPTOS.xlsx dentro del campo Texto cab.documento.

No debe asumirse igualdad exacta del texto completo. El algoritmo debe detectar conceptos incluso cuando el texto contenga información adicional antes o después de la nomenclatura.

### 5.5 Conceptos no identificados

Si no existe coincidencia con ningún concepto del catálogo, el registro no debe eliminarse. Debe conservarse y marcarse con concepto_estado = No identificado.

### 5.6 Matriz de detalle

La matriz debe ser de detalle transaccional. No debe incluir subtotales, totales ni resúmenes dentro de la tabla base.

---

## 6. Casos especiales

### 6.1 Concepto no encontrado

Cuando no se detecta un concepto válido:

- el registro debe mantenerse
- concepto_detectado debe quedar vacío
- concepto_estado debe marcarse como No identificado

### 6.2 Moneda no definida

Cuando la moneda del documento no aparece en MONEDA.xlsx:

- el registro debe mantenerse
- moneda_valida debe marcarse como falso

### 6.3 Sociedad no definida

Cuando la sociedad no aparece en SOCIEDADES.xlsx:

- el registro debe mantenerse
- sociedad_nombre debe quedar vacío o dejar el código original sin reemplazo ambiguo

### 6.4 Texto con varias referencias

Si el texto del documento contiene más de una nomenclatura, el diseño debe priorizar una regla clara y consistente. Para el modelo inicial, se recomienda detectar la primera coincidencia válida y marcar el registro para revisión si hay ambigüedad.

---

## 7. Preparación para futuras monedas

La solución debe ser completamente parametrizable para nuevas monedas.

### Reglas de escalabilidad para monedas

- la incorporación de nuevas monedas debe hacerse únicamente mediante el archivo MONEDA.xlsx
- no debe requerirse modificación de Python para soportarlas
- la validación debe basarse en el catálogo maestro y no en valores hardcodeados
- la matriz debe seguir funcionando aunque aparezcan monedas nuevas en futuros archivos de entrada

---

## 8. Preparación para nuevos conceptos

La solución debe ser completamente parametrizable para nuevos conceptos.

### Reglas de escalabilidad para conceptos

- la incorporación de nuevos conceptos debe hacerse únicamente mediante CONCEPTOS.xlsx
- no debe requerirse modificación de Python para soportarlos
- la detección debe basarse en el contenido del catálogo y no en reglas fijas dentro del código
- la matriz debe permitir identificar conceptos nuevos sin afectar el detalle de los registros

---

## 9. Preparación para nuevas sociedades

La solución debe ser completamente parametrizable para nuevas sociedades.

### Reglas de escalabilidad para sociedades

- la incorporación de nuevas sociedades debe hacerse únicamente mediante SOCIEDADES.xlsx
- no debe requerirse modificación de Python para soportarlas
- el enriquecimiento de sociedad debe basarse en el catálogo maestro
- la matriz debe seguir siendo válida aunque aumente el número de sociedades del negocio

---

## 10. Recomendación de uso para Excel y Power BI

La matriz debe ser la única fuente de verdad del proyecto.

### Para Excel

El libro debe consumir la matriz plana y limpia para:

- filtros
- análisis visual
- tablas dinámicas operativas
- revisión de conceptos no identificados

### Para Power BI

La matriz debe permitir:

- modelado en estrella
- segmentación por sociedad, moneda, concepto y período
- agregaciones sin alterar la tabla base
- ingreso de nuevas dimensiones sin duplicar lógica

---

## 11. Principios de diseño del modelo empresarial

La matriz final debe respetar los siguientes principios:

- una fila por transacción
- una única fuente de verdad
- preservación de datos originales
- normalización interna sin alterar el origen SAP
- parametrización por catálogos maestros
- escalabilidad para crecer sin cambios de código

---

## 12. Conclusión

La matriz empresarial v1 debe ser una tabla de detalle transaccional, limpia, enriquecida y preparada para análisis. Debe reemplazar las tablas dinámicas actuales, conservar la integridad del dato original y servir como base común para Excel, Power BI y futuras automatizaciones.
