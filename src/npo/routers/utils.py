from fastapi import APIRouter, HTTPException, status

from npo.models.errors import ErrorDetail

COMMON_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorDetail,
        "description": "Bad Request",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorDetail,
        "description": "Resource not found",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorDetail,
        "description": "Internal Server Error",
    },
}

VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class APIException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail=ErrorDetail(code=code, message=message).model_dump(),
        )


def create_route_decorator(router: APIRouter):
    def route_decorator(
        path: str, method: str = "GET", responses: dict = None, override_404: dict = None, **kwargs
    ):
        if method.upper() not in VALID_HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method: {method}. Must be one of {VALID_HTTP_METHODS}")
        if responses is None:
            responses = COMMON_RESPONSES.copy()
        else:
            responses.update(COMMON_RESPONSES.copy())
        if override_404:
            overrides = {
                status.HTTP_404_NOT_FOUND: {
                    "model": ErrorDetail,
                    "description": override_404.get("description", "Resource not found"),
                    "content": {
                        "application/json": {
                            "example": {
                                "code": override_404.get("code", "string"),
                                "message": override_404.get("message", "string"),
                            }
                        }
                    },
                }
            }
            responses.update(overrides)
        route_method = getattr(router, method.lower())
        return route_method(path, responses=responses, **kwargs)

    return route_decorator
