import os
import re
from importlib import metadata
from typing import Annotated

from fastapi import APIRouter, Depends, status

from npo import config
from npo.constants import ErrorCode
from npo.dependencies import get_frontend_settings
from npo.routers.settings.schema import Version
from npo.routers.utils import APIException

settings_router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}},
)


@settings_router.get(
    "",
    summary="App frontend settings",
)
async def info(settings: Annotated[config.FrontendSettings, Depends(get_frontend_settings)]):
    return settings


@settings_router.get(
    "/version",
    summary="App version",
    response_model=Version,
    tags=["Settings"],
)
async def version():
    package_name = "npo"
    commit_sha = os.getenv("GIT_COMMIT_SHA", "unknown")
    commit_date = os.getenv("GIT_COMMIT_DATE", "unknown")

    try:
        from npo.version import (  # type: ignore # noqa: PLC0415
            commit_id,
            version as app_version,
        )

        if commit_id:
            commit_sha = commit_id
    except ImportError:
        try:
            app_version = metadata.version(package_name)
        except metadata.PackageNotFoundError as e:
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code=ErrorCode.SETTINGS_VERSION_NOT_FOUND,
                message=ErrorCode.SETTINGS_VERSION_NOT_FOUND.formatMsg(package_name=package_name),
            ) from e

    # Extract date from app version
    match = re.search(r"\.d(\d{8})", app_version)
    if match:
        d = match.group(1)
        commit_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"

    # Extract commit SHA1 from app version
    if "+" in app_version:
        app_version = app_version.split("+")[0]

    return {
        "version": app_version,
        "commit_sha": commit_sha,
        "commit_date": commit_date,
        "environment": os.getenv("NPO_ENVIRONMENT", "production"),
    }


@settings_router.get("/{path:path}", include_in_schema=False)
async def settings_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.SETTINGS_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.SETTINGS_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
