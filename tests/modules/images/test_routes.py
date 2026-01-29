import hashlib
from unittest.mock import patch

import exiftool
import pyvips
from fastapi import status
from tests.constants import (
    ERROR_DUPLICATE_PERCEPTUAL_HASH,
    ERROR_IMAGE_NOT_FOUND,
    ERROR_IMAGES_WEBSERVICE_NOT_FOUND,
    ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND,
    ERROR_RAW_METADATA_NOT_FOUND,
    IMAGE_01_JPG,
    IMAGE_02_JPG,
    IMAGE_03_DNG,
    IMAGE_04_DNG,
    IMAGE_05_NEF,
    IMAGE_06_NEF,
    PERCEPTUAL_HASH_LENGTH,
)

from npo.core import config
from npo.modules.images.crud import get_images_list


async def test_root(override_db_session, client):
    """
    Test the root endpoint.
    """
    _, initial_total = await get_images_list(override_db_session, limit=1)

    response = await client.get("/images/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert all(k in data for k in ("meta", "data"))

    ITEMS_PER_PAGE_DEFAULT = 100
    TOTAL_ITEMS_DEFAULT = initial_total
    TOTAL_PAGES_DEFAULT = (initial_total + ITEMS_PER_PAGE_DEFAULT - 1) // ITEMS_PER_PAGE_DEFAULT
    CURRENT_PAGE_DEFAULT = 1

    DATA_DEFAULT = []

    assert "pagination" in data["meta"]
    pagination = data["meta"]["pagination"]
    assert all(
        k in pagination for k in ("total_items", "total_pages", "current_page", "items_per_page")
    )
    assert pagination["total_items"] == TOTAL_ITEMS_DEFAULT
    assert pagination["total_pages"] == TOTAL_PAGES_DEFAULT
    assert pagination["current_page"] == CURRENT_PAGE_DEFAULT
    assert pagination["items_per_page"] == ITEMS_PER_PAGE_DEFAULT

    assert (
        data["data"] == DATA_DEFAULT
        if TOTAL_ITEMS_DEFAULT == 0
        else len(data["data"]) <= ITEMS_PER_PAGE_DEFAULT
    )


async def test_upload_image(large_file_cache, upload_image):
    """
    Test image upload via the /images/upload endpoint.
    Uses a real image file via pytest-datadir.
    """
    # large_file_cache points to the temporary folder containing a copy of tests/data
    image_name = IMAGE_01_JPG
    image_path = large_file_cache / image_name
    image_mime = "image/jpeg"

    response = await upload_image(image_name, return_full_response=True)

    # Verify that the upload succeeded (Code 201 Created)
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()

    # Verify that the key (filename) is present in the JSON response
    assert image_name in response_data

    # Verify that all expected keys are present via a set
    expected_keys = {
        "name",
        "path",
        "path_hash_dir",
        "path_hash_file",
        "size",
        "mime",
        "orientation",
        "image_unique_id",
        "file_hash",
        "pixel_hash",
        "perceptual_hash",
        "latitude",
        "longitude",
        "altitude",
        "datetime_shooting",
        "datetime_digitized",
        "meta_data",
    }
    assert expected_keys == set(response_data[image_name].keys())

    assert response_data[image_name]["name"] == image_name

    # Verify size
    assert response_data[image_name]["size"] == image_path.stat().st_size

    # Verify MIME type
    assert response_data[image_name]["mime"] == image_mime

    _verify_pixel_hash(response_data, image_name, image_path)
    _verify_hash_structure(response_data, image_name)
    _verify_metadata(response_data[image_name], image_path)


def _verify_pixel_hash(response_data, image_name, image_path):
    # Verify pixel hash
    img = pyvips.Image.new_from_file(image_path, access="sequential")
    # write_to_memory() forces decoding and returns the pixel bytes (RGB/RGBA...)
    data = img.write_to_memory()
    # digest_size=16 produces 128 bits (32 hex chars), a format identical to MD5 but faster/safer
    expected_hash = hashlib.blake2b(data, digest_size=16).hexdigest()
    assert response_data[image_name]["pixel_hash"] == expected_hash


def _verify_hash_structure(response_data, image_name):
    # Verify path_hash_dir and path_hash_file composition
    hash_value = response_data[image_name]["pixel_hash"]
    step = config.settings.hash_dir_step
    parts_count = config.settings.hash_dir_parts_count
    chunks = [hash_value[i : i + step] for i in range(0, step * parts_count, step)]
    assert response_data[image_name]["path_hash_dir"] == "".join(
        [chunk + "/" for chunk in chunks[:parts_count]]
    )
    assert response_data[image_name]["path_hash_file"] == hash_value[step * parts_count :]


def _verify_metadata(response_image_data, image_path):
    # Verify metadata content (EXIF)
    meta_data = response_image_data["meta_data"]
    assert isinstance(meta_data, dict)

    # Cross-validation: use exiftool locally on the source file
    # to verify that the API returns the same values.
    with exiftool.ExifToolHelper() as et:
        local_metadata = et.get_metadata(str(image_path), params=["-n"])[0]

    _compare_critical_metadata_fields(local_metadata, meta_data)
    _verify_metadata_altitude(local_metadata, response_image_data)
    _verify_metadata_latitude(local_metadata, response_image_data)
    _verify_metadata_longitude(local_metadata, response_image_data)


def _compare_critical_metadata_fields(local_metadata, meta_data):
    """Comparison of critical fields (MIME, Dimensions) only to avoid some fields that may vary.
    This ensures that the API correctly extracts real data from the file.
    """
    critical_fields = ["File:MIMEType", "File:ImageWidth", "File:ImageHeight"]
    for field in critical_fields:
        if field in local_metadata:
            assert meta_data[field] == local_metadata[field]


def _verify_metadata_altitude(local_metatadata, response_image_data):
    """Check altitude negativity based on reference.
    EXIF:GPSAltitudeRef indicates whether the altitude is above (0) or below (1) sea level.
    """
    if ("EXIF:GPSAltitude", "EXIF:GPSAltitudeRef") in local_metatadata:
        expected_altitude = local_metatadata["EXIF:GPSAltitude"]
        if local_metatadata.get("EXIF:GPSAltitudeRef") == 1:
            expected_altitude = -expected_altitude
        assert isinstance(response_image_data["altitude"], float)
        assert response_image_data["altitude"] == expected_altitude


def _verify_metadata_latitude(local_metatadata, response_image_data):
    """Check latitude negativity based on reference.
    EXIF:GPSLatitudeRef indicates whether the latitude is north (N) or south (S) of the equator.
    """
    if ("EXIF:GPSLatitude", "EXIF:GPSLatitudeRef") in local_metatadata:
        expected_latitude = local_metatadata["EXIF:GPSLatitude"]
        if local_metatadata.get("EXIF:GPSLatitudeRef") == "S":
            expected_latitude = -expected_latitude
        assert isinstance(response_image_data["latitude"], float)
        assert response_image_data["latitude"] == expected_latitude


def _verify_metadata_longitude(local_metatadata, response_image_data):
    """Check longitude negativity based on reference.
    EXIF:GPSLongitudeRef indicates whether the longitude is east (E) or west (W)
    of the prime meridian.
    """
    if ("EXIF:GPSLongitude", "EXIF:GPSLongitudeRef") in local_metatadata:
        expected_longitude = local_metatadata["EXIF:GPSLongitude"]
        if local_metatadata.get("EXIF:GPSLongitudeRef") == "W":
            expected_longitude = -expected_longitude
        assert isinstance(response_image_data["longitude"], float)
        assert response_image_data["longitude"] == expected_longitude


async def test_upload_duplicate_image(upload_image):
    """
    Test image upload of a duplicate image file via the /images/upload endpoint.
    The second upload of the same file should be detected as a duplicate.
    """
    image_name = IMAGE_01_JPG

    # First upload
    response1_perceptual_hash = await upload_image(image_name, return_attribute="perceptual_hash")

    # Second upload (duplicate)
    response2 = await upload_image(image_name, return_full_response=True, skip_seed=True)

    assert response2.status_code == status.HTTP_409_CONFLICT
    response_data2 = response2.json()
    assert "detail" in response_data2
    error_detail = response_data2["detail"]
    assert error_detail["code"] == ERROR_DUPLICATE_PERCEPTUAL_HASH
    assert (
        error_detail["message"]
        == f"Image {image_name} with perceptual hash {response1_perceptual_hash} already exists."
    )


async def test_upload_duplicate_perceptual_image(large_file_cache, shared_datadir, upload_image):
    """
    Test image file upload of a perceptual duplicate file via the /images/upload endpoint.
    Uses two similar image files via pytest-datadir.
    The second upload of a perceptually similar file should be detected as a duplicate.
    """
    # large_file_cache points to the temporary folder containing a copy of tests/data
    image_name = IMAGE_01_JPG
    image_path = large_file_cache / image_name

    # First upload
    response1_perceptual_hash = await upload_image(image_name, return_attribute="perceptual_hash")

    # Transform image using pyvips to create a perceptual duplicate
    img = pyvips.Image.new_from_file(str(image_path), access="sequential")
    img = img.resize(0.99)
    modified_image_name = "image_01_modified.jpg"
    modified_image_path = shared_datadir / modified_image_name
    img.write_to_file(str(modified_image_path))

    # Second upload (perceptual duplicate)
    response2 = await upload_image(modified_image_name, return_full_response=True)

    assert response2.status_code == status.HTTP_409_CONFLICT
    response_data2 = response2.json()
    assert "detail" in response_data2
    error_detail = response_data2["detail"]
    assert error_detail["code"] == ERROR_DUPLICATE_PERCEPTUAL_HASH
    assert (
        error_detail["message"] == f"Image {modified_image_name} with perceptual hash "
        f"{response1_perceptual_hash} already exists."
    )


async def test_upload_duplicate_image_fr(client, large_file_cache, upload_image):
    """
    Test file upload of a duplicate file via the /images/upload endpoint with French locale.
    """
    # large_file_cache points to the temporary folder containing a copy of tests/data
    image_name = IMAGE_01_JPG
    image_path = large_file_cache / image_name
    image_mime = "image/jpeg"

    # First upload
    response1_perceptual_hash = await upload_image(image_name, return_attribute="perceptual_hash")

    # Mock translation function to simulate French translation without ContextVar dependency
    def mock_gettext(message):
        if message == "Image {filename} with perceptual hash {perceptual_hash} already exists.":
            return "Image {filename} avec hash perceptuel {perceptual_hash} déjà existant."
        return message

    # Second upload (duplicate) with Accept-Language: fr
    with open(image_path, "rb") as f:
        files = {"files": (image_name, f, image_mime)}
        with patch("npo.core.constants._", side_effect=mock_gettext):
            response2 = await client.post(
                "/images/upload",
                files=files,
                headers={"Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"},
            )

    assert response2.status_code == status.HTTP_409_CONFLICT
    response_data2 = response2.json()
    assert "detail" in response_data2
    error_detail = response_data2["detail"]
    assert error_detail["code"] == ERROR_DUPLICATE_PERCEPTUAL_HASH
    assert error_detail["message"] == (
        f"Image {image_name} avec hash perceptuel {response1_perceptual_hash} déjà existant."
    )


async def test_get_tile(client, shared_datadir, upload_image):
    """
    Test tile image retrieve via the /images/{file_hash}/{zoom}/{x}/{y}.jpg endpoint.
    Compare with a real tile image file via pytest-datadir.
    """

    image_name = IMAGE_02_JPG
    tile_image_name = "image_02_z2_x0_y1.jpg"
    tile_image_path = shared_datadir / tile_image_name
    tile_image_mime = "image/jpeg"

    uploaded_file_hash = await upload_image(image_name)

    # Get a tile image via the API
    response = await client.get(f"/images/{uploaded_file_hash}/2/0/1.jpg")

    # Verify that the retrieve tile image succeeded (Code 200 OK)
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(tile_image_path, "rb") as file:
        assert response.content == file.read()

    # Verify MIME type
    assert response.headers["content-type"] == tile_image_mime


async def test_get_tile_for_orientation(client, shared_datadir, upload_image):
    """
    Test tile image retrieve via the /images/{file_hash}/{zoom}/{x}/{y}.jpg endpoint
    for an image with EXIF orientation distinct from 1.
    Compare with a real tile image file via pytest-datadir.
    """

    image_name = IMAGE_01_JPG
    tile_image_name = "image_01_z3_x1_y1.jpg"
    tile_image_path = shared_datadir / tile_image_name
    tile_image_mime = "image/jpeg"

    uploaded_file_hash = await upload_image(image_name)

    # Get a tile image via the API
    response = await client.get(f"/images/{uploaded_file_hash}/3/1/1.jpg")

    # Verify that the retrieve tile image succeeded (Code 200 OK)
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(tile_image_path, "rb") as file:
        assert response.content == file.read()

    # Verify MIME type
    assert response.headers["content-type"] == tile_image_mime


async def test_get_tile_not_found(verify_404):
    """
    Test tile image retrieve via the /images/{file_hash}/{zoom}/{x}/{y}.jpg endpoint
    for 404 response.
    """

    pixel_hash = "abcdef1234567890abcdef1234567890"
    zoom = 2
    x = 0
    y = 1

    await verify_404(
        f"/images/{pixel_hash}/{zoom}/{x}/{y}.jpg",
        ERROR_IMAGE_NOT_FOUND,
        f"Image {pixel_hash} not found.",
    )


async def test_get_image(client, large_file_cache, upload_image):
    """
    Test image retrieve via the /images/{file_hash} endpoint.
    Compare with a real image file via pytest-datadir.
    """

    image_name = IMAGE_02_JPG
    image_path = large_file_cache / image_name

    uploaded_file_hash = await upload_image(image_name)

    response = await client.get(f"/images/{uploaded_file_hash}")
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(image_path, "rb") as file:
        assert response.content == file.read()


async def test_get_image_not_found(verify_404):
    """
    Test image retrieve via the /images/{file_hash} endpoint for 404 response.
    """

    pixel_hash = "abcdef1234567890abcdef1234567890"

    await verify_404(
        f"/images/{pixel_hash}",
        ERROR_IMAGE_NOT_FOUND,
        f"Image {pixel_hash} not found.",
    )


async def test_mime_type_for_dng(upload_image):
    dng = IMAGE_03_DNG
    mime_type = await upload_image(dng, return_attribute="mime")
    assert mime_type == "image/x-adobe-dng"


async def test_perceptual_hash_for_dng(upload_image):
    dng = IMAGE_04_DNG
    perceptual_hash = await upload_image(dng, return_attribute="perceptual_hash")
    assert len(perceptual_hash) == PERCEPTUAL_HASH_LENGTH
    assert perceptual_hash != "0000000000000000"


async def test_distinct_pixel_hash_for_dng(upload_image):
    dng1 = IMAGE_03_DNG
    dng2 = IMAGE_04_DNG

    pixel_hash_1 = await upload_image(dng1)
    pixel_hash_2 = await upload_image(dng2)

    assert pixel_hash_1 != pixel_hash_2


async def test_distinct_pixel_hash_for_raw(upload_image):
    raw1 = IMAGE_05_NEF
    raw2 = IMAGE_06_NEF

    pixel_hash_1 = await upload_image(raw1)
    pixel_hash_2 = await upload_image(raw2)

    assert pixel_hash_1 != pixel_hash_2


async def test_metadata(client, large_file_cache, upload_image):
    """Test the metadata endpoint."""

    image_name = IMAGE_01_JPG
    image_path = large_file_cache / image_name

    uploaded_file_hash = await upload_image(image_name)

    response = await client.get(f"/images/{uploaded_file_hash}/metadata")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    meta_data = response.json()

    # Cross-validation: use exiftool locally on the source file
    # to verify that the API returns the same values.
    with exiftool.ExifToolHelper() as et:
        local_metadata = et.get_metadata(str(image_path))[0]

    # Comparison of critical fields (MIME, Dimensions) only to avoid some fields that may vary.
    # This ensures that the API correctly extracts real data from the file.
    for key in ["File:MIMEType", "File:ImageWidth", "File:ImageHeight"]:
        if key in local_metadata:
            assert meta_data[key] == local_metadata[key]


async def test_raw_metadata_not_found(verify_404):
    """Test the raw metadata endpoint for 404 response."""

    pixel_hash = "abcdef1234567890abcdef1234567890"
    await verify_404(
        f"/images/{pixel_hash}/metadata",
        ERROR_RAW_METADATA_NOT_FOUND,
        f"Raw metadata for file {pixel_hash} not found.",
    )


async def test_photography_metadata_not_found(verify_404):
    """Test the photography metadata endpoint for 404 response."""

    pixel_hash = "abcdef1234567890abcdef1234567890"
    await verify_404(
        f"/images/{pixel_hash}/metadata/photography",
        ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND,
        f"Photography metadata for file {pixel_hash} not found.",
    )


async def test_images_catch_all(verify_404):
    """Test the images catch-all endpoint for 404 response."""

    unknown_path = "some/random/path"
    await verify_404(
        f"/images/{unknown_path}",
        ERROR_IMAGES_WEBSERVICE_NOT_FOUND,
        f"Webservice /images/{unknown_path} requested not found.",
    )
