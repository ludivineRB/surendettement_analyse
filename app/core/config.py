from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "surendettement-macro-api"
    APP_VERSION: str = "0.1.0"
    ANALYTICS_DB_PATH: str = "data/processed/analytics/surendettement_macro_analytics.db"
    ANALYTICS_DATABASE_URL: str | None = None


settings = Settings()
