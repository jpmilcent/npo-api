from fastapi import APIRouter, status

from npo.core.constants import ErrorCode
from npo.core.exceptions import APIException
from npo.modules.users.routes.admin import admin_router
from npo.modules.users.routes.profile import profile_router

users_router = APIRouter(
    prefix="/users",
)

users_router.include_router(profile_router)
users_router.include_router(admin_router)


@users_router.get("/{path:path}", include_in_schema=False)
async def users_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.USERS_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.USERS_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
