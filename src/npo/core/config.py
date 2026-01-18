"""Application configuration settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Common application settings."""

    app_name: str = "Nature Photo Organizer API"
    # Use same name for app_code as the root directory of this API in the src/ directory
    app_code: str = "npo"
    environment: str = "production"
    default_language: str = "en"


class BackendSettings(CommonSettings):
    """Backend application settings."""

    database_uri: str
    admin_email: str
    uploads_dir: str
    storage_dir: str
    log_level: str = "INFO"
    logs_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5
    hash_dir_parts_count: int = 6
    hash_dir_step: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        if v.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Log level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return v.upper()

    @field_validator("log_max_bytes", mode="before")
    @classmethod
    def parse_human_readable_size(cls, v: str | int) -> int:
        if isinstance(v, int):
            return v

        v_str = str(v).strip().upper()
        if v_str.isdigit():
            return int(v_str)

        units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

        # Trie les unités par longueur décroissante pour matcher "MB" avant "B"
        for unit, multiplier in sorted(units.items(), key=lambda x: len(x[0]), reverse=True):
            if v_str.endswith(unit):
                try:
                    number_part = v_str[: -len(unit)].strip()
                    return int(float(number_part) * multiplier)
                except ValueError:
                    pass

        raise ValueError(f"Invalid size format: {v}. Expected format like '10MB', '1GB'.")

    @field_validator("uploads_dir", "storage_dir", "logs_dir")
    @classmethod
    def ensure_trailing_slash(cls, v: str) -> str:
        if v and not v.endswith("/"):
            return f"{v}/"
        return v


class FrontendSettings(CommonSettings):
    """Frontend application settings."""

    zoom_max: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")


class AppSettings(BackendSettings, FrontendSettings):
    """Combined application settings."""


backend_settings = BackendSettings()
frontend_settings = FrontendSettings()
settings = AppSettings()
