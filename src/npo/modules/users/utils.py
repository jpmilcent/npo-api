import logging

logger = logging.getLogger(__name__)


def send_verification_email(email: str, token: str) -> None:
    """
    Simulates sending a verification email.
    In a real application, you would use an SMTP client or an email API here.
    """
    # TODO: Replace with actual email sending logic
    verification_link = f"https://myapp.com/verify-email?token={token}"
    logger.info(f"📧 Sending verification email to {email}")
    logger.info(f"🔗 Verification link: {verification_link}")
