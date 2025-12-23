from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.database import get_session
from npo.routers.health.schemas import HealthCheck, HealthPing
from npo.routers.health.services import (
    check_database,
    check_storage_directory,
    check_upload_directory,
)

health_router = APIRouter(
    prefix="/health",
    tags=["health"],
    responses={404: {"description": "Not found"}},
)


@health_router.get(
    "/check",
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
)
async def check_health(session: AsyncSession = Depends(get_session)) -> HealthCheck:
    """Endpoint to perform a healthcheck."""
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
    status_code=status.HTTP_200_OK,
    response_model=HealthPing,
)
async def get_pong():
    return HealthPing(ping="pong")
