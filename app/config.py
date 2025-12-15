from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    ADMIN_KEY: str = Field(...)

    DATABASE_URL: str = Field(...)
    REDIS_URL: str = Field(...)

    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    PROXY_CONFIG_PATH: str = "/app/concord.config.yaml"

settings = Settings()
