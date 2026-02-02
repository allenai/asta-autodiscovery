"""Email sending utilities.

This module provides functions for sending emails via SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Default SMTP server
DEFAULT_SMTP_SERVER = "smtp.example.com"

# Default sender email
DEFAULT_SENDER_EMAIL = "no-reply@asta.allenai.org"


def send_email(
    recipient_email: str,
    subject: str,
    body_html: str,
    sender_email: str = DEFAULT_SENDER_EMAIL,
    smtp_server: str = DEFAULT_SMTP_SERVER,
) -> None:
    """Send an HTML email via SMTP.

    Args:
        recipient_email: Recipient email address
        subject: Email subject line
        body_html: HTML email body
        sender_email: Sender email address
        smtp_server: SMTP server hostname

    Raises:
        smtplib.SMTPException: If email sending fails
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(smtp_server) as conn:
        conn.starttls()  # Upgrade connection to secure
        conn.send_message(msg)
        logger.info(f"Email sent successfully to {recipient_email}")
