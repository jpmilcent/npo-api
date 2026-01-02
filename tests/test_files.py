import hashlib

import exiftool
import pyvips
from fastapi import status

from npo import config


async def test_upload_file(client, shared_datadir):
    """
    Test file upload via the /files/upload endpoint.
    Uses a real image file via pytest-datadir.
    """
    # shared_datadir points to the temporary folder containing a copy of tests/data
    image_name = "image_01.jpg"
    image_path = shared_datadir / image_name
    image_mime = "image/jpeg"

    # Open file in binary mode for upload
    with open(image_path, "rb") as f:
        files = {"files": (image_name, f, image_mime)}
        response = await client.post("/files/upload", files=files)

    # Verify that the upload succeeded (Code 200 OK or 201 Created depending on your implementation)
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()

    # Verify that the key (filename) is present in the JSON response
    assert image_name in response_data

    # Verify that all expected keys are present via a set
    expected_keys = {
        "name",
        "path",
        "size",
        "mime",
        "orientation",
        "image_unique_id",
        "perceptual_hash",
        "pixel_hash",
        "latitude",
        "longitude",
        "altitude",
        "datetime_shooting",
        "datetime_digitized",
        "hash",
        "hash_dir",
        "hash_file",
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
    # write_to_memory() force le décodage et retourne les bytes des pixels (RGB/RGBA...)
    data = img.write_to_memory()
    # digest_size=16 produit 128 bits (32 hex chars), format identique à MD5 mais plus rapide/sûr
    expected_hash = hashlib.blake2b(data, digest_size=16).hexdigest()
    assert response_data[image_name]["pixel_hash"] == expected_hash


def _verify_hash_structure(response_data, image_name):
    # Verify hash_dir and hash_file composition
    hash_value = response_data[image_name]["pixel_hash"]
    step = config.settings.hash_dir_step
    parts_count = config.settings.hash_dir_parts_count
    chunks = [hash_value[i : i + step] for i in range(0, step * parts_count, step)]
    assert response_data[image_name]["hash_dir"] == "".join(
        [chunk + "/" for chunk in chunks[:parts_count]]
    )
    assert response_data[image_name]["hash_file"] == hash_value[step * parts_count :]


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


async def test_get_tile(client, shared_datadir, upload_image):
    """
    Test tile image retrieve via the /files/{file_hash}/{zoom}/{x}/{y}.jpg endpoint.
    Compare with a real tile image file via pytest-datadir.
    """

    image_name = "image_02.jpg"
    tile_image_name = "image_02_z2_x0_y1.jpg"
    tile_image_path = shared_datadir / tile_image_name
    tile_image_mime = "image/jpeg"

    uploaded_file_hash = await upload_image(image_name)

    # Get a tile image via the API
    response = await client.get(f"/files/{uploaded_file_hash}/2/0/1.jpg")

    # Verify that the retrieve tile image succeeded (Code 200 OK)
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(tile_image_path, "rb") as file:
        assert response.content == file.read()

    # Verify MIME type
    assert response.headers["content-type"] == tile_image_mime


async def test_get_tile_for_orientation(client, shared_datadir, upload_image):
    """
    Test tile image retrieve via the /files/{file_hash}/{zoom}/{x}/{y}.jpg endpoint
    for an image with EXIF orientation distinct from 1.
    Compare with a real tile image file via pytest-datadir.
    """

    image_name = "image_01.jpg"
    tile_image_name = "image_01_z3_x1_y1.jpg"
    tile_image_path = shared_datadir / tile_image_name
    tile_image_mime = "image/jpeg"

    uploaded_file_hash = await upload_image(image_name)

    # Get a tile image via the API
    response = await client.get(f"/files/{uploaded_file_hash}/3/1/1.jpg")

    # Verify that the retrieve tile image succeeded (Code 200 OK)
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(tile_image_path, "rb") as file:
        assert response.content == file.read()

    # Verify MIME type
    assert response.headers["content-type"] == tile_image_mime


async def test_get_image(client, shared_datadir, upload_image):
    """
    Test image retrieve via the /files/{file_hash} endpoint.
    Compare with a real image file via pytest-datadir.
    """

    image_name = "image_02.jpg"
    image_path = shared_datadir / image_name

    uploaded_file_hash = await upload_image(image_name)

    # Get image via the API
    response = await client.get(f"/files/{uploaded_file_hash}")
    # Verify that the retrieve image succeeded (Code 200 OK)
    assert response.status_code == status.HTTP_200_OK

    # Open tile image file in binary mode to compare with web service response
    with open(image_path, "rb") as file:
        assert response.content == file.read()
