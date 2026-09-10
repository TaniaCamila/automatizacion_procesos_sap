"""Fecha de compensación dinámica en el correo (sin Outlook)."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.config.config import FBL1N_FUTURE_ENABLED
from src.modules.actualizacion_automatica.mail import (
    COMPENSATION_BODY_PHRASE,
    MAIL_SUCCEEDED,
    MailSendError,
    POWERBI_UPDATE_NOTICE,
    build_mail_html_body,
    build_mail_plain_body,
    build_mail_subject,
    compose_mail_payload,
    format_compensation_date_visible,
    mail_may_be_composed,
    needs_mail_retry,
    parse_iso_compensation_date,
    pipeline_allows_mail,
    pipeline_mail_hash,
    run_mail_stage,
    write_mail_state,
)

ROOT = Path(__file__).resolve().parents[1]
PROD_MAIL_STATE = ROOT / "state" / "last_mail_state.json"
PROD_PIPELINE_STATE = ROOT / "state" / "last_fbl1n_state.json"
PREVIEW_PATH = (
    ROOT / "temp" / "auditoria_dos_fbl1n_20260827_20260827_173610" / "d5_mail_preview.json"
)

FAKE_TO = "destinatario@example.test"
FAKE_CC = "copia@example.test"
FAKE_BCC = "oculto@example.test"
FAKE_SENDER = "remitente@example.test"
FAKE_SP = "https://example.test/sharepoint"
FAKE_PBI = "https://example.test/powerbi"
PERIOD = "Agosto-2026"
LEGACY_SUBJECT = "Detalle Pagos_Resumen en CLP y USD - Agosto 2026"
FUTURE_SUBJECT = (
    "Detalle Pagos_Resumen en CLP y USD - Fecha de pago al 02/09/2026"
)
CUTOFF_SUBJECT = (
    "Detalle Pagos_Resumen en CLP y USD - Fecha de pago al 31/08/2026"
)
FUTURE_PHRASE = "Información actualizada hasta la fecha de compensación 02/09/2026."


def _mtime(path: Path) -> int | None:
    if not path.is_file():
        return None
    return int(path.stat().st_mtime_ns)


class CompensationDateFormatTests(unittest.TestCase):
    def test_flag_off_subject_unchanged(self) -> None:
        self.assertEqual(
            build_mail_subject(PERIOD, future_enabled=False),
            LEGACY_SUBJECT,
        )

    def test_flag_off_body_unchanged(self) -> None:
        body = build_mail_plain_body(
            PERIOD,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            future_enabled=False,
        )
        self.assertIn("correspondiente a Agosto 2026", body)
        self.assertNotIn("Fecha de compensación", body)
        html = build_mail_html_body(
            PERIOD,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            future_enabled=False,
        )
        self.assertIn("correspondiente a Agosto 2026", html)

    def test_flag_on_2026_09_02_subject(self) -> None:
        self.assertEqual(
            build_mail_subject(
                PERIOD,
                latest_compensation_date="2026-09-02",
                future_enabled=True,
            ),
            FUTURE_SUBJECT,
        )

    def test_flag_on_2026_08_31_subject_exact(self) -> None:
        self.assertEqual(
            build_mail_subject(
                PERIOD,
                latest_compensation_date="2026-08-31",
                future_enabled=True,
            ),
            CUTOFF_SUBJECT,
        )
        self.assertEqual(
            CUTOFF_SUBJECT,
            "Detalle Pagos_Resumen en CLP y USD - Fecha de pago al 31/08/2026",
        )

    def test_visible_format_dd_mm_yyyy(self) -> None:
        self.assertEqual(format_compensation_date_visible("2026-09-02"), "02/09/2026")

    def test_october_eighth(self) -> None:
        self.assertEqual(format_compensation_date_visible("2026-10-08"), "08/10/2026")
        self.assertIn(
            "08/10/2026",
            build_mail_subject(
                PERIOD,
                latest_compensation_date="2026-10-08",
                future_enabled=True,
            ),
        )

    def test_year_change(self) -> None:
        self.assertEqual(format_compensation_date_visible("2025-12-31"), "31/12/2025")
        self.assertEqual(format_compensation_date_visible("2027-01-01"), "01/01/2027")

    def test_missing_date_fail_closed(self) -> None:
        with self.assertRaises(MailSendError):
            parse_iso_compensation_date(None)
        with self.assertRaises(MailSendError):
            build_mail_subject(PERIOD, future_enabled=True)

    def test_invalid_date_fail_closed(self) -> None:
        for raw in ("02/09/2026", "2026/09/02", "2026-13-01", "septiembre", "2026-09-31"):
            with self.subTest(raw=raw):
                with self.assertRaises(MailSendError):
                    parse_iso_compensation_date(raw)

    def test_no_fallback_to_today(self) -> None:
        today = date.today().strftime("%d/%m/%Y")
        visible = format_compensation_date_visible("2026-09-02")
        self.assertEqual(visible, "02/09/2026")
        self.assertNotEqual(visible, today)
        body = build_mail_plain_body(
            PERIOD,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        self.assertIn("02/09/2026", body)
        self.assertNotIn(today, body)

    def test_plain_and_html_contain_phrase(self) -> None:
        payload = compose_mail_payload(
            to=FAKE_TO,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            period_label=PERIOD,
            cc=FAKE_CC,
            bcc=FAKE_BCC,
            sender_account=FAKE_SENDER,
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        self.assertIn(FUTURE_PHRASE, payload.body)
        self.assertIn(FUTURE_PHRASE, payload.html_body or "")
        self.assertEqual(
            COMPENSATION_BODY_PHRASE.format(visible="02/09/2026"),
            FUTURE_PHRASE,
        )

    def test_no_cierre_septiembre(self) -> None:
        payload = compose_mail_payload(
            to=FAKE_TO,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        blob = payload.body + (payload.html_body or "") + payload.subject
        self.assertNotIn("Cierre de septiembre", blob)
        self.assertNotIn("Septiembre 2026", blob)
        self.assertNotIn("correspondiente a Agosto", blob)
        self.assertNotIn("correspondiente a Septiembre", blob)

    def test_links_and_attachment_name_remain(self) -> None:
        payload = compose_mail_payload(
            to=FAKE_TO,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            attachment=Path("PAGO_MONEDA_EXTRANJERA.xlsx"),
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        self.assertIn(FAKE_SP, payload.body)
        self.assertIn(FAKE_SP, payload.html_body or "")
        self.assertIn(POWERBI_UPDATE_NOTICE, payload.body)
        self.assertNotIn(FAKE_PBI, payload.body)
        self.assertNotIn(FAKE_PBI, payload.html_body or "")
        self.assertIsNone(payload.powerbi_link)
        self.assertEqual(payload.attachment.name, "PAGO_MONEDA_EXTRANJERA.xlsx")

    def test_recipients_and_sender_unchanged(self) -> None:
        payload = compose_mail_payload(
            to=FAKE_TO,
            cc=FAKE_CC,
            bcc=FAKE_BCC,
            sender_account=FAKE_SENDER,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        self.assertEqual(payload.to, FAKE_TO)
        self.assertEqual(payload.cc, FAKE_CC)
        self.assertEqual(payload.bcc, FAKE_BCC)
        self.assertEqual(payload.sender_account, FAKE_SENDER)


class PowerBiUpdateNoticeTests(unittest.TestCase):
    """P8D: aviso temporal en lugar de enlace Power BI (sin Outlook)."""

    def _assert_no_powerbi_url(self, blob: str) -> None:
        self.assertNotIn("Ver Dashboard Power BI", blob)
        self.assertNotIn("Power BI:", blob)
        self.assertNotIn(FAKE_PBI, blob)
        lowered = blob.lower()
        self.assertNotIn("powerbi.com", lowered)
        self.assertNotIn("/powerbi", lowered)
        self.assertNotIn('href="https://example.test/powerbi"', blob)

    def test_agosto_plain_and_html_notice(self) -> None:
        payload = compose_mail_payload(
            to=FAKE_TO,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            period_label=PERIOD,
            attachment=Path("PAGO_MONEDA_EXTRANJERA.xlsx"),
            future_enabled=False,
        )
        self.assertEqual(payload.subject, LEGACY_SUBJECT)
        self.assertIn(POWERBI_UPDATE_NOTICE, payload.body)
        html = payload.html_body or ""
        self.assertIn(POWERBI_UPDATE_NOTICE.replace("\n", "<br>"), html)
        self.assertIn(FAKE_SP, payload.body)
        self.assertIn(FAKE_SP, html)
        self.assertIn("Ver Reporte Query Mensual", html)
        self.assertIn("PAGO_MONEDA_EXTRANJERA.xlsx", payload.body)
        self.assertEqual(payload.attachment.name, "PAGO_MONEDA_EXTRANJERA.xlsx")
        self.assertIsNone(payload.powerbi_link)
        self._assert_no_powerbi_url(payload.body + "\n" + html)

    def test_powerbi_arg_ignored_even_if_configured(self) -> None:
        body = build_mail_plain_body(
            PERIOD,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            future_enabled=False,
        )
        html = build_mail_html_body(
            PERIOD,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            future_enabled=False,
        )
        self.assertIn(POWERBI_UPDATE_NOTICE, body)
        self.assertNotIn(FAKE_PBI, body)
        self.assertNotIn(FAKE_PBI, html)
        self.assertNotIn("Ver Dashboard Power BI", html)
        self.assertNotIn("Power BI:", body)
        self.assertNotIn("Power BI:", html)

    def test_compose_only_does_not_send(self) -> None:
        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("Outlook/Send no debe ejecutarse en P8D")

        with (
            patch(
                "src.modules.actualizacion_automatica.mail.send_outlook_mail",
                side_effect=_boom,
            ),
            patch(
                "src.modules.actualizacion_automatica.mail.resolve_outlook_sender",
                side_effect=_boom,
            ),
        ):
            logger = logging.getLogger("p8d_compose_only")
            logger.addHandler(logging.NullHandler())
            with tempfile.TemporaryDirectory() as raw:
                result = run_mail_stage(
                    "combined-sha",
                    logger,
                    months=["2026-08"],
                    future_enabled=False,
                    mail_state_path=Path(raw) / "mail.json",
                    compose_only=True,
                )
            self.assertFalse(result.executed)
            self.assertEqual(result.mail_subject, LEGACY_SUBJECT)


class MailGateAndStateTests(unittest.TestCase):
    def test_unchanged_no_mail(self) -> None:
        self.assertFalse(
            mail_may_be_composed(
                future_enabled=True,
                decision="Unchanged",
                publish_ok=True,
            )
        )

    def test_nodata_no_mail(self) -> None:
        self.assertFalse(
            mail_may_be_composed(
                future_enabled=True,
                decision="NoData",
                publish_ok=True,
            )
        )

    def test_publish_failed_no_mail(self) -> None:
        self.assertFalse(
            mail_may_be_composed(
                future_enabled=True,
                decision="Changed",
                publish_ok=False,
            )
        )

    def test_changed_publish_ok_can_compose(self) -> None:
        self.assertTrue(
            mail_may_be_composed(
                future_enabled=True,
                decision="Changed",
                publish_ok=True,
            )
        )

    def test_anti_duplicado_uses_combined_hash(self) -> None:
        combined = "combined-sha-abc"
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "last_mail_state.json"
            path.write_text(
                json.dumps(
                    {
                        "source_fbl1n_sha256": combined,
                        "mail_status": MAIL_SUCCEEDED,
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(needs_mail_retry(combined, path))
            self.assertTrue(needs_mail_retry("other-hash", path))

    def test_pipeline_hash_alias_combined(self) -> None:
        payload = {
            "sha256": "hist-physical",
            "combined_source_sha256": "combined-sha",
            "source_fbl1n_sha256": "combined-sha",
            "last_success_at": "2026-08-28T00:00:00",
        }
        self.assertEqual(
            pipeline_mail_hash(payload, future_enabled=True),
            "combined-sha",
        )
        self.assertEqual(
            pipeline_mail_hash(payload, future_enabled=False),
            "hist-physical",
        )
        pipeline_allows_mail(
            "combined-sha",
            pipeline_state=payload,
            future_enabled=True,
        )

    def test_temp_state_keeps_date(self) -> None:
        prod_mtime = _mtime(PROD_MAIL_STATE)
        logger = logging.getLogger("d5_mail_state")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "last_mail_state.json"
            written = write_mail_state(
                sha256="combined-sha",
                status=MAIL_SUCCEEDED,
                subject=FUTURE_SUBJECT,
                logger=logger,
                latest_compensation_date="2026-09-02",
                path=path,
            )
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["latest_compensation_date"], "2026-09-02")
            self.assertEqual(loaded["source_fbl1n_sha256"], "combined-sha")
            self.assertEqual(loaded["mail_subject"], FUTURE_SUBJECT)
            self.assertEqual(written["latest_compensation_date"], "2026-09-02")
        if prod_mtime is not None:
            self.assertEqual(_mtime(PROD_MAIL_STATE), prod_mtime)

    def test_outlook_never_instantiated_on_compose(self) -> None:
        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("Outlook no debe instanciarse en D5")

        with (
            patch(
                "src.modules.actualizacion_automatica.mail.send_outlook_mail",
                side_effect=_boom,
            ),
            patch(
                "src.modules.actualizacion_automatica.mail.resolve_outlook_sender",
                side_effect=_boom,
            ),
            patch(
                "src.modules.actualizacion_automatica.mail.list_outlook_accounts",
                side_effect=_boom,
            ),
        ):
            compose_mail_payload(
                to=FAKE_TO,
                sharepoint=FAKE_SP,
                powerbi=FAKE_PBI,
                latest_compensation_date="2026-09-02",
                future_enabled=True,
            )
            logger = logging.getLogger("d5_compose_only")
            logger.addHandler(logging.NullHandler())
            with tempfile.TemporaryDirectory() as raw:
                staged = run_mail_stage(
                    "combined-sha",
                    logger,
                    latest_compensation_date="2026-09-02",
                    future_enabled=True,
                    decision="Changed",
                    publish_ok=True,
                    mail_state_path=Path(raw) / "mail.json",
                    compose_only=True,
                )
            self.assertEqual(staged.mail_subject, FUTURE_SUBJECT)
            self.assertFalse(staged.executed)

    def test_run_stage_skips_unchanged_and_nodata(self) -> None:
        logger = logging.getLogger("d5_skip")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "mail.json"
            unchanged = run_mail_stage(
                "combined-sha",
                logger,
                latest_compensation_date="2026-09-02",
                future_enabled=True,
                decision="Unchanged",
                publish_ok=True,
                mail_state_path=path,
                compose_only=True,
            )
            nodata = run_mail_stage(
                "combined-sha",
                logger,
                latest_compensation_date="2026-09-02",
                future_enabled=True,
                decision="NoData",
                publish_ok=True,
                mail_state_path=path,
                compose_only=True,
            )
        self.assertTrue(unchanged.skipped)
        self.assertTrue(nodata.skipped)
        self.assertFalse(path.exists())

    def test_default_flag_off(self) -> None:
        self.assertFalse(FBL1N_FUTURE_ENABLED)


class D5PreviewTests(unittest.TestCase):
    def test_write_sanitized_preview(self) -> None:
        prod_mail = _mtime(PROD_MAIL_STATE)
        prod_pipe = _mtime(PROD_PIPELINE_STATE)
        payload = compose_mail_payload(
            to=FAKE_TO,
            sharepoint=FAKE_SP,
            powerbi=FAKE_PBI,
            latest_compensation_date="2026-09-02",
            future_enabled=True,
        )
        body_hash = hashlib.sha256(payload.body.encode("utf-8")).hexdigest()
        html_hash = hashlib.sha256(
            (payload.html_body or "").encode("utf-8")
        ).hexdigest()
        preview = {
            "created_at": date.today().isoformat(),
            "stage": "D5",
            "subject": payload.subject,
            "latest_compensation_date": payload.latest_compensation_date,
            "visible_date": "02/09/2026",
            "plain_contains_phrase": FUTURE_PHRASE in payload.body,
            "html_contains_phrase": FUTURE_PHRASE in (payload.html_body or ""),
            "plain_body_sha256": body_hash,
            "html_body_sha256": html_hash,
            "outlook_instantiated": False,
            "recipients_included": False,
            "real_links_included": False,
            "real_attachment_included": False,
        }
        PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        PREVIEW_PATH.write_text(
            json.dumps(preview, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        loaded = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        self.assertEqual(loaded["subject"], FUTURE_SUBJECT)
        self.assertTrue(loaded["plain_contains_phrase"])
        self.assertNotIn("to", loaded)
        self.assertNotIn("example.test", json.dumps(loaded))
        if prod_mail is not None:
            self.assertEqual(_mtime(PROD_MAIL_STATE), prod_mail)
        if prod_pipe is not None:
            self.assertEqual(_mtime(PROD_PIPELINE_STATE), prod_pipe)
