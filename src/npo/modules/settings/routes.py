import logging
import os
import re
from importlib import metadata
from typing import Annotated

from fastapi import APIRouter, Depends, status

from npo.core import config
from npo.core.constants import ErrorCode
from npo.core.dependencies import get_frontend_settings
from npo.core.exceptions import APIException
from npo.modules.settings.schema import Version

logger = logging.getLogger(__name__)

settings_router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
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
            logger.exception(f"Version for package {package_name} not found")
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
        "environment": config.settings.environment,
    }


@settings_router.get("/{path:path}", include_in_schema=False)
async def settings_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.SETTINGS_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.SETTINGS_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
