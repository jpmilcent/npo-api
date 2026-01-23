import logging

import pytest
from fastapi import APIRouter

from npo.common.decorators import NpoApiRoute

VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


@pytest.mark.parametrize("invalid_method", ["INVALID", "HEAD", "OPTIONS"])
def test_invalid_http_method_comprehensive(caplog, invalid_method):
    """
    Test log and exception for invalid HTTP methods.
    """
    router = APIRouter()
    npo_route = NpoApiRoute(router)

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(ValueError, match=f"Invalid HTTP method: {invalid_method}") as exc_info,
    ):
        npo_route("/test", method=invalid_method)

    assert f"Invalid HTTP method attempted: {invalid_method}" in caplog.text

    error_msg = str(exc_info.value)
    assert f"Must be one of {VALID_HTTP_METHODS}" in error_msg
