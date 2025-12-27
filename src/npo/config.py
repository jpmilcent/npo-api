"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Common application settings."""

    app_name: str = "Nature Photo Organizer API"


class BackendSettings(CommonSettings):
    """Backend application settings."""

    database_uri: str
    admin_email: str
    uploads_dir: str
    storage_dir: str
    hash_dir_parts_count: int = 6
    hash_dir_step: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")


class FrontendSettings(CommonSettings):
    """Frontend application settings."""

    zoom_max: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")


class AppSettings(BackendSettings, FrontendSettings):
    """Combined application settings."""


backend_settings = BackendSettings()
frontend_settings = FrontendSettings()
settings = AppSettings()
