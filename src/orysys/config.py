from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORYSYS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    use_fake_adapters: bool = True
    cloudflare_account_id: str | None = Field(
        default=None, validation_alias="CLOUDFLARE_ACCOUNT_ID"
    )
    cloudflare_api_token: SecretStr | None = Field(
        default=None, validation_alias="CLOUDFLARE_API_TOKEN"
    )
    cloudflare_ai_gateway_id: str | None = Field(
        default=None, validation_alias="CLOUDFLARE_AI_GATEWAY_ID"
    )
    cloudflare_embedding_model: str = Field(
        default="@cf/qwen/qwen3-embedding-0.6b",
        validation_alias="CLOUDFLARE_EMBEDDING_MODEL",
    )
    cloudflare_embedding_dimensions: int = Field(
        default=1024,
        ge=1,
        validation_alias="CLOUDFLARE_EMBEDDING_DIMENSIONS",
    )
    pinecone_api_key: SecretStr | None = Field(default=None, validation_alias="PINECONE_API_KEY")
    pinecone_index: str | None = Field(default=None, validation_alias="PINECONE_INDEX")
    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: SecretStr | None = Field(default=None, validation_alias="REDIS_URL")

    def require_ingestion_credentials(self) -> None:
        required = {
            "CLOUDFLARE_ACCOUNT_ID": self.cloudflare_account_id,
            "CLOUDFLARE_API_TOKEN": self.cloudflare_api_token,
            "PINECONE_API_KEY": self.pinecone_api_key,
            "PINECONE_INDEX": self.pinecone_index,
        }
        missing = sorted(name for name, value in required.items() if value is None)
        if missing:
            raise ValueError(f"Missing ingestion settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
