import warnings
from typing import Literal, Self

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn
    TEST_DATABASE_URL: PostgresDsn | None = None

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn | None) -> str | None:
        if value is None:
            return None
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # Map layer providers (one vendor may serve several domains)
    GEOCODING_PROVIDER: Literal["tomtom"] = "tomtom"
    ROUTING_PROVIDER: Literal["tomtom"] = "tomtom"
    TRAFFIC_PROVIDER: Literal["tomtom", "off"] = "tomtom"
    FUEL_PROVIDER: Literal["internal", "here", "off"] = "internal"
    TRUCK_RESTRICTION_PROVIDER: Literal["internal"] = "internal"
    REST_AREAS_PROVIDER: Literal["here"] = "here"

    # TomTom configuration (routing + traffic)
    TOMTOM_API_KEY: str | None = None
    TOMTOM_BASE_URL: str = "https://api.tomtom.com"
    TOMTOM_API_VERSION: str = "3"
    TOMTOM_TIMEOUT_SECONDS: int = 30

    # Internal fuel station catalog import settings.
    # When FUEL_PROVIDER=internal, route searches run locally against PostGIS;
    # these values are only relevant for optional upstream ingest workflows.
    FUEL_API_BASE_URL: str | None = None
    FUEL_API_KEY: str | None = None
    FUEL_API_TIMEOUT_SECONDS: int = 15

    # HERE Fuel Prices API (fuel stations along route, backend only)
    HERE_FUEL_BASE_URL: str = "https://fuel.hereapi.com"
    HERE_FUEL_CORRIDOR_WIDTH: int = 1000
    HERE_FUEL_LIMIT: int = 1000

    # PumpPrice import API (admin ingest only)
    PUMPPRICE_BASE_URL: str = "https://www.pumpprice.co"
    PUMPPRICE_TIMEOUT_SECONDS: int = 30

    # Internal truck restriction API
    TRUCK_RESTRICTION_API_BASE_URL: str | None = None
    TRUCK_RESTRICTION_API_KEY: str | None = None
    TRUCK_RESTRICTION_API_TIMEOUT_SECONDS: int = 15

    # HERE Search API (rest areas along a TomTom route)
    HERE_API_KEY: str | None = None
    HERE_BASE_URL: str = "https://browse.search.hereapi.com"
    HERE_TIMEOUT_SECONDS: int = 30
    HERE_POI_CORRIDOR_WIDTH_METERS: int = 1000
    HERE_POI_LIMIT: int = 100
    HERE_POI_CACHE_TTL_SECONDS: int = 86400
    HERE_POI_USE_EXCURSION_DISTANCE_RANKING: bool = False

    # Per-domain cache TTLs (lazy invalidation on read)
    GEOCODING_CACHE_TTL_SECONDS: int = 2_592_000  # 30 days
    ROUTE_CALCULATION_CACHE_TTL_SECONDS: int = 3600  # 1 hour
    TRAFFIC_CACHE_TTL_SECONDS: int = 120  # 2 minutes
    FUEL_CACHE_TTL_SECONDS: int = 86400  # 1 day
    TRUCK_RESTRICTION_CACHE_TTL_SECONDS: int = 604800  # 1 week

    # Map overview defaults
    MAP_LAYER_RADIUS_METERS: int = 5000
    MAP_LAYER_RESULT_LIMIT: int = 5000

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _validate_routing_config(self) -> Self:
        # In development, allow missing TOMTOM_API_KEY, but warn
        # Note: "off" providers don't require API keys
        uses_tomtom = any(
            provider == "tomtom"
            for provider in (
                self.GEOCODING_PROVIDER,
                self.ROUTING_PROVIDER,
                self.TRAFFIC_PROVIDER,
            )
        )
        if uses_tomtom and not self.TOMTOM_API_KEY:
            if self.FASTAPI_ENV == "development":
                warnings.warn(
                    "TOMTOM_API_KEY is not set. TomTom-backed geocoding/routing APIs will not work until configured.",
                    stacklevel=1,
                )
            else:
                raise ValueError(
                    "TOMTOM_API_KEY is required when a TomTom-backed provider is enabled"
                )
        return self

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
