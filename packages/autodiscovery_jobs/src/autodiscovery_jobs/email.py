"""Email sending utilities.

This module provides functions for sending emails via SMTP.
"""

import logging
import smtplib
from email.message import EmailMessage
from email.policy import SMTP as SMTPPolicy

logger = logging.getLogger(__name__)

# Default SMTP server - Internal AI2 mail server
DEFAULT_SMTP_SERVER = "smtp.example.com"
DEFAULT_SMTP_PORT = 25

# Default sender email
DEFAULT_SENDER_EMAIL = "no-reply@allenai.org"


def send_email(
    recipient_email: str,
    subject: str,
    body_html: str,
    sender_email: str = DEFAULT_SENDER_EMAIL,
    smtp_server: str = DEFAULT_SMTP_SERVER,
    smtp_port: int = DEFAULT_SMTP_PORT,
) -> None:
    """Send an HTML email via SMTP.

    Args:
        recipient_email: Recipient email address
        subject: Email subject line
        body_html: HTML email body
        sender_email: Sender email address
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port (default: 25)

    Raises:
        smtplib.SMTPException: If email sending fails
    """
    msg = EmailMessage(policy=SMTPPolicy)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(body_html, subtype="html", charset="utf-8")

    with smtplib.SMTP(smtp_server, smtp_port) as conn:
        conn.send_message(msg)
        logger.info(f"Email sent successfully to {recipient_email}")
