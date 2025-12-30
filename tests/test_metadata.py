import exiftool
from fastapi import status
from fastapi.testclient import TestClient

from npo.main import app

client = TestClient(app)


async def test_metadata(shared_datadir, upload_image):
    """Test the metadata endpoint."""

    image_name = "image_01.jpg"
    image_path = shared_datadir / image_name

    uploaded_file_hash = await upload_image(image_name)

    response = client.get(f"/metadata/{uploaded_file_hash}")
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
