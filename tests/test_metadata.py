import exiftool
from fastapi import status


async def test_metadata(client, shared_datadir, upload_image):
    """Test the metadata endpoint."""

    image_name = "image_01.jpg"
    image_path = shared_datadir / image_name

    uploaded_file_hash = await upload_image(image_name)

    response = await client.get(f"/metadata/{uploaded_file_hash}")
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
        f"/metadata/{pixel_hash}",
        "RAW_METADATA_NOT_FOUND",
        f"Raw metadata for file {pixel_hash} not found.",
    )


async def test_photography_metadata_not_found(verify_404):
    """Test the photography metadata endpoint for 404 response."""

    pixel_hash = "abcdef1234567890abcdef1234567890"
    await verify_404(
        f"/metadata/{pixel_hash}/photography",
        "PHOTOGRAPHY_METADATA_NOT_FOUND",
        f"Photography metadata for file {pixel_hash} not found.",
    )


async def test_metadata_catch_all(verify_404):
    """Test the metadata catch-all endpoint for 404 response."""

    unknown_path = "some/random/path"
    await verify_404(
        f"/metadata/{unknown_path}",
        "METADATA_WEBSERVICE_NOT_FOUND",
        f"Webservice /metadata/{unknown_path} requested not found.",
    )
