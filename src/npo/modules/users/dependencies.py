from typing import Annotated

from fastapi import Depends, status

from npo.core.constants import ErrorCode
from npo.core.exceptions import APIException
from npo.modules.auth.services import get_current_active_user
from npo.modules.users.models import User
from npo.modules.users.permissions import UserPermission


class CheckPermission:
    def __init__(self, permission: UserPermission):
        self.permission = permission

    def __call__(self, user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if not user.is_superadmin:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.UNAUTHORIZED_USER_ERROR,
                message="User is not a superadmin",
            )

        # Ici, on considère que les superadmins ont toutes les permissions définies
        # Dans un système plus complexe, on vérifierait `if self.permission in user.permissions`
        # Pour l'instant, le simple fait d'être superadmin valide l'accès.
        return user
