from fastapi import HTTPException

from npo.core.logging import request_id_context
from npo.core.schemas import ErrorDetail


class APIException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail=ErrorDetail(
                code=code, message=message, request_id=request_id_context.get()
            ).model_dump(),
        )
