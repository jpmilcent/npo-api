import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from npo.core.database import Base

if TYPE_CHECKING:
    from npo.modules.images.models import Image


class User(Base):
    uid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    firstname: Mapped[str | None] = mapped_column(String(150))
    lastname: Mapped[str | None] = mapped_column(String(150))
    picture_url: Mapped[str | None] = mapped_column(String(500), default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)

    password: Mapped[str | None] = mapped_column(String(250))
    refresh_token_jti: Mapped[str | None] = mapped_column(String(36), default=None)
    oauth_providers: Mapped[dict | None] = mapped_column(JSON, default=dict)

    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="user", cascade="all, delete-orphan"
    )
