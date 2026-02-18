from fastapi import HTTPException

from npo.core.constants import ErrorCode
from npo.core.logging import request_id_context
from npo.core.schemas import ErrorDetail


class DomainError(Exception):
    """Base class for domain exceptions."""

    def __init__(self, code: ErrorCode, **kwargs):
        self.code = code
        self.kwargs = kwargs


class APIException(HTTPException):
    def __init__(
        self, status_code: int, code: str, message: str, headers: dict[str, str] | None = None
    ):
        super().__init__(
            status_code=status_code,
            detail=ErrorDetail(
                code=code, message=message, request_id=request_id_context.get()
            ).model_dump(),
            headers=headers,
        )
