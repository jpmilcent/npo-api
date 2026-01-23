from npo.modules.images.crud import get_image_by_file_hash
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
    )
    override_db_session.add(image)
    await override_db_session.commit()

    # Act
    result = await get_image_by_file_hash(file_hash, override_db_session)

    # Assert
    assert result is not None
    assert result.id == image.id
    assert result.file_hash == file_hash


async def test_get_image_by_file_hash_not_found(override_db_session):
    """
    Vérifie que la recherche d'un hash inexistant retourne None.
    """
    # Act
    result = await get_image_by_file_hash("nonexistent_hash", override_db_session)

    # Assert
    assert result is None
