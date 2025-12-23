from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from npo.database import Base


class File(Base):
    name: Mapped[str]
    path: Mapped[str] = mapped_column(String(250), unique=True)
    mime: Mapped[str | None] = mapped_column(String(50), default=None)
    size: Mapped[int | None] = mapped_column(Integer, default=None)

    hash: Mapped[str] = mapped_column(String(32), default="")
    hash_dir: Mapped[str] = mapped_column(String(16), default="")
    hash_file: Mapped[str] = mapped_column(String(20), default="")

    meta_data: Mapped[dict | None] = mapped_column(JSON, default=None)
