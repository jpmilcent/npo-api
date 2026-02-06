from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.i18n import _
from npo.modules.health.schemas import HealthCheck, HealthPing
from npo.modules.health.services import (
    check_database,
    check_storage_directory,
    check_upload_directory,
)

health_router = APIRouter(
    prefix="/health",
    tags=["Health"],
    responses={404: {"description": "Not found"}},
)


@health_router.get(
    "/check",
    summary=_("Perform a Health Check"),
    description=_(
        "Endpoint to perform a healthcheck."
        "Check if API return HTTP status 200 (OK) and if database and "
        "directory configurations are operational or not."
    ),
    response_description=_("Return up or down informations about crucial parts of this API."),
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
)
async def check_health(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthCheck:
    health = HealthCheck()
    db_status = await check_database(session)
    health.database = "up" if db_status else "down"

    upload_status = await check_upload_directory()
    health.upload_directory = "up" if upload_status else "down"

    storage_status = await check_storage_directory()
    health.storage_directory = "up" if storage_status else "down"

    return health


@health_router.get(
    "/ping",
    summary="Respond with pong !",
    description="Endpoint for checking only if the API is responding.",
    response_description="Pong !",
    status_code=status.HTTP_200_OK,
    response_model=HealthPing,
)
async def get_pong():
    return HealthPing(ping="pong")


@health_router.get("/{path:path}", include_in_schema=False)
async def health_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.HEALTH_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.HEALTH_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
