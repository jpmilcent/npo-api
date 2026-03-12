from datetime import UTC, datetime, timedelta

from npo.modules.users.models import User


async def test_add_refresh_token():
    fake_jti = "test_jti"
    fake_expires_at = datetime.now(UTC) + timedelta(days=2)
    fake_device_info = "test_device_info"

    user = User()
    user.refresh_tokens = None
    user.add_refresh_token(jti=fake_jti, expires_at=fake_expires_at, device_info=fake_device_info)

    assert fake_jti in user.refresh_tokens
    assert user.refresh_tokens[fake_jti]["device_info"] == fake_device_info
    assert user.refresh_tokens[fake_jti]["expires_at"] == fake_expires_at.isoformat()


async def test_cleanup_expired_refresh_tokens_without_refresh_tokens():
    user = User()
    user.refresh_tokens = None
    result = user.cleanup_expired_refresh_tokens()

    assert result is None


async def test_cleanup_expired_refresh_tokens_with_expired_tokens():
    fake_jti = "test_jti"
    fake_expires_at = datetime.now(UTC) - timedelta(days=2)
    fake_device_info = "test_device_info"

    user = User()
    user.refresh_tokens = {
        fake_jti: {"device_info": fake_device_info, "expires_at": fake_expires_at.isoformat()}
    }
    result = user.cleanup_expired_refresh_tokens()

    assert fake_jti not in user.refresh_tokens
    assert result is None
