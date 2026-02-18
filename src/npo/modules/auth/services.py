import logging
from typing import Annotated

from fastapi import Depends, status
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.security import decode_access_token, oauth2_scheme, verify_password
from npo.modules.auth.exceptions import InactiveUserError, UnauthorizedUserError
from npo.modules.auth.schema import TokenData
from npo.modules.users.crud import get_user_by_email, get_user_by_uid
from npo.modules.users.models import User

logger = logging.getLogger(__name__)


async def authenticate_user(
    db: Annotated[AsyncSession, Depends(get_session)], sub: str, password: str
) -> User | None:
    out = None
    # Try to fetch by email first (standard login), then by sub (username)
    user = await get_user_by_email(db, sub)
    if user and user.password and verify_password(password, user.password):
        out = user
    return out


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_session)], token: Annotated[str, Depends(oauth2_scheme)]
):
    credentials_error = UnauthorizedUserError(ErrorCode.UNAUTHORIZED_USER_ERROR)
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if username is None:
            raise credentials_error
        token_data = TokenData(username=username)
    except InvalidTokenError as e:
        raise credentials_error from e

    # The token 'sub' claim now contains the User internal UUID
    user = await get_user_by_uid(db, uid=token_data.username)
    if user is None:
        raise credentials_error
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise InactiveUserError(ErrorCode.INACTIVE_USER_ERROR)
    return current_user


async def get_oauth_user_info(client, token: dict, provider: str) -> dict:
    """
    Fetch and normalize user information from the provider.
    Handles provider-specific quirks (like GitHub private emails).
    """
    user_info = token.get("userinfo")
    if not user_info and client.server_metadata.get("userinfo_endpoint"):
        try:
            user_info = await client.userinfo(token=token)
        except Exception as e:
            logger.error(f"Failed to fetch user info from {provider}: {e}")
            return {}

    if not user_info:
        return {}

    email, email_verified = await get_email_from_provider(client, token, provider, user_info)

    sub = user_info.get("sub") or user_info.get("id")
    if not sub:
        logger.warning(f"No 'sub' or 'id' found in user info for {provider}")
        return {}

    # Normalize data
    return {
        "email": email,
        "email_verified": email_verified,
        "sub": str(sub),
        "picture_url": user_info.get("picture") or user_info.get("avatar_url"),
        "given_name": user_info.get("given_name"),
        "family_name": user_info.get("family_name"),
        "name": user_info.get("name"),
    }


async def get_email_from_provider(client, token: dict, provider: str, user_info: dict):
    email = user_info.get("email")
    email_verified = user_info.get("email_verified")

    # Specific logic for GitHub to retrieve private email
    if provider == "github":
        if not email:
            try:
                resp = await client.get("user/emails", token=token)
                if resp.status_code == status.HTTP_200_OK:
                    emails = resp.json()
                    for e in emails:
                        if e.get("primary") and e.get("verified"):
                            email = e.get("email")
                            email_verified = True
                            break
            except Exception as e:
                logger.warning(f"Failed to fetch emails from GitHub: {e}")
        else:
            # If email is present in public profile, consider it verified
            email_verified = True

    return email, email_verified


def extract_name_parts(user_data: dict) -> tuple[str, str]:
    firstname = user_data.get("given_name", "")
    lastname = user_data.get("family_name", "")
    # Fallback for name if firstname/lastname are missing (e.g. GitHub returns "name": "John Doe")
    if not firstname and not lastname and user_data.get("name"):
        name_parts = user_data.get("name", "").split(" ", 1)
        firstname = name_parts[0]
        if len(name_parts) > 1:
            lastname = name_parts[1]

    return (firstname, lastname)
