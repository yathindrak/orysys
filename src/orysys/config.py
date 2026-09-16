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
    demo_subject: str = "assessment-user"
    demo_tenant_id: str = "commercial-bank"
    demo_role: Literal["viewer", "analyst", "administrator"] = "analyst"
    demo_departments: str = "payments"
    demo_clearance: int = Field(default=2, ge=0, le=10)
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
    cloudflare_chat_model: str = Field(
        default="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        validation_alias="CLOUDFLARE_CHAT_MODEL",
    )
    cloudflare_chat_max_tokens: int = Field(
        default=4096, ge=1, validation_alias="CLOUDFLARE_CHAT_MAX_TOKENS"
    )
    pinecone_api_key: SecretStr | None = Field(default=None, validation_alias="PINECONE_API_KEY")
    pinecone_index: str | None = Field(default=None, validation_alias="PINECONE_INDEX")
    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: SecretStr | None = Field(default=None, validation_alias="REDIS_URL")
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="orysys-development", validation_alias="LANGSMITH_PROJECT"
    )
    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")

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

    def require_chat_credentials(self) -> None:
        required = {
            "CLOUDFLARE_ACCOUNT_ID": self.cloudflare_account_id,
            "CLOUDFLARE_API_TOKEN": self.cloudflare_api_token,
        }
        missing = sorted(name for name, value in required.items() if value is None)
        if missing:
            raise ValueError(f"Missing chat settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
