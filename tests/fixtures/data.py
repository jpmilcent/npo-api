import logging
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import status
from tests.constants import EXTERNAL_FILES

logger = logging.getLogger(__name__)


class MockResponse:
    def __init__(self, json_data, status_code=201):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self.json_data


@pytest.fixture(scope="session")
def large_file_cache():
    """Creates and returns the path to the persistent cache directory."""
    cache_dir = Path(__file__).parent.parent / ".cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def seed_data(session_client, large_file_cache):
    """
    Uploads common images once per session and returns their API responses.
    """
    seeded_responses = {}

    for filename, url in EXTERNAL_FILES.items():
        cache_path = large_file_cache / filename

        # Ensure file exists (download logic duplicated here to avoid scope issues)
        if not cache_path.exists():
            logger.info(f"Downloading {filename} from {url} for seeding...")
            with httpx.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                with open(cache_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

        # Upload via API
        with open(cache_path, "rb") as f:
            files = {"files": (filename, f, "image/jpeg")}
            response = await session_client.post("/images/upload", files=files)
            if response.status_code == status.HTTP_201_CREATED:
                seeded_responses[filename] = response.json()

    return seeded_responses


@pytest.fixture()
def upload_image(client, shared_datadir, large_file_cache, seed_data, request):
    """
    Fixture (Factory function) that provides a function to upload an image and return its hash.
    It uses cached data from seed_data if available to skip the actual upload.
    """
    # Check for marker to set default behavior
    marker = request.node.get_closest_marker("skip_seed")
    default_skip_seed = marker is not None

    async def _uploader(
        image_name,
        return_full_response=False,
        return_response_data=False,
        return_attribute="pixel_hash",
        skip_seed=default_skip_seed,
    ):
        # Check if we have this image pre-loaded
        if not skip_seed and image_name in seed_data:
            # Return a mock response with the pre-calculated data
            response = MockResponse(seed_data[image_name])
        else:
            # Fallback to real upload for non-standard files
            shared_path = shared_datadir / image_name
            cache_path = large_file_cache / image_name
            if cache_path.exists():
                image_path = cache_path
            elif shared_path.exists():
                image_path = shared_path
            else:
                raise FileNotFoundError(
                    f"Image file '{image_name}' not found in shared_datadir or large_file_cache."
                )

            image_mime = "image/jpeg"

            with open(image_path, "rb") as f:
                files = {"files": (image_name, f, image_mime)}
                response = await client.post("/images/upload", files=files)

        if return_full_response:
            return response
        else:
            assert response.status_code == status.HTTP_201_CREATED, response.json()
            response_data = response.json()
            if return_response_data:
                return response_data
            else:
                assert image_name in response_data
                assert return_attribute in response_data[image_name]
                return response_data[image_name][return_attribute]

    return _uploader
