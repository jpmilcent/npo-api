from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="A unique error code identifying the issue.")
    message: str = Field(..., description="A human-readable message explaining the error.")
