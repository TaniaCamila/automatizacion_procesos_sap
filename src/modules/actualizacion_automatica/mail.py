"""Notificación por correo vía Outlook clásico (COM).

Display() vive solo en display_outlook_draft() (script visual).
Send() vive solo en send_outlook_mail(), invocada por run_mail_stage()
cuando MAIL_AUTO_SEND=true y authorized=True. Con MAIL_AUTO_SEND=false
el orquestador no abre Outlook, no crea MailItem y no envía.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

OL_MAIL_ITEM = 0
OL_TO = 1
OL_CC = 2
OL_BCC = 3


class OutlookAccountError(Exception):
    """No se pudo resolver/listar la cuenta de Outlook (COM/MAPI o config)."""


class MailSendError(Exception):
    """Fallo controlado antes o durante el envío real."""


@dataclass(frozen=True)
class MailPayload:
    """Contrato estable para la notificación."""

    to: str
    subject: str
    body: str
    attachment: Path | None = None
    powerbi_link: str | None = None
    sharepoint_link: str | None = None
    html_body: str | None = None
    cc: str = ""
    bcc: str = ""
    sender_account: str = ""
    latest_compensation_date: str | None = None


@dataclass(frozen=True)
class OutlookDraftInspection:
    """Propiedades leídas del MailItem antes/después de Display (sin Send)."""

    to: str
    cc: str
    bcc: str
    subject: str
    attachment_name: str
    attachment_path: str
    attachment_size: int
    recipient_count: int
    attachment_count: int
    body_has_powerbi_link: bool
    body_has_sharepoint_link: bool
    html_configured: bool
    outlook_classic: bool
    displayed: bool


def send_notification(
    payload: MailPayload,
    *,
    enabled: bool = False,
) -> None:
    """
    Registrar la notificación. No envía.

    enabled=False → solo log (orquestador).
    enabled=True  → no autorizado aún (no hay Send).
    """

    logger.info(
        "Placeholder correo (NO es la fuente de verdad; usar MAIL_TO/CC/BCC "
        "y run_mail_stage). enabled=%s to=%s subject=%s attachment=%s powerbi=%s",
        enabled,
        payload.to,
        payload.subject,
        payload.attachment,
        payload.powerbi_link,
    )
    logger.info("Cuerpo correo (no enviado):\n%s", payload.body)

    if enabled:
        raise NotImplementedError(
            "El envío real (.Send) aún no está autorizado."
        )


def _recipient_address(recipient: Any) -> str:
    for attr in ("Address", "Name"):
        value = str(getattr(recipient, attr, "") or "").strip()
        if value:
            return value
    return ""


def _bind_send_using_account(outlook: Any, mail: Any, smtp: str) -> Any:
    """Asignar SendUsingAccount por SmtpAddress. No envía."""

    wanted = (smtp or "").strip().lower()
    if not wanted:
        raise OutlookAccountError("No hay SmtpAddress para SendUsingAccount.")
    accounts = outlook.Session.Accounts
    for index in range(1, int(accounts.Count) + 1):
        item = accounts.Item(index)
        addr = str(getattr(item, "SmtpAddress", "") or "").strip()
        if addr.lower() == wanted:
            mail.SendUsingAccount = item
            return item
    raise OutlookAccountError(
        f"No se encontró la cuenta Outlook para SendUsingAccount: {smtp}"
    )


def display_outlook_draft(
    payload: MailPayload,
    *,
    expected_to: str,
    expected_attachment_name: str,
    expected_powerbi_link: str,
    expected_sharepoint_link: str = "",
    expected_subject: str = "",
) -> OutlookDraftInspection:
    """
    Crear un MailItem en Outlook clásico y mostrarlo con Display().

    No llama a Send(). No marca el correo como enviado.
    """

    if payload.to.strip() != expected_to:
        raise ValueError(
            f"Destinatario no autorizado: {payload.to!r} (esperado {expected_to!r})"
        )

    if payload.attachment is None:
        raise ValueError("Falta el adjunto.")
    attachment = payload.attachment.resolve()
    if not attachment.is_file():
        raise FileNotFoundError(f"Adjunto inexistente: {attachment}")
    if attachment.stat().st_size <= 0:
        raise ValueError(f"Adjunto vacío: {attachment}")
    if attachment.name != expected_attachment_name:
        raise ValueError(
            f"Adjunto no autorizado: {attachment.name!r} "
            f"(esperado {expected_attachment_name!r})"
        )

    link = (payload.powerbi_link or "").strip()
    if link != expected_powerbi_link:
        raise ValueError("El enlace de Power BI no coincide con el autorizado.")
    if expected_powerbi_link not in payload.body:
        raise ValueError("El cuerpo de texto no incluye el enlace de Power BI autorizado.")

    sharepoint = (payload.sharepoint_link or "").strip()
    if expected_sharepoint_link:
        if sharepoint != expected_sharepoint_link:
            raise ValueError("El enlace de SharePoint no coincide con el autorizado.")
        if expected_sharepoint_link not in payload.body:
            raise ValueError("El cuerpo de texto no incluye el enlace de SharePoint autorizado.")

    html = (payload.html_body or "").strip()
    if html:
        if expected_powerbi_link not in html:
            raise ValueError("El HTML no incluye el enlace de Power BI autorizado.")
        if expected_sharepoint_link and expected_sharepoint_link not in html:
            raise ValueError("El HTML no incluye el enlace de SharePoint autorizado.")

    if expected_subject and payload.subject != expected_subject:
        raise ValueError(
            f"Asunto inesperado: {payload.subject!r} (esperado {expected_subject!r})"
        )

    import win32com.client  # type: ignore

    outlook = win32com.client.Dispatch("Outlook.Application")
    name = str(getattr(outlook, "Name", "") or "")
    outlook_classic = "Outlook" in name

    mail = outlook.CreateItem(OL_MAIL_ITEM)
    sender_smtp = (payload.sender_account or "").strip()
    if sender_smtp:
        _bind_send_using_account(outlook, mail, sender_smtp)
    mail.To = expected_to
    mail.CC = (payload.cc or "").strip()
    mail.BCC = (payload.bcc or "").strip()
    mail.Subject = payload.subject
    mail.Body = payload.body
    if html:
        mail.HTMLBody = html
    mail.Attachments.Add(str(attachment))

    to_count = 0
    cc_count = 0
    bcc_count = 0
    recipients = mail.Recipients
    for i in range(1, int(recipients.Count) + 1):
        item = recipients.Item(i)
        kind = int(item.Type)
        if kind == OL_TO:
            to_count += 1
        elif kind == OL_CC:
            cc_count += 1
        elif kind == OL_BCC:
            bcc_count += 1

    to_text = str(mail.To or "").strip()
    cc_text = str(mail.CC or "").strip()
    bcc_text = str(mail.BCC or "").strip()
    attach_count = int(mail.Attachments.Count)

    if to_count != 1 or recipients.Count != 1:
        raise RuntimeError(
            f"Se esperaba 1 destinatario To; Recipients={recipients.Count} To={to_count}"
        )
    if expected_to.lower() not in to_text.lower() and expected_to.lower() not in _recipient_address(
        recipients.Item(1)
    ).lower():
        raise RuntimeError(f"Destinatario To inesperado: {to_text!r}")
    if cc_count != 0 or cc_text:
        expected_cc = (payload.cc or "").strip()
        if not expected_cc:
            raise RuntimeError(f"CC debe estar vacío; CC={cc_text!r}")
        if expected_cc.lower() not in cc_text.lower():
            raise RuntimeError(f"CC inesperado: {cc_text!r}")
    elif (payload.cc or "").strip():
        raise RuntimeError("CC configurado no quedó en el MailItem")
    if bcc_count != 0 or bcc_text:
        expected_bcc = (payload.bcc or "").strip()
        if not expected_bcc:
            raise RuntimeError(f"BCC debe estar vacío; BCC={bcc_text!r}")
        if expected_bcc.lower() not in bcc_text.lower():
            raise RuntimeError(f"BCC inesperado: {bcc_text!r}")
    elif (payload.bcc or "").strip():
        raise RuntimeError("BCC configurado no quedó en el MailItem")
    if attach_count != 1:
        raise RuntimeError(f"Se esperaba 1 adjunto; hay {attach_count}")
    attached_name = str(mail.Attachments.Item(1).FileName)
    if attached_name != expected_attachment_name:
        raise RuntimeError(f"Adjunto inesperado: {attached_name!r}")

    if expected_subject and str(mail.Subject or "") != expected_subject:
        raise RuntimeError(f"Asunto inesperado en MailItem: {mail.Subject!r}")

    html_text = str(getattr(mail, "HTMLBody", "") or "")
    body_text = str(mail.Body or "")
    combined = body_text + "\n" + html_text
    body_has_powerbi = expected_powerbi_link in combined
    body_has_sharepoint = (
        (not expected_sharepoint_link) or expected_sharepoint_link in combined
    )
    if not body_has_powerbi:
        raise RuntimeError("El MailItem no contiene el enlace de Power BI.")
    if expected_sharepoint_link and not body_has_sharepoint:
        raise RuntimeError("El MailItem no contiene el enlace de SharePoint.")
    html_configured = bool(html) and expected_powerbi_link in html_text

    inspection = OutlookDraftInspection(
        to=to_text or expected_to,
        cc=cc_text,
        bcc=bcc_text,
        subject=str(mail.Subject or ""),
        attachment_name=attached_name,
        attachment_path=str(attachment),
        attachment_size=int(attachment.stat().st_size),
        recipient_count=int(recipients.Count),
        attachment_count=attach_count,
        body_has_powerbi_link=body_has_powerbi,
        body_has_sharepoint_link=body_has_sharepoint,
        html_configured=html_configured,
        outlook_classic=outlook_classic,
        displayed=False,
    )
    logger.info(
        "Borrador Outlook validado to=%s attachments=%s size=%s send=NO",
        inspection.to,
        inspection.attachment_name,
        inspection.attachment_size,
    )

    mail.Display()
    return OutlookDraftInspection(
        to=inspection.to,
        cc=inspection.cc,
        bcc=inspection.bcc,
        subject=inspection.subject,
        attachment_name=inspection.attachment_name,
        attachment_path=inspection.attachment_path,
        attachment_size=inspection.attachment_size,
        recipient_count=inspection.recipient_count,
        attachment_count=inspection.attachment_count,
        body_has_powerbi_link=inspection.body_has_powerbi_link,
        body_has_sharepoint_link=inspection.body_has_sharepoint_link,
        html_configured=inspection.html_configured,
        outlook_classic=inspection.outlook_classic,
        displayed=True,
    )


# --- Estado, configuración y etapa de correo (sin .Send) ---

from ...config.config import (  # noqa: E402
    FBL1N_FUTURE_ENABLED,
    MAIL_AUTO_SEND,
    MAIL_BCC,
    MAIL_CC,
    MAIL_POWERBI_LINK,
    MAIL_SENDER_ACCOUNT,
    MAIL_SHAREPOINT_LINK,
    MAIL_TO,
    PUBLICATION_DIR,
    resolve_state_dir,
)
from ...modules.publicacion_final.module import (  # noqa: E402
    PUBLISH_SUCCEEDED,
    load_publish_state,
)

MAIL_STATE_FILENAME = "last_mail_state.json"
PIPELINE_STATE_FILENAME = "last_fbl1n_state.json"
MAIL_PENDING = "Pending"
MAIL_SUCCEEDED = "Succeeded"
MAIL_FAILED = "Failed"
MAIL_ATTACHMENT_NAME = "PAGO_MONEDA_EXTRANJERA.xlsx"


def _mail_state_path(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return resolve_state_dir() / MAIL_STATE_FILENAME


def _pipeline_state_path() -> Path:
    return resolve_state_dir() / PIPELINE_STATE_FILENAME


# Compatibilidad: valor al import. Las funciones operativas usan _mail_state_path().
MAIL_STATE_PATH = _mail_state_path()


@dataclass(frozen=True)
class OutlookAccountInfo:
    smtp: str
    display_name: str
    index: int


@dataclass
class MailStageResult:
    status: str
    skipped: bool = False
    executed: bool = False
    message: str = ""
    source_fbl1n_sha256: str = ""
    mail_to: str = ""
    mail_subject: str = ""
    sender_account: str = ""
    error: str = ""
    latest_compensation_date: str = ""


_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
COMPENSATION_BODY_PHRASE = (
    "Información actualizada hasta la fecha de compensación {visible}."
)
# Aviso temporal en el correo operativo (sin URL ni encabezado "Power BI:").
POWERBI_UPDATE_NOTICE = (
    "El Dashboard de Power BI se encuentra en proceso de actualización\n"
    "de formato y será enviado la próxima semana."
)


def _future_mail_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return bool(override)
    return bool(FBL1N_FUTURE_ENABLED)


def parse_iso_compensation_date(raw: str | None) -> str:
    """Validar YYYY-MM-DD. Sin fallback a fecha actual."""

    text = str(raw or "").strip()
    if not text:
        raise MailSendError(
            "latest_compensation_date ausente; no se construye el correo."
        )
    match = _ISO_DATE_RE.fullmatch(text)
    if match is None:
        raise MailSendError(
            "latest_compensation_date inválida; se exige YYYY-MM-DD."
        )
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise MailSendError(
            "latest_compensation_date inválida; no es una fecha calendario."
        ) from exc
    return parsed.isoformat()


def format_compensation_date_visible(raw: str | None) -> str:
    """YYYY-MM-DD → DD/MM/YYYY."""

    iso = parse_iso_compensation_date(raw)
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def mail_may_be_composed(
    *,
    future_enabled: bool,
    decision: str | None,
    publish_ok: bool,
) -> bool:
    """El payload futuro solo se construye con Changed + publicación OK."""

    if not future_enabled:
        return True
    if not publish_ok:
        return False
    return str(decision or "") == "Changed"


def pipeline_mail_hash(
    payload: dict[str, Any],
    *,
    future_enabled: bool | None = None,
) -> str:
    """Hash que el correo debe contrastar con el state del pipeline."""

    if _future_mail_enabled(future_enabled):
        return str(
            payload.get("source_fbl1n_sha256")
            or payload.get("combined_source_sha256")
            or ""
        )
    return str(payload.get("sha256") or "")


def parse_address_list(raw: str) -> list[str]:
    items: list[str] = []
    for chunk in str(raw or "").replace(",", ";").split(";"):
        text = chunk.strip()
        if text:
            items.append(text)
    return items


def join_addresses(values: list[str]) -> str:
    return "; ".join(values)


def period_label_from_months(months: list[str]) -> tuple[str, str]:
    cleaned = [str(item).strip() for item in months if str(item).strip()]
    if not cleaned:
        raise ValueError("No hay months para determinar el período del correo.")
    period = max(cleaned)
    from ...modules.margen.module import InformeMargenModule

    label = InformeMargenModule._month_label_from_period(period)
    if not label or label == "Total":
        raise ValueError(f"No se pudo mapear el período {period!r} a un mes.")
    return period, f"{label}-{period[:4]}"


def _visual_period_label(period_label: str) -> str:
    """Agosto-2026 → Agosto 2026. El período sigue viniendo de months."""
    text = str(period_label or "").strip()
    if "-" in text:
        month, year = text.rsplit("-", 1)
        return f"{month.strip()} {year.strip()}"
    return text


def build_mail_subject(
    period_label: str,
    *,
    latest_compensation_date: str | None = None,
    future_enabled: bool | None = None,
) -> str:
    if _future_mail_enabled(future_enabled):
        visible = format_compensation_date_visible(latest_compensation_date)
        return (
            "Detalle Pagos_Resumen en CLP y USD - "
            f"Fecha de pago al {visible}"
        )
    return (
        "Detalle Pagos_Resumen en CLP y USD - "
        f"{_visual_period_label(period_label)}"
    )


def build_mail_plain_body(
    period_label: str,
    *,
    sharepoint: str,
    powerbi: str,
    latest_compensation_date: str | None = None,
    future_enabled: bool | None = None,
) -> str:
    # powerbi conservado en la firma por compatibilidad; no se inserta.
    _ = powerbi
    if _future_mail_enabled(future_enabled):
        visible = format_compensation_date_visible(latest_compensation_date)
        intro = (
            "Junto con saludar, se encuentra disponible el Detalle de Pagos_Resumen "
            "en CLP y USD, elaborado a partir de la "
            "información extraída desde SAP mediante la transacción FBL1N.\n"
            "\n"
            f"{COMPENSATION_BODY_PHRASE.format(visible=visible)}\n"
        )
    else:
        visual = _visual_period_label(period_label)
        intro = (
            "Junto con saludar, se encuentra disponible el Detalle de Pagos_Resumen "
            f"en CLP y USD correspondiente a {visual}, elaborado a partir de la "
            "información extraída desde SAP mediante la transacción FBL1N.\n"
        )
    return (
        "Estimados,\n"
        "\n"
        "Buenas tardes,\n"
        "\n"
        f"{intro}"
        "\n"
        "Asimismo, se encuentran disponibles en el Reporte Query Mensual los "
        "archivos actualizados correspondientes al proceso:\n"
        "\n"
        "• DINAMICAS_FINALES_ACTUAL\n"
        "• PROVEEDORES\n"
        "• PAGO_MONEDA_EXTRANJERA\n"
        "\n"
        "Reporte Query Mensual:\n"
        f"{sharepoint}\n"
        "\n"
        f"{POWERBI_UPDATE_NOTICE}\n"
        "\n"
        "Se adjunta el archivo PAGO_MONEDA_EXTRANJERA.xlsx correspondiente al "
        "proceso.\n"
        "\n"
        "Saludos.\n"
    )


def build_mail_html_body(
    period_label: str,
    *,
    sharepoint: str,
    powerbi: str,
    latest_compensation_date: str | None = None,
    future_enabled: bool | None = None,
) -> str:
    # powerbi conservado en la firma por compatibilidad; no se inserta.
    _ = powerbi
    if _future_mail_enabled(future_enabled):
        visible = format_compensation_date_visible(latest_compensation_date)
        intro = (
            "<p>Junto con saludar, se encuentra disponible el Detalle de Pagos_Resumen "
            "en CLP y USD, elaborado a partir de la "
            "información extraída desde SAP mediante la transacción FBL1N.</p>"
            f"<p>{COMPENSATION_BODY_PHRASE.format(visible=visible)}</p>"
        )
    else:
        visual = _visual_period_label(period_label)
        intro = (
            "<p>Junto con saludar, se encuentra disponible el Detalle de Pagos_Resumen "
            f"en CLP y USD correspondiente a {visual}, elaborado a partir de la "
            "información extraída desde SAP mediante la transacción FBL1N.</p>"
        )
    return (
        "<html><body style=\"font-family:Calibri,Arial,sans-serif;font-size:11pt;\">"
        "<p>Estimados,</p>"
        "<p>Buenas tardes,</p>"
        f"{intro}"
        "<p>Asimismo, se encuentran disponibles en el Reporte Query Mensual los "
        "archivos actualizados correspondientes al proceso:</p>"
        "<ul>"
        "<li>DINAMICAS_FINALES_ACTUAL</li>"
        "<li>PROVEEDORES</li>"
        "<li>PAGO_MONEDA_EXTRANJERA</li>"
        "</ul>"
        "<p>Reporte Query Mensual:<br>"
        f'<a href="{sharepoint}">Ver Reporte Query Mensual</a></p>'
        "<p>"
        + POWERBI_UPDATE_NOTICE.replace("\n", "<br>")
        + "</p>"
        "<p>Se adjunta el archivo PAGO_MONEDA_EXTRANJERA.xlsx correspondiente al "
        "proceso.</p>"
        "<p>Saludos.</p>"
        "</body></html>"
    )


def compose_mail_payload(
    *,
    to: str,
    sharepoint: str,
    powerbi: str,
    period_label: str = "",
    cc: str = "",
    bcc: str = "",
    sender_account: str = "",
    attachment: Path | None = None,
    latest_compensation_date: str | None = None,
    future_enabled: bool | None = None,
) -> MailPayload:
    """Construir payload en memoria. No abre Outlook."""

    enabled = _future_mail_enabled(future_enabled)
    iso_date = None
    if enabled:
        iso_date = parse_iso_compensation_date(latest_compensation_date)
    subject = build_mail_subject(
        period_label,
        latest_compensation_date=iso_date,
        future_enabled=enabled,
    )
    # MAIL_POWERBI_LINK / argumento powerbi no se insertan en este correo.
    _ = powerbi
    return MailPayload(
        to=to,
        subject=subject,
        body=build_mail_plain_body(
            period_label,
            sharepoint=sharepoint,
            powerbi="",
            latest_compensation_date=iso_date,
            future_enabled=enabled,
        ),
        attachment=attachment,
        powerbi_link=None,
        sharepoint_link=sharepoint,
        html_body=build_mail_html_body(
            period_label,
            sharepoint=sharepoint,
            powerbi="",
            latest_compensation_date=iso_date,
            future_enabled=enabled,
        ),
        cc=cc,
        bcc=bcc,
        sender_account=sender_account,
        latest_compensation_date=iso_date,
    )


def months_from_pipeline_state() -> list[str]:
    path = _pipeline_state_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [str(item).strip() for item in (payload.get("months") or []) if str(item).strip()]


def published_pago_me_path() -> Path:
    return PUBLICATION_DIR / MAIL_ATTACHMENT_NAME


def load_mail_state(path: Path | None = None) -> dict[str, Any] | None:
    target = _mail_state_path(path)
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_mail_state(payload: dict[str, Any], path: Path | None = None) -> None:
    target = _mail_state_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def needs_mail_retry(fbl1n_sha256: str, path: Path | None = None) -> bool:
    """True si no hay envío Succeeded vinculado a este hash."""

    state = load_mail_state(path)
    if state is None:
        return True
    stored = str(state.get("source_fbl1n_sha256") or "")
    if stored != str(fbl1n_sha256 or ""):
        return True
    return str(state.get("mail_status") or "") != MAIL_SUCCEEDED


def _cfg() -> Any:
    from ...config import config as config_mod

    return config_mod


def write_mail_state(
    *,
    sha256: str,
    status: str,
    subject: str,
    sender: str = "",
    error: str | None = None,
    logger: logging.Logger,
    latest_compensation_date: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    cfg = _cfg()
    payload = {
        "source_fbl1n_sha256": sha256,
        "mail_status": status,
        "mail_at": datetime.now().isoformat(timespec="seconds"),
        "mail_to": cfg.MAIL_TO,
        "mail_cc": cfg.MAIL_CC,
        "mail_bcc": cfg.MAIL_BCC,
        "mail_subject": subject,
        "mail_sender_account": sender,
        "mail_error": error,
    }
    if latest_compensation_date:
        payload["latest_compensation_date"] = parse_iso_compensation_date(
            latest_compensation_date
        )
    target = _mail_state_path(path)
    save_mail_state(payload, target)
    logger.info(
        "Estado correo guardado status=%s hash=%s auto_send=%s error=%s",
        status,
        sha256,
        cfg.MAIL_AUTO_SEND,
        error or "(ninguno)",
    )
    return payload


def pipeline_allows_mail(
    sha256: str,
    *,
    pipeline_state: dict[str, Any] | None = None,
    future_enabled: bool | None = None,
) -> None:
    if pipeline_state is None:
        path = _pipeline_state_path()
        if not path.is_file():
            raise MailSendError("last_fbl1n_state.json ausente; pipeline no OK.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MailSendError(
                f"No se pudo leer last_fbl1n_state.json: {exc}"
            ) from exc
    else:
        payload = pipeline_state
    stored = pipeline_mail_hash(payload, future_enabled=future_enabled)
    if stored != str(sha256 or ""):
        raise MailSendError(
            "El hash de last_fbl1n_state.json no coincide con el hash actual."
        )
    if not str(payload.get("last_success_at") or "").strip():
        raise MailSendError("El pipeline técnico no tiene last_success_at.")


def publication_allows_mail(sha256: str) -> None:
    state = load_publish_state()
    if state is None:
        raise MailSendError("last_publish_state.json ausente.")
    status = str(state.get("publish_status") or "")
    if status != PUBLISH_SUCCEEDED:
        raise MailSendError(f"Publicación no Succeeded (status={status or 'ausente'}).")
    stored = str(state.get("source_fbl1n_sha256") or "")
    if stored != str(sha256 or ""):
        raise MailSendError(
            "source_fbl1n_sha256 de publicación no coincide con el hash actual."
        )


def validate_mail_attachment(path: Path | None) -> Path:
    expected = published_pago_me_path().resolve()
    if path is None:
        raise MailSendError("Falta el adjunto PAGO_MONEDA_EXTRANJERA.xlsx.")
    attachment = path.resolve()
    if os.path.normcase(str(attachment)) != os.path.normcase(str(expected)):
        raise MailSendError(
            f"Adjunto no autorizado: {attachment} (esperado {expected})"
        )
    if not attachment.is_file():
        raise MailSendError(f"Adjunto inexistente: {attachment}")
    if attachment.stat().st_size <= 0:
        raise MailSendError(f"Adjunto vacío: {attachment}")
    if attachment.name != MAIL_ATTACHMENT_NAME:
        raise MailSendError(
            f"Adjunto no autorizado: {attachment.name!r} "
            f"(esperado {MAIL_ATTACHMENT_NAME!r})"
        )
    return attachment


def list_outlook_accounts() -> list[OutlookAccountInfo]:
    """Listar cuentas Outlook. No envía. No abre MailItem."""

    try:
        import win32com.client  # type: ignore

        outlook = win32com.client.Dispatch("Outlook.Application")
        accounts = outlook.Session.Accounts
        found: list[OutlookAccountInfo] = []
        for index in range(1, int(accounts.Count) + 1):
            account = accounts.Item(index)
            smtp = str(getattr(account, "SmtpAddress", "") or "").strip()
            display = str(getattr(account, "DisplayName", "") or "").strip()
            found.append(
                OutlookAccountInfo(smtp=smtp, display_name=display, index=index)
            )
        return found
    except Exception as exc:
        raise OutlookAccountError(
            f"No se pudieron consultar cuentas Outlook (COM/MAPI): {exc}"
        ) from exc


def resolve_outlook_sender(configured: str | None = None) -> OutlookAccountInfo:
    """
    Resolver cuenta remitente. Sin fallback silencioso entre varias cuentas.
    No envía.
    """

    wanted = (
        configured if configured is not None else _cfg().MAIL_SENDER_ACCOUNT
    ).strip()
    accounts = list_outlook_accounts()
    valid = [item for item in accounts if item.smtp]
    if wanted:
        needle = wanted.lower()
        for item in valid:
            if item.smtp.lower() == needle:
                return item
        raise OutlookAccountError(
            f"MAIL_SENDER_ACCOUNT no está disponible en Outlook: {wanted}"
        )
    if len(valid) == 1:
        return valid[0]
    if not valid:
        raise OutlookAccountError("Outlook no expuso ninguna cuenta con SmtpAddress.")
    names = ", ".join(item.smtp for item in valid)
    raise OutlookAccountError(
        "Hay varias cuentas Outlook; configure MAIL_SENDER_ACCOUNT. "
        f"Cuentas: {names}"
    )


def send_outlook_mail(payload: MailPayload, *, authorized: bool) -> None:
    """
    Envío real vía Outlook COM.

    No llama Display(). Ejecuta MailItem.Send() únicamente si:
    authorized=True y MAIL_AUTO_SEND=true.
    """

    cfg = _cfg()
    if not authorized:
        raise MailSendError("send_outlook_mail no está autorizado.")
    if not cfg.MAIL_AUTO_SEND:
        raise MailSendError("MAIL_AUTO_SEND=false; Send bloqueado.")

    recipients_to = parse_address_list(payload.to)
    if not recipients_to:
        raise MailSendError("MAIL_TO no contiene destinatarios.")
    sharepoint = (payload.sharepoint_link or "").strip()
    html = (payload.html_body or "").strip()
    if not sharepoint or sharepoint != str(cfg.MAIL_SHAREPOINT_LINK or "").strip():
        raise MailSendError("MAIL_SHAREPOINT_LINK inválido o no coincide con .env.")
    if not html:
        raise MailSendError("Falta HTMLBody del correo.")
    if sharepoint not in html:
        raise MailSendError("El HTML no incluye el vínculo de SharePoint configurado.")
    if sharepoint not in payload.body:
        raise MailSendError(
            "El cuerpo de texto no incluye el vínculo de SharePoint configurado."
        )
    if POWERBI_UPDATE_NOTICE not in payload.body:
        raise MailSendError("El cuerpo de texto no incluye el aviso de Power BI.")
    if POWERBI_UPDATE_NOTICE.replace("\n", "<br>") not in html:
        raise MailSendError("El HTML no incluye el aviso de Power BI.")
    attachment = validate_mail_attachment(payload.attachment)
    sender_smtp = (payload.sender_account or "").strip()
    if not sender_smtp:
        raise MailSendError("Remitente vacío; no se asigna SendUsingAccount.")

    import win32com.client  # type: ignore

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(OL_MAIL_ITEM)
    try:
        _bind_send_using_account(outlook, mail, sender_smtp)
        mail.To = join_addresses(recipients_to)
        mail.CC = join_addresses(parse_address_list(payload.cc))
        mail.BCC = join_addresses(parse_address_list(payload.bcc))
        mail.Subject = payload.subject
        mail.Body = payload.body
        mail.HTMLBody = html
        mail.Attachments.Add(str(attachment))

        attach_count = int(mail.Attachments.Count)
        if attach_count != 1:
            raise MailSendError(f"Se esperaba 1 adjunto; hay {attach_count}")
        attached_name = str(mail.Attachments.Item(1).FileName)
        if attached_name != MAIL_ATTACHMENT_NAME:
            raise MailSendError(f"Adjunto inesperado: {attached_name!r}")
        if not str(mail.To or "").strip():
            raise MailSendError("MailItem.To quedó vacío.")
        logger.info(
            "MailItem listo para envío to=%s cc=%s bcc=%s sender=%s "
            "attachment=%s send_authorized=True auto_send=True",
            mail.To,
            mail.CC,
            mail.BCC,
            sender_smtp,
            attached_name,
        )
        if (not authorized) or (not _cfg().MAIL_AUTO_SEND):
            raise MailSendError("Candado final: Send bloqueado.")
        mail.Send()
    except Exception:
        try:
            mail.Delete()
        except Exception:
            pass
        raise
    logger.info("MailItem.Send() ejecutado sin excepción COM. send=SI")


def run_mail_stage(
    source_fbl1n_sha256: str,
    logger: logging.Logger,
    *,
    months: list[str] | None = None,
    latest_compensation_date: str | None = None,
    future_enabled: bool | None = None,
    decision: str | None = None,
    publish_ok: bool = True,
    mail_state_path: Path | None = None,
    compose_only: bool = False,
) -> MailStageResult:
    """
    Etapa de correo del orquestador.

    MAIL_AUTO_SEND=false: no Outlook, no Display, no Send; queda Pending.
    MAIL_AUTO_SEND=true: send_outlook_mail(authorized=True).
    compose_only=True: construye payload en memoria y no instancia Outlook.
    """

    cfg = _cfg()
    sha = str(source_fbl1n_sha256 or "").strip()
    enabled = _future_mail_enabled(future_enabled)
    state_path = _mail_state_path(mail_state_path)
    result = MailStageResult(status=MAIL_PENDING, source_fbl1n_sha256=sha)
    if not sha:
        raise ValueError("source_fbl1n_sha256 vacío; no se evalúa el correo.")

    if enabled and not mail_may_be_composed(
        future_enabled=True,
        decision=decision,
        publish_ok=publish_ok,
    ):
        result.skipped = True
        result.status = MAIL_PENDING
        result.message = (
            f"Correo no aplica (decisión={decision or '-'}, "
            f"publicación_ok={publish_ok})."
        )
        logger.info("%s", result.message)
        return result

    iso_date: str | None = None
    period_label = ""
    if enabled:
        iso_date = parse_iso_compensation_date(latest_compensation_date)
        result.latest_compensation_date = iso_date
        subject = build_mail_subject(
            "",
            latest_compensation_date=iso_date,
            future_enabled=True,
        )
    else:
        month_list = list(months or [])
        if not month_list:
            month_list = months_from_pipeline_state()
        _period, period_label = period_label_from_months(month_list)
        subject = build_mail_subject(period_label, future_enabled=False)
    result.mail_subject = subject
    result.mail_to = cfg.MAIL_TO

    if not needs_mail_retry(sha, state_path):
        logger.info("Correo ya enviado para este hash. Skip.")
        result.status = MAIL_SUCCEEDED
        result.skipped = True
        result.message = "Correo ya enviado para este hash. Skip."
        return result

    write_mail_state(
        sha256=sha,
        status=MAIL_PENDING,
        subject=subject,
        error=None,
        logger=logger,
        latest_compensation_date=iso_date,
        path=state_path,
    )

    if compose_only:
        payload = compose_mail_payload(
            to="preview@example.test",
            sharepoint="https://example.test/sharepoint",
            powerbi="",
            period_label=period_label,
            latest_compensation_date=iso_date,
            future_enabled=enabled,
        )
        result.status = MAIL_PENDING
        result.message = "payload construido (compose_only; sin Outlook)"
        result.mail_subject = payload.subject
        logger.info("compose_only: payload listo subject=%s", payload.subject)
        return result

    if not cfg.MAIL_AUTO_SEND:
        logger.info(
            "Correo pendiente/no ejecutado: MAIL_AUTO_SEND=false. "
            "No se abre Outlook, no Display, no Send."
        )
        result.status = MAIL_PENDING
        result.message = "Correo pendiente/no ejecutado: MAIL_AUTO_SEND=false"
        return result

    sender = ""
    try:
        pipeline_allows_mail(sha, future_enabled=enabled)
        publication_allows_mail(sha)
        if not parse_address_list(cfg.MAIL_TO):
            raise MailSendError("MAIL_TO no contiene destinatarios.")
        if not str(cfg.MAIL_SHAREPOINT_LINK or "").strip():
            raise MailSendError("MAIL_SHAREPOINT_LINK está vacío.")
        # MAIL_POWERBI_LINK no se usa en este correo (aviso temporal).
        attachment = validate_mail_attachment(published_pago_me_path())
        resolved = resolve_outlook_sender()
        sender = resolved.smtp
        result.sender_account = sender
        payload = compose_mail_payload(
            to=cfg.MAIL_TO,
            sharepoint=cfg.MAIL_SHAREPOINT_LINK,
            powerbi="",
            period_label=period_label,
            cc=cfg.MAIL_CC,
            bcc=cfg.MAIL_BCC,
            sender_account=sender,
            attachment=attachment,
            latest_compensation_date=iso_date,
            future_enabled=enabled,
        )
        send_outlook_mail(payload, authorized=True)
    except Exception as exc:
        error_text = str(exc)
        logger.error("Correo Failed: %s", error_text)
        write_mail_state(
            sha256=sha,
            status=MAIL_FAILED,
            subject=subject,
            sender=sender,
            error=error_text,
            logger=logger,
            latest_compensation_date=iso_date,
            path=state_path,
        )
        result.status = MAIL_FAILED
        result.message = error_text
        result.error = error_text
        result.sender_account = sender
        return result

    write_mail_state(
        sha256=sha,
        status=MAIL_SUCCEEDED,
        subject=subject,
        sender=sender,
        error=None,
        logger=logger,
        latest_compensation_date=iso_date,
        path=state_path,
    )
    result.status = MAIL_SUCCEEDED
    result.executed = True
    result.sender_account = sender
    result.message = "correo enviado"
    logger.info("Correo Succeeded para hash %s sender=%s", sha, sender)
    return result
