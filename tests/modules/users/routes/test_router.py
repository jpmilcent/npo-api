from tests.constants import (
    ERROR_USERS_WEBSERVICE_NOT_FOUND,
)


async def test_users_catch_all(verify_404):
    """Test the users catch-all endpoint for 404 response."""

    unknown_path = "some/random/path"
    await verify_404(
        f"/users/{unknown_path}",
        ERROR_USERS_WEBSERVICE_NOT_FOUND,
        f"Webservice /users/{unknown_path} requested not found.",
    )
