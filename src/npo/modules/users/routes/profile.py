import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from npo.modules.users.crud import get_user_by_email
from npo.modules.users.dependencies import get_current_active_user
from npo.modules.users.models import User as UserStorage
from npo.modules.users.schema import (
    User,
    UserPasswordUpdate,
    UserProfileUpdate,
)
from npo.modules.users.utils import send_verification_email

logger = logging.getLogger(__name__)

profile_router = APIRouter(tags=["User Profile"])
profile_route = NpoApiRoute(profile_router)


@profile_route("/me")
async def read_users_me(
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
) -> User:
    return User.model_validate(current_user)


@profile_route("/me/providers", response_model=list[str])
async def read_user_providers(
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
) -> list[str]:
    providers = []
    if current_user.password:
        providers.append("local")
    if current_user.oauth_providers:
        for provider_name in current_user.oauth_providers:
            providers.append(provider_name)
    return providers


@profile_route("/me/providers/{provider}", method="DELETE", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_provider(
    provider: str,
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    if not current_user.oauth_providers or provider not in current_user.oauth_providers:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.PROVIDER_NOT_FOUND,
            message=ErrorCode.PROVIDER_NOT_FOUND.formatMsg(provider=provider),
        )

    if not current_user.password and len(current_user.oauth_providers) == 1:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.CANNOT_REMOVE_LAST_AUTH_METHOD,
            message=ErrorCode.CANNOT_REMOVE_LAST_AUTH_METHOD.formatMsg(),
        )

    providers = dict(current_user.oauth_providers)
    del providers[provider]
    current_user.oauth_providers = providers
    await db.commit()


@profile_route("/me", method="PATCH", response_model=User)
async def update_user_profile(
    user_update: UserProfileUpdate,
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    background_tasks: BackgroundTasks,
) -> User:
    update_data = user_update.model_dump(exclude_unset=True)

    if "email" in update_data:
        new_email = update_data["email"]
        if new_email != current_user.email:
            existing_user = await get_user_by_email(db, email=new_email)
            if existing_user:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code=ErrorCode.EMAIL_ALREADY_REGISTERED,
                    message=ErrorCode.EMAIL_ALREADY_REGISTERED.formatMsg(),
                )
            current_user.email = new_email
            current_user.email_verified = False

            # Generate verification token and send email
            token = create_access_token(
                data={"sub": new_email, "type": "email_verification"},
                expires_delta=timedelta(hours=24),
            )
            background_tasks.add_task(send_verification_email, new_email, token)
        del update_data["email"]

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return User.model_validate(current_user)


@profile_route("/me/password", method="PUT", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    password_update: UserPasswordUpdate,
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    if not current_user.password or not verify_password(
        password_update.old_password, current_user.password
    ):
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.INCORRECT_PASSWORD,
            message=ErrorCode.INCORRECT_PASSWORD.formatMsg(),
        )

    current_user.password = get_password_hash(password_update.new_password)
    await db.commit()


@profile_route("/me", method="DELETE", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    current_user: Annotated[UserStorage, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await db.delete(current_user)
    await db.commit()


@profile_route("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    invalid_token_error = APIException(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=ErrorCode.INVALID_VERIFICATION_TOKEN,
        message=ErrorCode.INVALID_VERIFICATION_TOKEN.formatMsg(),
    )
    try:
        payload = decode_access_token(token)
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if email is None or token_type != "email_verification":
            raise invalid_token_error
    except Exception as e:
        raise invalid_token_error from e

    user = await get_user_by_email(db, email=email)
    if not user:
        raise invalid_token_error

    if not user.email_verified:
        user.email_verified = True
        await db.commit()

    return {"message": "Email successfully verified"}
