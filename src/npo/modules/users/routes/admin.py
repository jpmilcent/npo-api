import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.modules.users.crud import (
    create_user,
    get_user_by_email,
    get_user_by_uid,
    get_users,
    update_user,
)
from npo.modules.users.dependencies import CheckPermission
from npo.modules.users.permissions import UserPermission
from npo.modules.users.schema import (
    User,
    UserCreate,
    UserUpdate,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter(tags=["User Administration"])
admin_route = NpoApiRoute(admin_router)


@admin_route(
    "/",
    response_model=list[User],
    dependencies=[Depends(CheckPermission(UserPermission.READ))],
)
async def read_users(
    db: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
):
    return await get_users(db, skip=skip, limit=limit)


@admin_route(
    "/",
    method="POST",
    response_model=User,
    dependencies=[Depends(CheckPermission(UserPermission.WRITE))],
)
async def create_new_user(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await get_user_by_email(db, email=user_in.email)
    if user:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.EMAIL_ALREADY_REGISTERED,
            message=ErrorCode.EMAIL_ALREADY_REGISTERED.formatMsg(),
        )
    return await create_user(db, user_in)


@admin_route(
    "/{uid}",
    response_model=User,
    dependencies=[Depends(CheckPermission(UserPermission.READ))],
)
async def read_user_by_id(
    uid: str,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await get_user_by_uid(db, uid=uid)
    if not user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.USER_NOT_FOUND,
            message=ErrorCode.USER_NOT_FOUND.formatMsg(uid=uid),
        )
    return user


@admin_route(
    "/{uid}",
    method="PATCH",
    response_model=User,
    dependencies=[Depends(CheckPermission(UserPermission.WRITE))],
)
async def update_user_by_id(
    uid: str,
    user_in: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await get_user_by_uid(db, uid=uid)
    if not user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.USER_NOT_FOUND,
            message=ErrorCode.USER_NOT_FOUND.formatMsg(uid=uid),
        )
    return await update_user(db, user, user_in)


@admin_route(
    "/{uid}",
    method="DELETE",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(CheckPermission(UserPermission.DELETE))],
)
async def delete_user_by_id(
    uid: str,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await get_user_by_uid(db, uid=uid)
    if not user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.USER_NOT_FOUND,
            message=ErrorCode.USER_NOT_FOUND.formatMsg(uid=uid),
        )
    await db.delete(user)
    await db.commit()
