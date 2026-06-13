from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Insight Notebook API"
    app_version: str = "0.1.0"
    environment: str = "local"

    postgres_dsn: str = "postgresql://insight:insight@localhost:5432/insight"
    opensearch_url: str = "http://localhost:9200"
    s3_endpoint_url: str = "http://localhost:8333"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="INSIGHT_")


settings = Settings()

