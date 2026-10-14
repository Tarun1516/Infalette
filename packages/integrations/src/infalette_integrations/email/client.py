"""Email integration client.

Real delivery paths:
- provider == "ses": AWS SES v1 API via boto3 (lazy import)
- provider == "smtp": stdlib smtplib (STARTTLS) — no extra dependencies
When neither is configured the send returns ``status: "skipped"`` and logs
the payload; it never claims a fake "sent".
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class EmailClient:
    """Client for sending emails via AWS SES or SMTP."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._email_settings = self._settings.email
        self._provider = (self._email_settings.provider or "ses").lower()
        self._from_address = self._email_settings.from_address

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        tenant_id: UUID,
        text_content: Optional[str] = None,
    ) -> dict:
        """Send an email through the configured provider."""
        if not to:
            return {"status": "error", "error": "No recipient"}

        if self._provider == "smtp" and self._email_settings.smtp_host:
            return await self._send_via_smtp(to, subject, html_content, text_content)
        if self._provider == "ses":
            result = await self._send_via_ses(to, subject, html_content, text_content)
            if result.get("status") != "unconfigured":
                return result

        logger.info(
            "Email skipped (no %s delivery configured): to=%s subject=%s",
            self._provider,
            to,
            subject,
        )
        return {
            "status": "skipped",
            "reason": "email_delivery_not_configured",
            "to": to,
            "subject": subject,
            "provider": self._provider,
        }

    async def _send_via_ses(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
    ) -> dict:
        try:
            import boto3
        except ImportError:
            return {"status": "unconfigured", "reason": "boto3_not_installed"}

        access_key = self._email_settings.aws_access_key_id
        secret_key = self._email_settings.aws_secret_access_key
        if not access_key or not secret_key:
            return {"status": "unconfigured", "reason": "aws_credentials_missing"}

        client = boto3.client(
            "ses",
            region_name=self._email_settings.aws_region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key.get_secret_value(),
        )
        try:
            import asyncio

            response = await asyncio.to_thread(
                client.send_email,
                Source=self._from_address,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Html": {"Data": html_content},
                        **({"Text": {"Data": text_content}} if text_content else {}),
                    },
                },
            )
            return {
                "status": "sent",
                "to": to,
                "subject": subject,
                "provider": "ses",
                "message_id": response.get("MessageId"),
            }
        except Exception as e:
            logger.error("SES send failed: %s", e)
            return {"status": "error", "error": str(e), "provider": "ses"}

    async def _send_via_smtp(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str],
    ) -> dict:
        import asyncio
        import smtplib

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self._from_address
        message["To"] = to
        message.attach(MIMEText(text_content or html_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        settings = self._email_settings

        def _send() -> dict:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username and settings.smtp_password:
                    server.login(
                        settings.smtp_username,
                        settings.smtp_password.get_secret_value(),
                    )
                server.sendmail(self._from_address, [to], message.as_string())
            return {
                "status": "sent",
                "to": to,
                "subject": subject,
                "provider": "smtp",
            }

        try:
            return await asyncio.to_thread(_send)
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return {"status": "error", "error": str(e), "provider": "smtp"}

    async def send_bulk_email(
        self,
        to_list: list[str],
        subject: str,
        html_content: str,
        tenant_id: UUID,
    ) -> dict:
        """Send bulk emails."""
        sent = 0
        failed = 0
        for to in to_list:
            result = await self.send_email(to, subject, html_content, tenant_id)
            if result.get("status") == "sent":
                sent += 1
            else:
                failed += 1

        return {"status": "sent" if sent else "failed", "count": sent, "failed": failed}

    async def send_template_email(
        self,
        to: str,
        template_name: str,
        variables: dict,
        tenant_id: UUID,
    ) -> dict:
        """Send an email from a template."""
        rows = "".join(f"<p><b>{k}</b>: {v}</p>" for k, v in variables.items())
        html_content = f"<h1>{template_name}</h1>{rows}"
        return await self.send_email(to, template_name, html_content, tenant_id)

    async def verify_email_identity(self, email: str) -> dict:
        """Verify an email identity with SES when configured."""
        if self._provider != "ses" or not self._email_settings.aws_access_key_id:
            return {"status": "skipped", "reason": "ses_not_configured", "email": email}
        try:
            import boto3

            client = boto3.client(
                "ses",
                region_name=self._email_settings.aws_region,
                aws_access_key_id=self._email_settings.aws_access_key_id,
                aws_secret_access_key=self._email_settings.aws_secret_access_key.get_secret_value(),
            )
            client.verify_email_identity(EmailAddress=email)
            return {"status": "verification_sent", "email": email}
        except Exception as e:
            return {"status": "error", "error": str(e), "email": email}
