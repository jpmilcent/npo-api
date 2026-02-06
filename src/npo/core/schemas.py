from pydantic import BaseModel, Field

from npo.core.i18n import _


class ErrorDetail(BaseModel):
    code: str = Field(..., description=_("A unique error code identifying the issue."))
    message: str = Field(..., description=_("A human-readable message explaining the error."))
    request_id: str | None = Field(
        default=None, description=_("A unique identifier for the request, useful for tracing.")
    )
