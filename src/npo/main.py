"""Main application entry point for NPO API."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi_babel import BabelConfigs, BabelMiddleware, _
from starlette.middleware.sessions import SessionMiddleware

from npo.core import config
from npo.core.database import init_db
from npo.core.dependencies import (
    ensure_system_directories,
)
from npo.core.i18n import N_
from npo.core.logging import request_id_context, setup_logging
from npo.core.openapi import register_custom_openapi
from npo.modules.auth.routes import auth_router
from npo.modules.health.routes import health_router
from npo.modules.images.routes import images_router
from npo.modules.settings.routes import settings_router
from npo.modules.users.routes.router import users_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_system_directories()
    await init_db()
    logger.info("✅ Application started and database tables created!")
    yield
    logger.info("🛑 Application shutting down!")


description = N_(
    """NPO API helps you manage your naturalist images.

## Middlewares

The API uses several middlewares for all endpoints:

*   **Request ID**: A unique request ID is generated for each incoming
request and added to the response headers as `X-Request-ID`. This is useful
for tracking and debugging.
*   **Request Logging**: All requests are logged with their method, path,
status code, and processing time.
*   **Response Time**: The processing time for a request is added to the
call_next response headers as `X-Response-Time`.
*   **Internationalization (i18n)**: The API supports multiple languages.
The language is determined by the `Accept-Language` header in the request.
"""
)


app = FastAPI(
    title=config.settings.app_name,
    description=description,
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(settings_router)
app.include_router(images_router)
app.include_router(users_router)
app.include_router(auth_router)

# Session Middleware is required for OAuth2 (Authlib) to store the "state" parameter
app.add_middleware(SessionMiddleware, secret_key=config.settings.jwt_secret_key)

# CORS Middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.backend_settings.cors_origins,
    allow_credentials=config.backend_settings.cors_allow_credentials,
    allow_methods=config.backend_settings.cors_allow_methods,
    allow_headers=config.backend_settings.cors_allow_headers,
    expose_headers=config.backend_settings.cors_expose_headers,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code}",
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(process_time, 2),
            }
        },
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

# Register custom OpenAPI generation for dynamic translation
register_custom_openapi(app, _)


@app.get(
    "/",
    summary=N_("Upload form"),
    description=N_("Simple upload form for testing purposes."),
)
async def main():
    content = """
<body>
<form action="/images/upload" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)
