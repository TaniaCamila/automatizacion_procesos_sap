from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ...config.config import Config
from ...config.logger import LoggerManager
from ...services.output_artifact_service import OutputArtifactService


logger = LoggerManager.get_logger(__name__)

ND = "N/D"


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y · %H:%M")


def _col(df, *names: str) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def map_system_status(
    output_service: OutputArtifactService,
    config: Config,
) -> list[dict]:
    """Construir ServiceStatus[] a partir de rutas y artefacto más reciente."""

    latest = output_service.latest()
    python_detail = "Motor de procesamiento disponible"
    python_health = "operational"

    if latest is None:
        excel_detail = "Sin archivos MATRIZ_FBL1N en data/output"
        excel_health = "offline"
    else:
        meta = output_service.file_metadata(latest)
        excel_detail = (
            f"Último Excel: {meta['name']} · {meta['modified_display']}"
        )
        excel_health = "operational"

    def path_status(path: Path, label: str) -> tuple[str, str]:
        if path.exists():
            return "operational", f"{label} disponible: {path.name}"
        return "offline", f"{label} no encontrado: {path}"

    fbl_health, fbl_detail = path_status(config.fbl1n_path, "FBL1N")
    soc_health, soc_detail = path_status(config.sociedades_path, "SOCIEDADES")
    mon_health, mon_detail = path_status(config.moneda_path, "MONEDA")
    con_health, con_detail = path_status(config.conceptos_path, "CONCEPTOS")

    catalogs_ok = all(
        h == "operational"
        for h in (soc_health, mon_health, con_health)
    )

    # Solo indica que existe un enlace de dashboard configurado.
    # No implica refresh automático, REST API ni sincronización.
    powerbi_configured = bool(str(config.mail_powerbi_link or "").strip())
    if powerbi_configured:
        powerbi_health = "operational"
        powerbi_detail = "Dashboard analítico disponible"
    else:
        powerbi_health = "not_configured"
        powerbi_detail = "Visualización analítica — pendiente"

    def _under_onedrive(path: Path) -> bool:
        return "onedrive" in str(path).lower()

    # Rutas de trabajo sincronizadas. No implica Graph/OneDrive API.
    onedrive_ready = any(
        path.exists() and _under_onedrive(path)
        for path in (
            config.input_dir,
            config.output_dir,
            config.publication_dir,
        )
    )
    if onedrive_ready:
        onedrive_health = "operational"
        onedrive_detail = "Sincronización de archivos disponible"
    else:
        onedrive_health = "not_configured"
        onedrive_detail = "Almacenamiento en la nube — pendiente"

    # Enlace y/o carpeta de publicación. No implica SharePoint API.
    sharepoint_configured = bool(
        str(config.mail_sharepoint_link or "").strip()
    )
    publication_ready = config.publication_dir.exists()
    if sharepoint_configured or publication_ready:
        sharepoint_health = "operational"
        sharepoint_detail = "Reporte Query Mensual disponible"
    else:
        sharepoint_health = "not_configured"
        sharepoint_detail = "Publicación corporativa — pendiente"

    # Destinatario configurado = capacidad de correo. MAIL_AUTO_SEND no
    # desactiva la configuración; solo el envío automático permanente.
    outlook_configured = bool(str(config.mail_to or "").strip())
    if outlook_configured:
        outlook_health = "operational"
        if config.mail_auto_send:
            outlook_detail = "Correo configurado · envío automático activo"
        else:
            outlook_detail = (
                "Correo configurado · envío automático desactivado"
            )
    else:
        outlook_health = "not_configured"
        outlook_detail = "Distribución por correo — pendiente"

    return [
        {
            "id": "sap",
            "name": "SAP",
            "health": "not_configured",
            "detail": "Integración directa pendiente · FBL1N vía archivo",
        },
        {
            "id": "python",
            "name": "Python",
            "health": python_health,
            "detail": python_detail,
        },
        {
            "id": "output",
            "name": "Excel salida",
            "health": excel_health,
            "detail": excel_detail,
        },
        {
            "id": "fbl1n",
            "name": "FBL1N",
            "health": fbl_health,
            "detail": fbl_detail,
        },
        {
            "id": "catalogs",
            "name": "Catálogos",
            "health": "operational" if catalogs_ok else "degraded",
            "detail": (
                f"{soc_detail}; {mon_detail}; {con_detail}"
            ),
        },
        {
            "id": "powerbi",
            "name": "Power BI",
            "health": powerbi_health,
            "detail": powerbi_detail,
        },
        {
            "id": "onedrive",
            "name": "OneDrive",
            "health": onedrive_health,
            "detail": onedrive_detail,
        },
        {
            "id": "sharepoint",
            "name": "SharePoint",
            "health": sharepoint_health,
            "detail": sharepoint_detail,
        },
        {
            "id": "outlook",
            "name": "Outlook",
            "health": outlook_health,
            "detail": outlook_detail,
        },
    ]
