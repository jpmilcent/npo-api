from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="A unique error code identifying the issue.")
    message: str = Field(..., description="A human-readable message explaining the error.")
    request_id: str | None = Field(
        default=None, description="A unique identifier for the request, useful for tracing."
    )
