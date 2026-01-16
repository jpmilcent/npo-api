from pydantic import BaseModel


class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    database: str | None = None
    storage_directory: str | None = None
    upload_directory: str | None = None



class HealthPing(BaseModel):
    """Response model to ping endpoint."""

    ping: str = "pong"
