"""Main application entry point for NPO API."""

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from npo import config
from npo.database import init_db
from npo.dependencies import (
    make_db_directory,
    make_storage_directory,
    make_upload_directory,
)
from npo.routers.files.routes import files_router
from npo.routers.health.routes import health_router
from npo.routers.metadata.routes import metadata_router
from npo.routers.settings.routes import settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=config.settings.app_name,
    dependencies=[
        Depends(make_db_directory),
        Depends(make_upload_directory),
        Depends(make_storage_directory),
    ],
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(settings_router)
app.include_router(files_router)
app.include_router(metadata_router)


@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{(time.time() - start_time) * 1000:.2f}ms"
    return response


@app.get("/")
async def main():
    """Simple upload form for testing purposes."""
    content = """
<body>
<form action="/files/upload" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)
