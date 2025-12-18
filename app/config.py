from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    redis_url: str | None = None  # e.g. redis://localhost:6379/0
    api_key_pepper: str = "change-me"  # used when hashing API keys


settings = Settings()


