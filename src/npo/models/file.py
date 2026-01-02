from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from npo.database import Base


class File(Base):
    name: Mapped[str]
    path: Mapped[str] = mapped_column(String(250), unique=True)
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
    hash: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    hash_dir: Mapped[str] = mapped_column(String(75), default="")
    hash_file: Mapped[str] = mapped_column(String(32), default="")

    meta_data: Mapped[dict | None] = mapped_column(JSON, default=None)
