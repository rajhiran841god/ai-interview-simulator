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

    # Provider selection: "anthropic" (real, direct — default) or
    # "gateway" (validation-only, third-party OpenAI-compatible proxy).
    # Set in your OWN .env, never shared in chat. See provider_adapter.py.
    LLM_PROVIDER: str = "anthropic"
    GATEWAY_API_KEY: str = ""
    GATEWAY_BASE_URL: str = ""
    GATEWAY_MODEL: str = "claude-3-5-sonnet-20241022"

    # App
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    ENVIRONMENT: str = "development"

    # Voice interface (Decision Log #004) — set in your OWN .env, never
    # shared in chat. LIVEKIT_URL is the WebSocket URL the frontend
    # client connects to (e.g. wss://your-project.livekit.cloud).
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # Engine store backend: "postgres" (real, persistent, default —
    # required for voice, since the FastAPI backend and the LiveKit
    # voice worker are separate processes and need shared state) or
    # "memory" (in-process only — used by the offline test suite so
    # it never needs real Supabase connectivity).
    STORE_BACKEND: str = "postgres"

    class Config:
        env_file = ".env"
        # Real bug found during live voice setup: pydantic-settings
        # rejects any .env variable not declared as a field here by
        # default. DEEPGRAM_API_KEY and ELEVEN_API_KEY are legitimately
        # read directly by their respective LiveKit plugin packages
        # (via os.environ, not through this Settings class) — they
        # don't belong here as fields, but must not cause a startup
        # crash either. "ignore" lets any such extra variable pass
        # through untouched.
        extra = "ignore"


settings = Settings()
