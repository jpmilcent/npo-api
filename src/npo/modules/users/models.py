import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.dialects import postgresql
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
    refresh_tokens: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"), default=dict, nullable=True
    )

    oauth_providers: Mapped[dict | None] = mapped_column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"), default=dict
    )

    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="user", cascade="all, delete-orphan"
    )

    def add_refresh_token(
        self, jti: str, expires_at: datetime, device_info: str | None = None
    ) -> None:
        """Ajoute un nouveau refresh token à la liste des sessions actives."""
        if self.refresh_tokens is None:
            self.refresh_tokens = {}

        # Copy explicitly dictionary to force SQLAlchemy to dectec change on JSON field
        tokens = dict(self.refresh_tokens)
        tokens[jti] = {
            "device_info": device_info,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.refresh_tokens = tokens

    def revoke_refresh_token(self, jti: str) -> None:
        """Révoque un refresh token spécifique (déconnexion d'un appareil)."""
        if self.refresh_tokens and jti in self.refresh_tokens:
            tokens = dict(self.refresh_tokens)
            del tokens[jti]
            self.refresh_tokens = tokens

    def revoke_all_refresh_tokens(self) -> None:
        """Révoque tous les refresh tokens (déconnexion de tous les appareils)."""
        self.refresh_tokens = {}

    def cleanup_expired_refresh_tokens(self) -> None:
        """Nettoie les tokens expirés de la liste."""
        if not self.refresh_tokens:
            return

        now = datetime.now(UTC)
        tokens = dict(self.refresh_tokens)
        # Identifier les clés à supprimer
        expired_jtis = [
            jti for jti, data in tokens.items() if datetime.fromisoformat(data["expires_at"]) < now
        ]

        if expired_jtis:
            for jti in expired_jtis:
                del tokens[jti]
            self.refresh_tokens = tokens
