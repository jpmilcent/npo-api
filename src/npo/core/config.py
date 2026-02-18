"""Application configuration settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Common application settings."""

    app_name: str = Field(
        default="Nature Photo Organizer API", description="Name of the application."
    )
    # Use same name for app_code as the root directory of this API in the src/ directory
    app_code: str = Field(
        default="npo", description="Code name for the application, used for directories."
    )
    environment: str = Field(
        default="production", description="Deployment environment (development, production, etc.)."
    )
    default_language: str = Field(default="en", description="Default language code.")


class BackendSettings(CommonSettings):
    """Backend application settings."""

    database_uri: str = Field(
        default="sqlite+aiosqlite:///npo.db", description="Database connection URI."
    )
    admin_email: str = Field(default="", description="Email address for the administrator.")
    uploads_dir: str = Field(default="", description="Directory for temporary uploads.")
    storage_dir: str = Field(default="", description="Directory for permanent storage.")
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."
    )
    logs_dir: str = Field(default="logs", description="Directory where log files are stored.")
    log_max_bytes: int = Field(
        default=10 * 1024 * 1024, description="Maximum size of a log file in bytes. Default: 10 MB."
    )
    log_backup_count: int = Field(default=5, description="Number of backup log files to keep.")
    hash_dir_parts_count: int = Field(
        default=6, description="Number of directory levels for hashed storage."
    )
    hash_dir_step: int = Field(default=2, description="Number of characters per directory level.")
    upload_safety_buffer: int = Field(
        default=50 * 1024 * 1024,
        description="Safety buffer size for uploads in bytes. Default: 50 MB.",
    )
    max_upload_size: int = Field(
        default=500 * 1024 * 1024,
        description="Maximum allowed upload size in bytes. Default: 500 MB.",
    )
    jwt_secret_key: str = Field(
        default="secret",
        description="Secret key for JWT token generation. Generate with: `openssl rand -hex 32`",
    )
    jwt_algorithm: str = Field(default="HS256", description="Algorithm used for JWT encoding.")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="JSON Web Token expiration time in minutes."
    )
    jwt_refresh_token_expire_minutes: int = Field(
        default=10080, description="Refresh Token expiration time in minutes (default 7 days)."
    )
    password_min_length: int = Field(default=8, description="Minimum length for passwords.")
    google_client_id: str = Field(default="", description="Google OAuth2 Client ID.")
    google_client_secret: str = Field(default="", description="Google OAuth2 Client Secret.")
    github_client_id: str = Field(default="", description="GitHub OAuth2 Client ID.")
    github_client_secret: str = Field(default="", description="GitHub OAuth2 Client Secret.")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")

    @property
    def oauth_configs(self) -> dict:
        return {
            "google": {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
                "client_kwargs": {"scope": "openid email profile"},
            },
            "github": {
                "client_id": self.github_client_id,
                "client_secret": self.github_client_secret,
                "access_token_url": "https://github.com/login/oauth/access_token",
                "authorize_url": "https://github.com/login/oauth/authorize",
                "api_base_url": "https://api.github.com/",
                "userinfo_endpoint": "https://api.github.com/user",
                "client_kwargs": {"scope": "user:email"},
            },
        }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        if v.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Log level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return v.upper()

    @field_validator("log_max_bytes", "upload_safety_buffer", "max_upload_size", mode="before")
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

    zoom_max: int = Field(default=4, description="Maximum zoom level for images.")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="npo_", extra="ignore")


class AppSettings(BackendSettings, FrontendSettings):
    """Combined application settings."""


backend_settings = BackendSettings()
frontend_settings = FrontendSettings()
settings = AppSettings()
