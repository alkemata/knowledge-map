from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    public_origin: str = "http://localhost:8080"
    database_url: str = "postgresql+psycopg://knowledge:knowledge@db/knowledge"
    session_secret: str = "development-only-change-me"
    asset_root: Path = Path("/data/assets")
    allowed_origins: str = "http://localhost:8080"
    trusted_proxy_cidrs: str = "127.0.0.1/32"
    mcp_enabled: bool = True
    mcp_write_enabled: bool = False
    log_level: str = "INFO"
    session_ttl_hours: int = 24
    max_upload_bytes: int = 10 * 1024 * 1024
    oidc_issuer: str = ""
    oidc_browser_client_id: str = ""
    oidc_browser_client_secret: str = ""
    oidc_mcp_audience: str = ""
    oidc_mcp_enforce: bool = False

    @field_validator("public_origin")
    @classmethod
    def no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]

    @property
    def mcp_allowed_hosts(self) -> list[str]:
        host = urlsplit(self.public_origin).netloc
        values = [host, f"{host}:*"] if host else []
        return values + ["localhost:*", "127.0.0.1:*"]

    @property
    def mcp_allowed_origins(self) -> list[str]:
        return self.origins + ["http://localhost:*", "http://127.0.0.1:*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
