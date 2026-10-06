from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage


def send_email(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    mail_from: str,
    mail_to: str,
    subject: str,
    body: str,
    use_ssl: bool = True,
) -> None:
    """通过 SMTP SSL 发送纯文本邮件。"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    if use_ssl or port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(msg)
