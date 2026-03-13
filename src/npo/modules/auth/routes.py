"""
/home/jpm/workspace/clapas/npo-api/src/npo/modules/auth/routes.py
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.config import backend_settings
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    oauth2_scheme,
)
from npo.modules.auth.oauth import oauth
from npo.modules.auth.schema import Token
from npo.modules.auth.services import (
    authenticate_user,
    extract_name_parts,
    get_oauth_user_info,
)
from npo.modules.users.crud import get_user_by_email, get_user_by_oauth, get_user_by_uid
from npo.modules.users.dependencies import get_current_active_user
from npo.modules.users.models import User as UserStorage

logger = logging.getLogger(__name__)

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

auth_route = NpoApiRoute(auth_router)


@auth_router.post("/login", response_model=Token)
async def login_for_access_token(
    db: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = await authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.LOGIN_AUTH_ERROR,
            message=ErrorCode.LOGIN_AUTH_ERROR.formatMsg(),
        )
    access_token_expires = timedelta(minutes=backend_settings.jwt_access_token_expire_minutes)
    refresh_token_expires_delta = timedelta(
        minutes=backend_settings.jwt_refresh_token_expire_minutes
    )
    refresh_token_expires_at = datetime.now(UTC) + refresh_token_expires_delta

    # Create refresh token and extract its JTI
    refresh_token = create_refresh_token(
        data={"sub": user.uid}, expires_delta=refresh_token_expires_delta
    )
    payload = decode_access_token(refresh_token)
    jti = payload["jti"]

    # Create access token linked to the refresh token's JTI (sid = session id)
    access_token = create_access_token(
        data={"sub": user.uid}, expires_delta=access_token_expires, sid=jti
    )
    user.add_refresh_token(jti, refresh_token_expires_at, request.headers.get("User-Agent"))
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@auth_router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: Annotated[str, Body(embed=True)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
    # TODO: create distinct APIExeception for each case
    credentials_exception = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=ErrorCode.REFRESH_AUTH_ERROR,
        message=ErrorCode.REFRESH_AUTH_ERROR.formatMsg(),
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(refresh_token)

        user_uid: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        old_jti: str | None = payload.get("jti")

        if user_uid is None or token_type != "refresh" or old_jti is None:
            raise credentials_exception
    except Exception as e:
        raise credentials_exception from e

    user = await get_user_by_uid(db, uid=user_uid)

    if user is None or not user.is_active:
        raise credentials_exception

    # Reuse detection: if the JTI is not in the active list, it's an old token.
    # Invalidate all sessions for this user as a security measure.
    if not user.refresh_tokens or old_jti not in user.refresh_tokens:
        if user.refresh_tokens:  # Only revoke if there were tokens to begin with
            user.revoke_all_refresh_tokens()
            await db.commit()
        raise credentials_exception

    # Create new tokens
    access_token_expires = timedelta(minutes=backend_settings.jwt_access_token_expire_minutes)
    refresh_token_expires_delta = timedelta(
        minutes=backend_settings.jwt_refresh_token_expire_minutes
    )
    refresh_token_expires_at = datetime.now(UTC) + refresh_token_expires_delta

    new_refresh_token = create_refresh_token(
        data={"sub": user.uid}, expires_delta=refresh_token_expires_delta
    )
    new_payload = decode_access_token(new_refresh_token)
    new_jti = new_payload["jti"]

    access_token = create_access_token(
        data={"sub": user.uid}, expires_delta=access_token_expires, sid=new_jti
    )

    # Rotate tokens: revoke old, add new
    user.revoke_refresh_token(old_jti)
    user.add_refresh_token(new_jti, refresh_token_expires_at, request.headers.get("User-Agent"))
    await db.commit()

    return Token(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    try:
        payload = decode_access_token(token)
        sid = payload.get("sid")  # Session ID is the JTI of the refresh token
        if sid:
            current_user.revoke_refresh_token(sid)
            await db.commit()
    except Exception:
        # If token is invalid for any reason, we can't revoke, but that's okay.
        # The main goal is to revoke the valid session.
        pass


@auth_router.get("/providers/{provider}/login")
async def login_provider(provider: str, request: Request):
    """
    Redirects the user to the OAuth2 provider login page.
    The redirect_uri must be registered in the provider's console.
    """
    client = oauth.create_client(provider)
    if not client:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.AUTH_PROVIDER_NOT_FOUND,
            message=ErrorCode.AUTH_PROVIDER_NOT_FOUND.formatMsg(provider=provider),
        )

    redirect_uri = request.url_for("auth_provider_callback", provider=provider)
    return await client.authorize_redirect(request, redirect_uri)


@auth_router.get("/providers/{provider}/callback", response_model=Token)
async def auth_provider_callback(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
    """
    Callback endpoint for OAuth2 providers.
    Exchanges the code for a token, gets user info, and issues local JWTs.
    """
    client = oauth.create_client(provider)
    if not client:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.AUTH_PROVIDER_NOT_FOUND,
            message=ErrorCode.AUTH_PROVIDER_NOT_FOUND.formatMsg(provider=provider),
        )

    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHORIZED_USER_ERROR,
            message=ErrorCode.UNAUTHORIZED_USER_ERROR.formatMsg(),
        ) from e

    user_data = await get_oauth_user_info(client, token, provider)
    if not user_data:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.NO_USER_INFO_AUTH_ERROR,
            message=ErrorCode.NO_USER_INFO_AUTH_ERROR.formatMsg(provider=provider),
        )

    firstname, lastname = extract_name_parts(user_data)

    email = user_data.get("email")
    if not email:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.NO_EMAIL_AUTH_ERROR,
            message=ErrorCode.NO_EMAIL_AUTH_ERROR.formatMsg(provider=provider),
        )

    if not user_data.get("email_verified"):
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.NOT_VERIFIED_EMAIL_AUTH_ERROR,
            message=ErrorCode.NOT_VERIFIED_EMAIL_AUTH_ERROR.formatMsg(provider=provider),
        )

    # 1. Try to login with OAuth account
    user = await get_user_by_oauth(db, provider=provider, sub=user_data["sub"])

    if not user:
        # 2. Try to link with existing email
        user = await get_user_by_email(db, email)
        if not user:
            # 3. Create new user
            user = UserStorage(
                email=email,
                firstname=firstname,
                lastname=lastname,
                picture_url=user_data["picture_url"],
                email_verified=True,
                oauth_providers={},
            )
            db.add(user)
            await db.flush()

    # Link/Update OAuth provider info
    providers = user.oauth_providers or {}
    providers[provider] = {
        "sub": user_data["sub"],
        "picture_url": user_data.get("picture_url"),
    }
    user.oauth_providers = dict(providers)  # Re-assign to trigger SQLAlchemy change detection

    # Generate tokens (reuse logic)
    access_token_expires = timedelta(minutes=backend_settings.jwt_access_token_expire_minutes)
    refresh_token_expires_delta = timedelta(
        minutes=backend_settings.jwt_refresh_token_expire_minutes
    )
    refresh_token_expires_at = datetime.now(UTC) + refresh_token_expires_delta

    refresh_token = create_refresh_token(
        data={"sub": user.uid}, expires_delta=refresh_token_expires_delta
    )
    payload = decode_access_token(refresh_token)
    jti = payload["jti"]

    access_token = create_access_token(
        data={"sub": user.uid}, expires_delta=access_token_expires, sid=jti
    )
    user.add_refresh_token(jti, refresh_token_expires_at, request.headers.get("User-Agent"))
    await db.commit()

    # NOTE: In a real app with a separate frontend, you would redirect here
    # to your frontend URL with the tokens (e.g., via query params or cookies).
    # For this API example, we return the JSON directly.
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@auth_router.get("/{path:path}", include_in_schema=False)
async def auth_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.AUTH_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.AUTH_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
