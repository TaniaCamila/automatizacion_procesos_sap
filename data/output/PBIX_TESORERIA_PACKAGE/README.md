# PBIX Tesorería — Paquete EF-08 (especificación académica)

**Dashboard de referencia:** Dashboard Tesorería — Pagos Moneda Extranjera (FBL1N)

**Alcance en este repositorio:** únicamente **especificación, estructura y material de referencia** para un futuro dashboard Power BI.

## Qué NO se incluye en el repositorio académico

- Archivos `.pbix` finales.
- `MODELO_POWERBI.xlsx` u otros libros Excel de modelo.
- Logos corporativos u otros assets gráficos de marca.
- Fórmulas DAX implementadas en un PBIX publicado.
- Datos productivos o rutas de despliegue empresariales.

Esos elementos deben obtenerse o generarse **solo** con recursos autorizados por la organización de despliegue, fuera de este repositorio.

## Contenido versionado (referencia)

| Carpeta | Contenido |
|---|---|
| `tema/` | Tema JSON de ejemplo (sin marca corporativa) |
| `recursos/` | Notas de referencia (sin logos incluidos) |
| `docs/` | Spec EF-07 + guía EF-08 + metadatos de portada |
| `paginas/` | Organización de páginas P00–P07 |
| `medidas/` | Estructura/catálogo de medidas (sin DAX embebido) |
| `modelo/` | Relaciones documentadas (sin archivo Excel de modelo) |
| `checklist/` | Checklist de construcción del PBIX |

## Uso recomendado

1. Tratar este directorio como **guía de diseño y checklist**, no como paquete listo para abrir en Power BI Desktop con todos los binarios.
2. En un entorno autorizado, la organización de despliegue provee datos, logos y el archivo de modelo permitidos.
3. Power BI permanece **en ajustes** respecto a la automatización diaria del Capstone; no forma parte del flujo cerrado de `scripts/run_diario.py`.
