"""
/home/jpm/workspace/clapas/npo-api/src/npo/modules/auth/routes.py
"""

import logging
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.config import backend_settings
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.security import create_access_token, create_refresh_token, decode_access_token
from npo.modules.auth.oauth import oauth
from npo.modules.auth.schema import Token
from npo.modules.auth.services import (
    authenticate_user,
    extract_name_parts,
    get_current_active_user,
    get_oauth_user_info,
)
from npo.modules.users.crud import get_user_by_email, get_user_by_oauth, get_user_by_uid
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
    access_token = create_access_token(data={"sub": user.uid}, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(minutes=backend_settings.jwt_refresh_token_expire_minutes)
    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(
        data={"sub": user.uid, "jti": jti}, expires_delta=refresh_token_expires
    )
    user.refresh_token_jti = jti
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@auth_router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: Annotated[str, Body(embed=True)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
    credentials_exception = APIException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=ErrorCode.REFRESH_AUTH_ERROR,
        message=ErrorCode.REFRESH_AUTH_ERROR.formatMsg(),
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(refresh_token)
        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti: str | None = payload.get("jti")
        if username is None or token_type != "refresh" or jti is None:
            raise credentials_exception
    except Exception as e:
        raise credentials_exception from e

    user = await get_user_by_uid(db, uid=username)

    # Additional check: JTI value in request must be equal to the one recorded
    if user is None or not user.is_active or user.refresh_token_jti != jti:
        raise credentials_exception

    access_token_expires = timedelta(minutes=backend_settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(data={"sub": user.uid}, expires_delta=access_token_expires)

    # Renew the refresh token (optional but recommended)
    refresh_token_expires = timedelta(minutes=backend_settings.jwt_refresh_token_expire_minutes)
    new_jti = str(uuid.uuid4())
    new_refresh_token = create_refresh_token(
        data={"sub": user.uid, "jti": new_jti}, expires_delta=refresh_token_expires
    )
    user.refresh_token_jti = new_jti
    await db.commit()

    return Token(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
):
    current_user.refresh_token_jti = None
    await db.commit()


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

    # Link/Update OAuth provider info
    providers = user.oauth_providers or {}
    providers[provider] = {
        "sub": user_data["sub"],
        "picture_url": user_data.get("picture_url"),
    }
    user.oauth_providers = dict(providers)  # Re-assign to trigger SQLAlchemy change detection

    # Generate tokens (reuse logic)
    access_token_expires = timedelta(minutes=backend_settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(data={"sub": user.uid}, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(minutes=backend_settings.jwt_refresh_token_expire_minutes)
    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(
        data={"sub": user.uid, "jti": jti}, expires_delta=refresh_token_expires
    )
    user.refresh_token_jti = jti
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
