from unittest.mock import patch

from npo.modules.users.utils import send_verification_email


async def test_send_verification_email():
    fake_email = "fake_email"
    fake_token = "fake_token"
    fake_verification_link = f"https://myapp.com/verify-email?token={fake_token}"

    with patch("npo.modules.users.utils.logger") as mock_logger:
        send_verification_email(fake_email, fake_token)

    mock_logger.info.assert_any_call(f"📧 Sending verification email to {fake_email}")
    mock_logger.info.assert_any_call(f"🔗 Verification link: {fake_verification_link}")
