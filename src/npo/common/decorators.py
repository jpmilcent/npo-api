import logging
import typing

from fastapi import APIRouter, status

from npo.core.schemas import ErrorDetail

logger = logging.getLogger(__name__)


class NpoApiRoute:
    COMMON_RESPONSES: typing.ClassVar[dict] = {
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

    VALID_HTTP_METHODS: typing.ClassVar[set] = {"GET", "POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, router: APIRouter):
        self.router = router

    def __call__(
        self,
        path: str,
        method: str = "GET",
        responses: dict | None = None,
        override_404: dict | None = None,
        **kwargs,
    ):
        if method.upper() not in self.VALID_HTTP_METHODS:
            logger.error(f"Invalid HTTP method attempted: {method}")
            raise ValueError(
                f"Invalid HTTP method: {method}. Must be one of {self.VALID_HTTP_METHODS}"
            )
        if responses is None:
            responses = self.COMMON_RESPONSES.copy()
        else:
            responses.update(self.COMMON_RESPONSES.copy())
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
        route_method = getattr(self.router, method.lower())
        return route_method(path, responses=responses, **kwargs)
