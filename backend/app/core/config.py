from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "Insight Notebook API"
    app_version: str = "0.1.0"
    environment: str = "local"

    postgres_dsn: str = "postgresql://insight:insight@localhost:5432/insight"
    opensearch_url: str = "http://localhost:9200"
    s3_endpoint_url: str = "http://localhost:8333"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")


settings = Settings(
    app_name=getenv("INSIGHT_APP_NAME", "Insight Notebook API"),
    app_version=getenv("INSIGHT_APP_VERSION", "0.1.0"),
    environment=getenv("INSIGHT_ENVIRONMENT", "local"),
    postgres_dsn=getenv("INSIGHT_POSTGRES_DSN", "postgresql://insight:insight@localhost:5432/insight"),
    opensearch_url=getenv("INSIGHT_OPENSEARCH_URL", "http://localhost:9200"),
    s3_endpoint_url=getenv("INSIGHT_S3_ENDPOINT_URL", "http://localhost:8333"),
    cors_origins=tuple(
        origin.strip()
        for origin in getenv(
            "INSIGHT_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ),
)
