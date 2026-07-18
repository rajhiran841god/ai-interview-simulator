"""
Central config. All secrets come from environment variables — never
hardcoded, never committed. See .env.example for required keys.

Provider independence (Decision Log #002, Architecture Review Gate #3):
Supabase and Claude are today's choices, not permanent ones. Nothing
outside this file should import provider SDKs directly — route through
app/services/ instead, so swapping a provider later means editing here
and in one service module, not hunting through business logic.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # AI provider (Interview Intelligence Engine — Milestone 2 will consume this,
    # not this milestone. Present here so the config surface is ready.)
    ANTHROPIC_API_KEY: str = ""

    # App
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
