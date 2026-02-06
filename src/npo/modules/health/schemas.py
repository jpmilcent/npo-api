from pydantic import BaseModel, Field

from npo.core.i18n import _


class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    database: str | None = Field(default=None, description=_("State of the database connection"))
    storage_directory: str | None = Field(
        default=None, description=_("State of the storage directory")
    )
    upload_directory: str | None = Field(
        default=None, description=_("State of the upload directory")
    )


class HealthPing(BaseModel):
    """Response model to ping endpoint."""

    ping: str = "pong"
