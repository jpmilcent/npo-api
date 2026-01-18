"""Main application entry point for NPO API."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi_babel import BabelConfigs, BabelMiddleware

from npo.core import config
from npo.core.database import init_db
from npo.core.dependencies import (
    make_db_directory,
    make_storage_directory,
    make_upload_directory,
)
from npo.core.logging import request_id_context, setup_logging
from npo.modules.health.routes import health_router
from npo.modules.images.routes import images_router
from npo.modules.settings.routes import settings_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("✅ Application started and database tables created!")
    yield
    logger.info("🛑 Application shutting down!")


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
app.include_router(images_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} - "
        "Status: {response.status_code} - Time: {process_time:.2f}ms"
    )
    response.headers["X-Response-Time"] = f"{process_time:.2f}ms"
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request_id_context.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


babel_configs = BabelConfigs(
    ROOT_DIR=__file__,
    BABEL_DEFAULT_LOCALE=config.settings.default_language,
    BABEL_TRANSLATION_DIRECTORY="locales",
)
app.add_middleware(
    BabelMiddleware,
    babel_configs=babel_configs,
)


@app.get("/")
async def main():
    """Simple upload form for testing purposes."""
    content = """
<body>
<form action="/images/upload" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)
