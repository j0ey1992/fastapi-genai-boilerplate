"""Configuration settings for the application"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import AppEnvs, CacheBackend, LogLevel, RateLimitBackend


class AppConfig(BaseSettings):
    """Primary configuration settings for the application."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    LOG_LEVEL: LogLevel = LogLevel.TRACE
    RELEASE_VERSION: str = "0.0.1"
    ENVIRONMENT: AppEnvs = AppEnvs.DEVELOPMENT
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    WORKER_COUNT: int | None = None
    ENV_FILE: str = ".env"
    API_PREFIX: str = "boilerplate"

    # Cache
    CACHE_BACKEND: CacheBackend = CacheBackend.LOCAL

    # Rate Limit
    RATE_LIMIT_BACKEND: RateLimitBackend = RateLimitBackend.REDIS

    # Redis
    REDIS_HOST: str = ""
    REDIS_PORT: str = ""
    REDIS_PASSWORD: str = ""

    # OPENAI Model (legacy - transitioning to Gemini)
    OPENAI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Local Model (LM Studio)
    LOCAL_MODEL_URL: str = "http://127.0.0.1:1234"
    USE_LOCAL_MODEL: bool = False  # Default to OpenAI, can be overridden

    # Search Provider Configuration
    SEARCH_PROVIDER: str = "duckduckgo"  # "duckduckgo" or "tavily"
    DUCKDUCKGO_MAX_RESULTS: int = 10

    # Google Gemini Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_CHAT_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Qdrant Vector Database
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "voyage_policies"
    EMBEDDING_DIMENSION: int = 768  # Gemini text-embedding-004 dimension

    # PostgreSQL Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/voyage_policies"

    # LangFuse
    LANGFUSE_HOST: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""


# Initialize configuration settings
settings = AppConfig()
