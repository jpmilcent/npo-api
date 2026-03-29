import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import Integer
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)
from sqlalchemy.sql import functions as func

from npo.core import config

# Configuration du pooling
engine_kwargs = {
    "echo": config.settings.log_level.upper() == "DEBUG",
    "pool_size": config.settings.db_pool_size,
    "max_overflow": config.settings.db_max_overflow,
    "pool_timeout": config.settings.db_pool_timeout,
    "pool_recycle": config.settings.db_pool_recycle,
    "pool_pre_ping": config.settings.db_pool_pre_ping,
}

# SQLite ne supporte pas pool_size et max_overflow de la même manière.
# On les retire si on utilise SQLite pour éviter des warnings ou erreurs selon le driver.
if config.settings.database_uri.startswith("sqlite"):
    # Pour SQLite, on laisse SQLAlchemy gérer le pool par défaut ou on pourrait utiliser NullPool
    engine_kwargs.pop("pool_size", None)
    engine_kwargs.pop("max_overflow", None)

engine = create_async_engine(config.settings.database_uri, **engine_kwargs)


async def init_db():
    """Initialize the database by running Alembic migrations."""
    # Exécuter les migrations Alembic
    alembic_cfg = Config(toml_file="pyproject.toml")
    alembic_cfg.set_main_option("sqlalchemy.url", config.settings.database_uri)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: command.upgrade(alembic_cfg, "head"))


async def get_session() -> AsyncGenerator[AsyncSession]:
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session


# Base class for all models
class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = (
        True  # The class is abstract so that you don't have to create a separate table for it
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(self) -> str:
        return self.__name__.lower() + "s"
