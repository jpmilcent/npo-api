import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from npo.core.config import backend_settings
from npo.core.database import Base

if TYPE_CHECKING:
    from npo.modules.users.models import User

logger = logging.getLogger(__name__)


class Image(Base):
    name: Mapped[str]
    path: Mapped[str] = mapped_column(String(250), unique=True)
    path_hash_dir: Mapped[str] = mapped_column(String(75), default="")
    path_hash_file: Mapped[str] = mapped_column(String(32), default="")

    mime: Mapped[str | None] = mapped_column(String(50), default=None)
    size: Mapped[int | None] = mapped_column(Integer, default=None)
    orientation: Mapped[int | None] = mapped_column(Integer, default=None)
    image_unique_id: Mapped[str | None] = mapped_column(String(64), default=None)

    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)
    altitude: Mapped[float | None] = mapped_column(default=None)
    datetime_shooting: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    datetime_digitized: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    perceptual_hash: Mapped[str | None] = mapped_column(String(16), default=None)
    pixel_hash: Mapped[str | None] = mapped_column(String(32), default=None)
    file_hash: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    meta_data: Mapped[dict | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"), default=None
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="images")


@event.listens_for(Image, "after_delete")
def delete_image_files(mapper, connection, target):
    """
    Deletes the physical files associated with the image when it is removed from the database.
    """
    if not target.path_hash_dir or not target.path_hash_file:
        return

    storage_dir = backend_settings.storage_dir
    dir_path = os.path.join(storage_dir, target.path_hash_dir)

    if not os.path.exists(dir_path):
        return

    try:
        for filename in os.listdir(dir_path):
            if filename.startswith(target.path_hash_file):
                file_path = os.path.join(dir_path, filename)
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
                except OSError as e:
                    logger.error(f"Error deleting file {file_path}: {e}")
    except OSError as e:
        logger.error(f"Error accessing directory {dir_path}: {e}")
