from typing import Annotated

from fastapi import APIRouter, Depends

from npo import config
from npo.dependencies import get_frontend_settings

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
