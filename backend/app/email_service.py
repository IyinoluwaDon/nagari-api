import logging
import re
import smtplib
from email.message import EmailMessage
from html import escape

import httpx

from .config import get_settings
from .models import DemoRequest
from .schemas import ROLE_LABELS

log = logging.getLogger("nagari.email")


def _one_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def build_notification(req: DemoRequest) -> EmailMessage:
    s = get_settings()
    role = ROLE_LABELS.get(req.role, req.role)
    submitted = req.created_at.strftime("%d %b %Y, %H:%M UTC")
    message = req.message or "(no message provided)"

    msg = EmailMessage()
    msg["Subject"] = _one_line(f"New Nagari demo request: {req.school_name}")
    msg["From"] = s.smtp_user
    msg["To"] = s.notify_email
    # Hitting Reply goes straight to the person who asked for the demo
    msg["Reply-To"] = req.email

    msg.set_content(
        "A new demo request was submitted on the Nagari website.\n\n"
        f"Full name:  {req.full_name}\n"
        f"School:     {req.school_name}\n"
        f"Email:      {req.email}\n"
        f"Phone:      {req.phone}\n"
        f"Role:       {role}\n"
        f"Submitted:  {submitted}\n"
        f"Request ID: {req.id}\n\n"
        f"Message:\n{message}\n"
    )

    rows = [
        ("Full name", req.full_name),
        ("School", req.school_name),
        ("Email", req.email),
        ("Phone", req.phone),
        ("Role", role),
        ("Submitted", submitted),
    ]
    table = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#6b7280">{escape(k)}</td>'
        f'<td style="padding:6px 0;color:#071F1A"><strong>{escape(v)}</strong></td></tr>'
        for k, v in rows
    )
    msg.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;font-size:14px">
<h2 style="color:#071F1A">New demo request</h2>
<table>{table}</table>
<p style="margin-top:16px;color:#6b7280">Message</p>
<p style="white-space:pre-wrap;color:#071F1A">{escape(message)}</p>
<p style="color:#9ca3af;font-size:12px">Request ID {req.id}. Reply to this email to respond directly.</p>
</div>""",
        subtype="html",
    )
    return msg


def _send_resend(req: DemoRequest) -> bool:
    s = get_settings()
    msg = build_notification(req)
    text = msg.get_body(preferencelist=("plain",)).get_content()
    html = msg.get_body(preferencelist=("html",)).get_content()
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {s.resend_api_key}"},
        json={
            "from": s.resend_from,
            "to": [s.notify_email],
            "reply_to": req.email,
            "subject": str(msg["Subject"]),
            "text": text,
            "html": html,
        },
        timeout=15,
    )
    if resp.status_code >= 300:
        log.error("Resend rejected request %s: %s %s", req.id, resp.status_code, resp.text[:300])
        return False
    return True


def _send_smtp(req: DemoRequest) -> bool:
    s = get_settings()
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
        server.starttls()
        server.login(s.smtp_user, s.smtp_password)
        server.send_message(build_notification(req))
    return True


def send_notification(req: DemoRequest) -> bool:
    """Send the notification. Returns True on success. Never raises."""
    s = get_settings()
    try:
        if s.resend_api_key:
            return _send_resend(req)
        if s.smtp_user and s.smtp_password:
            return _send_smtp(req)
        log.warning("No email provider configured; skipping email for request %s", req.id)
        return False
    except Exception:
        log.exception("Failed to send notification for request %s", req.id)
        return False
