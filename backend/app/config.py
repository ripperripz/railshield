from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAILSHIELD_", env_file=".env", extra="ignore")
    environment: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./railshield.db"
    api_key: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_body_bytes: int = 2_000_000
    max_pending_jobs: int = 20
    job_lease_seconds: int = 900

    @model_validator(mode="after")
    def production(self):
        if self.environment == "production":
            if len(self.api_key) < 32 or self.api_key.startswith("replace-"):
                raise ValueError("Production requires RAILSHIELD_API_KEY of at least 32 characters")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL")
            if "*" in self.cors_origins:
                raise ValueError("Production requires explicit CORS origins")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
