from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.security import oauth2_scheme
from npo.modules.auth.exceptions import InactiveUserError, UnauthorizedUserError
from npo.modules.auth.services import get_current_user
from npo.modules.users.models import User
from npo.modules.users.permissions import UserPermission


async def get_current_active_user(
    db: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    try:
        user = await get_current_user(db=db, token=token)
        if not user.is_active:
            raise InactiveUserError(ErrorCode.INACTIVE_USER_ERROR)
    except (UnauthorizedUserError, InactiveUserError) as e:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code=getattr(e, "code", ErrorCode.UNAUTHORIZED_USER_ERROR),
            message=str(e),
        ) from e
    return user


class CheckPermission:
    def __init__(self, permission: UserPermission):
        self.permission = permission

    async def __call__(self, user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if not user.is_superadmin:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.UNAUTHORIZED_USER_ERROR,
                message="User is not a superadmin",
            )

        # Here, we consider that superadmins have all permissions.
        # In a more complex system, we would check `if self.permission in user.permissions`.
        return user
