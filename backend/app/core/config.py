from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration with environment-driven settings.
    Secrets must be set via environment variables and are never hardcoded.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.test", "../.env", "../.env.test"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "BrandProof AI"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    # Supabase credentials (populated via environment)
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWKS_URL: str | None = None
    DATABASE_URL: str | None = None
    SUPABASE_STORAGE_BUCKET: str = "brandproof-guidelines-assets"

    @property
    def effective_jwks_url(self) -> str | None:
        if self.SUPABASE_JWKS_URL:
            return self.SUPABASE_JWKS_URL
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    # Google Gemini API key (Backend ONLY)
    GEMINI_API_KEY: str | None = None
    GEMINI_TEXT_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Feature flags
    FEATURE_TONE_ANALYSIS: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT.lower() == "testing"


@lru_cache
def get_settings() -> Settings:
    return Settings()
