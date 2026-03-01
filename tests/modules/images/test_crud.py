from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npo.modules.images.crud import (
    get_image_by_file_hash,
    get_image_by_image_unique_id,
    get_image_by_perceptual_hash,
    get_image_by_pixel_hash,
    get_images_list,
)
from npo.modules.images.models import Image


async def test_get_image_by_file_hash_success(override_db_session):
    """
    Check that an image can be retrieved by its file hash.
    """
    # Arrange
    file_hash = "a1b2c3d4e5f67890a1b2c3d4e5f67890"
    image = Image(
        name="test_crud_image.jpg",
        path="/tmp/test_crud_image.jpg",
        file_hash=file_hash,
        mime="image/jpeg",
        user_id=1,
    )
    override_db_session.add(image)
    await override_db_session.commit()

    # Act
    result = await get_image_by_file_hash(file_hash, override_db_session)

    # Assert
    assert result is not None
    assert result.id == image.id
    assert result.file_hash == file_hash
    assert result.user_id == 1


async def test_get_image_by_file_hash_not_found(override_db_session):
    """
    Check that searching for a non-existent hash returns None.
    """
    # Act
    result = await get_image_by_file_hash("nonexistent_hash", override_db_session)

    # Assert
    assert result is None


async def test_get_image_by_pixel_hash_success(override_db_session):
    """
    Check that an image can be retrieved by its pixel hash.
    """
    # Arrange
    pixel_hash = "a1b2c3d4e5f67890a1b2c3d4e5f67890"
    image = Image(
        name="test_crud_image.jpg",
        path="/tmp/test_crud_image.jpg",
        pixel_hash=pixel_hash,
        file_hash="d4e5f67890a1b2c3",
        mime="image/jpeg",
        user_id=1,
    )
    override_db_session.add(image)
    await override_db_session.commit()

    # Act
    result = await get_image_by_pixel_hash(pixel_hash, override_db_session)

    # Assert
    assert result is not None
    assert result.id == image.id
    assert result.pixel_hash == pixel_hash
    assert result.user_id == 1


async def test_get_image_by_pixel_hash_not_found(override_db_session):
    """
    Check that searching for a non-existent pixel hash returns None.
    """
    # Act
    result = await get_image_by_pixel_hash("nonexistent_hash", override_db_session)

    # Assert
    assert result is None


async def test_get_image_by_perceptual_hash_success(override_db_session):
    """
    Check that an image can be retrieved by its perceptual hash.
    """
    # Arrange
    perceptual_hash = "a1b2c3d4e5f67890a1b2c3d4e5f67890"
    image = Image(
        name="test_crud_image.jpg",
        path="/tmp/test_crud_image.jpg",
        perceptual_hash=perceptual_hash,
        file_hash="d4e5f67890a1b2c3",
        mime="image/jpeg",
        user_id=1,
    )
    override_db_session.add(image)
    await override_db_session.commit()

    # Act
    result = await get_image_by_perceptual_hash(perceptual_hash, override_db_session)

    # Assert
    assert result is not None
    assert result.id == image.id
    assert result.perceptual_hash == perceptual_hash


async def test_get_image_by_perceptual_hash_not_found(override_db_session):
    """
    Check that searching for a non-existent perceptual hash returns None.
    """
    # Act
    result = await get_image_by_perceptual_hash("nonexistent_hash", override_db_session)

    # Assert
    assert result is None


async def test_get_image_by_unique_id_success(override_db_session):
    """
    Check that an image can be retrieved by its unique ID.
    """
    # Arrange
    unique_id = "unique-image-id-123"
    image = Image(
        name="test_crud_image.jpg",
        path="/tmp/test_crud_image.jpg",
        image_unique_id=unique_id,
        file_hash="d4e5f67890a1b2c3",
        mime="image/jpeg",
        user_id=1,
    )
    override_db_session.add(image)
    await override_db_session.commit()

    # Act
    result = await get_image_by_image_unique_id(unique_id, override_db_session)

    # Assert
    assert result is not None
    assert result.id == image.id
    assert result.image_unique_id == unique_id
    assert result.user_id == 1


async def test_get_image_by_unique_id_not_found(override_db_session):
    """
    Check that searching for a non-existent unique ID returns None.
    """
    # Act
    result = await get_image_by_image_unique_id("nonexistent-unique-id", override_db_session)

    # Assert
    assert result is None


async def test_get_images_list_success(override_db_session):
    """
    Check that a list of images can be retrieved with pagination.
    """
    # Arrange
    # Get initial count to support running with other tests
    _, initial_total = await get_images_list(override_db_session, limit=1)

    # Create 3 images
    NUMBER_OF_IMAGES_TO_CREATE = 3
    for i in range(NUMBER_OF_IMAGES_TO_CREATE):
        image = Image(
            name=f"test_list_{i}.jpg",
            path=f"/tmp/test_list_{i}.jpg",
            file_hash=f"list_hash_{i}",
            pixel_hash=f"list_pixel_{i}",
            mime="image/jpeg",
            user_id=1,
        )
        override_db_session.add(image)
    await override_db_session.commit()

    # Act
    # Retrieve first page of 2 items
    NUMBER_OF_IMAGES_TO_RETRIEVE = 2
    results, total = await get_images_list(
        override_db_session, skip=0, limit=NUMBER_OF_IMAGES_TO_RETRIEVE
    )

    # Assert
    assert total == initial_total + NUMBER_OF_IMAGES_TO_CREATE
    assert len(results) == NUMBER_OF_IMAGES_TO_RETRIEVE
    # Verify that the 'pixel_hash' is correctly labeled as 'hash' in the result mapping
    assert results[0]["hash"] is not None
    assert results[0]["name"].startswith("test_list_")


@pytest.mark.asyncio
async def test_get_images_list_with_user_id():
    user_id = 1
    mappings = MagicMock()
    db = AsyncMock()
    db.scalar.return_value = None
    db.execute.return_value = mappings
    mappings.return_value.all.return_value = []
    with patch("npo.modules.images.crud.select") as mock_select:
        stmt_count = MagicMock()
        stmt_count.where.return_value = "fake_stmt_count"

        select_value = MagicMock()
        select_value.select_from.return_value = stmt_count

        mock_select.return_value = select_value

        await get_images_list(db, limit=1, user_id=user_id)

    assert stmt_count.where.call_count == 1
