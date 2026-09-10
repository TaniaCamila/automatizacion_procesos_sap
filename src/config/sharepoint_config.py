from __future__ import annotations

import os
from dataclasses import dataclass


REQUIRED_ENV_VARS: tuple[str, ...] = (
    "SHAREPOINT_SITE_URL",
    "SHAREPOINT_DOCUMENT_LIBRARY",
    "SHAREPOINT_TARGET_FOLDER",
    "SHAREPOINT_CLIENT_ID",
    "SHAREPOINT_TENANT_ID",
    "SHAREPOINT_CLIENT_SECRET",
)


@dataclass(frozen=True)
class SharePointConfig:
    """
    Configuración de SharePoint (BUSINESS-07).

    Todos los valores provienen de variables de entorno.
    No realiza conexiones de red.
    """

    SITE_URL: str
    DOCUMENT_LIBRARY: str
    TARGET_FOLDER: str
    CLIENT_ID: str
    TENANT_ID: str
    CLIENT_SECRET: str

    @classmethod
    def from_env(cls) -> SharePointConfig:
        """Construir configuración desde el entorno."""

        values = {
            "SITE_URL": os.getenv("SHAREPOINT_SITE_URL", "").strip(),
            "DOCUMENT_LIBRARY": os.getenv("SHAREPOINT_DOCUMENT_LIBRARY", "").strip(),
            "TARGET_FOLDER": os.getenv("SHAREPOINT_TARGET_FOLDER", "").strip(),
            "CLIENT_ID": os.getenv("SHAREPOINT_CLIENT_ID", "").strip(),
            "TENANT_ID": os.getenv("SHAREPOINT_TENANT_ID", "").strip(),
            "CLIENT_SECRET": os.getenv("SHAREPOINT_CLIENT_SECRET", "").strip(),
        }
        return cls(**values)

    def missing_fields(self) -> list[str]:
        """Listar nombres de atributos sin valor."""

        missing: list[str] = []
        for field_name in (
            "SITE_URL",
            "DOCUMENT_LIBRARY",
            "TARGET_FOLDER",
            "CLIENT_ID",
            "TENANT_ID",
            "CLIENT_SECRET",
        ):
            if not getattr(self, field_name):
                missing.append(field_name)
        return missing

    def is_configured(self) -> bool:
        """True si todas las variables requeridas están presentes."""

        return not self.missing_fields()

    def validate(self) -> None:
        """
        Validar que la configuración esté completa.

        Raises:
            ValueError: si falta alguna variable requerida.
        """

        missing = self.missing_fields()
        if missing:
            raise ValueError(
                "Configuración SharePoint incompleta. Faltan: "
                + ", ".join(missing)
            )


__all__ = (
    "REQUIRED_ENV_VARS",
    "SharePointConfig",
)
