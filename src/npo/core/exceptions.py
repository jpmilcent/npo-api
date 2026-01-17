from fastapi import HTTPException

from npo.core.schemas import ErrorDetail


class APIException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail=ErrorDetail(code=code, message=message).model_dump(),
        )
