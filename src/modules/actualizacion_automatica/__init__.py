"""Orquestación end-to-end del pipeline FBL1N (sin cambiar reglas de negocio)."""

from .mail import MailPayload, display_outlook_draft, send_notification
from .module import run_actualizacion

__all__ = (
    "MailPayload",
    "display_outlook_draft",
    "run_actualizacion",
    "send_notification",
)
