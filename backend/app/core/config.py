from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_ignore_empty=True, extra="ignore")

    # App
    app_env: str = "dev"
    log_level: str = "INFO"
    backend_public_base_url: str = "http://localhost:8000"
    cors_allow_origins_csv: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/zeitgeist"
    db_auto_create: bool = True  # for local/dev convenience; prefer Alembic in prod

    # Celery/Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM (OpenAI-compatible)
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_embeddings_model: str = "text-embedding-3-small"

    # Collectors (optional; missing creds => skipped)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "zeitgeist-rsa-agent/0.1"
    reddit_username: str | None = None
    reddit_password: str | None = None
    reddit_use_praw: bool = False

    x_bearer_token: str | None = None

    youtube_api_key: str | None = None

    # QA/policy
    qa_risky_terms_csv: str = "guarantee,guaranteed,100%,cure,miracle,instant,overnight,no risk,free money,legal advice,medical advice"
    qa_trademarks_csv: str = ""  # optional comma-separated list to avoid in RSA copy

    # Google Ads
    google_ads_developer_token: str | None = None
    google_ads_refresh_token: str | None = None
    google_ads_client_id: str | None = None
    google_ads_client_secret: str | None = None
    google_ads_login_customer_id: str | None = None


settings = Settings()

