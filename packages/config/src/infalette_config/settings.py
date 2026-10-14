"""Pydantic settings for all environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str | None:
    """Locate the active ``.env`` file.

    pydantic-settings resolves ``env_file`` relative to the *current
    working directory*, not the file that defined the settings. That
    means ``alembic`` (which runs from ``packages/database/``) and
    ``uvicorn`` (which runs from ``apps/api/``) need different cwd-relative
    paths even though they're loading the same config. We centralize the
    lookup here: search the cwd first, then walk up looking for the
    nearest ``.env`` (skipping nested duplicates), and fall back to
    ``None`` if nothing is found so the model still loads from the
    process env.
    """
    import os

    # Explicit override: INFALETTE_ENV_FILE=/dev/null (or an empty value)
    # makes the loader ignore any discovered .env — used by scripts/tests
    # that must run on an ephemeral DB even when a developer .env exists.
    override = os.environ.get("INFALETTE_ENV_FILE")
    if override is not None:
        return override.strip() or None

    cwd = Path.cwd()
    # 1. cwd-relative .env (works when launched from a directory that
    #    has one, e.g. repo root or apps/api/).
    candidate = cwd / ".env"
    if candidate.is_file():
        return str(candidate)
    # 2. Walk up to the filesystem root looking for a .env.
    for parent in cwd.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    # 3. Hardcoded fallback for the monorepo layout. The backend env
    #    file always lives here regardless of where the process is
    #    launched.
    repo_root = Path(__file__).resolve()
    for _ in range(6):  # this file is packages/config/src/infalette_config/settings.py
        repo_root = repo_root.parent
    fallback = repo_root / "apps" / "api" / ".env"
    if fallback.is_file():
        return str(fallback)
    # 4. Last resort: process env vars only.
    if os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_POOLED"):
        return None
    return None


_ENV_FILE = _find_env_file()


class DatabaseSettings(BaseSettings):
    """Database connection settings.

    Two DSNs are supported because Neon exposes separate endpoints:

    * ``pooled_url`` (env ``DATABASE_URL_POOLED``) — transaction-mode pooled
      endpoint. Used by the API and workers for all runtime queries.
    * ``direct_url`` (env ``DATABASE_URL_DIRECT``) — direct (non-pooled)
      endpoint. Used ONLY by Alembic for migrations; DDL does not survive
      the transaction-mode pooler reliably.

    ``url`` resolves at read-time: prefers ``pooled_url``, falls back to the
    legacy ``DATABASE_URL`` for tools that don't distinguish. Keep using
    ``database.url`` in code that just needs "the runtime DSN" (API, workers,
    tests). Use ``database.direct_url`` for the migration runner.
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Runtime DSN (pooled in production; falls back to DATABASE_URL for local
    # dev with docker-compose.local.yml).
    url: str = Field(
        default="postgresql+asyncpg://infalette:infalette@localhost:5432/infalette",
        validation_alias="DATABASE_URL",
    )
    pooled_url: str | None = Field(default=None, validation_alias="DATABASE_URL_POOLED")
    direct_url: str | None = Field(default=None, validation_alias="DATABASE_URL_DIRECT")

    host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    user: str = Field(default="infalette", validation_alias="POSTGRES_USER")
    password: str = Field(default="infalette", validation_alias="POSTGRES_PASSWORD")
    db: str = Field(default="infalette", validation_alias="POSTGRES_DB")
    pool_size: int = Field(default=20)
    max_overflow: int = Field(default=30)
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=3600)

    def resolved_url(self) -> str:
        """Return the runtime DSN.

        Prefers ``DATABASE_URL_POOLED`` (Neon pooled) and falls back to
        ``DATABASE_URL``. Kept as a method so callers can opt into the new
        behavior without breaking anyone reading ``.url`` directly.
        """
        if self.pooled_url:
            return self.pooled_url
        return self.url

    def migration_url(self) -> str:
        """Return the DSN for Alembic migrations.

        Prefers ``DATABASE_URL_DIRECT`` (Neon direct endpoint), then
        ``DATABASE_URL``. Never go through the pooler for DDL.
        """
        if self.direct_url:
            return self.direct_url
        return self.url

    @property
    def use_neon(self) -> bool:
        """True when the runtime DSN targets a Neon host."""
        dsn = self.resolved_url()
        return "neon.tech" in dsn or "neon.build" in dsn


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    db: int = Field(default=0)
    password: str | None = None
    decode_responses: bool = True


class AuthSettings(BaseSettings):
    """Authentication settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    secret_key: SecretStr = Field(
        default=SecretStr("change-me-to-a-long-random-string"),
        validation_alias="SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=7, validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )
    mfa_enabled: bool = Field(default=True, validation_alias="MFA_ENABLED")
    # Roles that must enroll in and verify MFA (spec §5: "MFA for admins").
    # Comma-separated role names; empty string disables enforcement.
    mfa_required_roles: str = Field(
        default="platform_owner,tenant_owner,store_manager",
        validation_alias="MFA_REQUIRED_ROLES",
    )
    bcrypt_rounds: int = Field(default=12)


class PaymentSettings(BaseSettings):
    """Payment provider settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    razorpay_key_id: str | None = Field(default=None, validation_alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: SecretStr | None = Field(
        default=None, validation_alias="RAZORPAY_KEY_SECRET"
    )
    razorpay_webhook_secret: str | None = Field(
        default=None, validation_alias="RAZORPAY_WEBHOOK_SECRET"
    )
    stripe_secret_key: SecretStr | None = Field(
        default=None, validation_alias="STRIPE_SECRET_KEY"
    )
    stripe_webhook_secret: str | None = Field(
        default=None, validation_alias="STRIPE_WEBHOOK_SECRET"
    )
    stripe_connect_client_id: str | None = Field(
        default=None, validation_alias="STRIPE_CONNECT_CLIENT_ID"
    )


class SocialSettings(BaseSettings):
    """Social API settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    instagram_client_id: str | None = Field(
        default=None, validation_alias="INSTAGRAM_CLIENT_ID"
    )
    instagram_client_secret: SecretStr | None = Field(
        default=None, validation_alias="INSTAGRAM_CLIENT_SECRET"
    )
    instagram_redirect_uri: str | None = Field(
        default=None, validation_alias="INSTAGRAM_REDIRECT_URI"
    )
    instagram_webhook_secret: str | None = Field(
        default=None, validation_alias="INSTAGRAM_WEBHOOK_SECRET"
    )
    instagram_verify_token: str | None = Field(
        default=None,
        validation_alias="INSTAGRAM_VERIFY_TOKEN",
        description="Meta webhook subscription verify token (falls back to client id)",
    )
    whatsapp_token: str | None = Field(default=None, validation_alias="WHATSAPP_TOKEN")
    whatsapp_phone_number_id: str | None = Field(
        default=None, validation_alias="WHATSAPP_PHONE_NUMBER_ID"
    )
    whatsapp_webhook_secret: str | None = Field(
        default=None, validation_alias="WHATSAPP_WEBHOOK_SECRET"
    )
    whatsapp_verify_token: str | None = Field(
        default=None, validation_alias="WHATSAPP_VERIFY_TOKEN"
    )


class EmailSettings(BaseSettings):
    """Email provider settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    provider: str = Field(default="ses", validation_alias="EMAIL_PROVIDER")
    from_address: str = Field(default="noreply@infalette.com", validation_alias="EMAIL_FROM")
    aws_access_key_id: str | None = Field(
        default=None, validation_alias="AWS_ACCESS_KEY_ID"
    )
    aws_secret_access_key: SecretStr | None = Field(
        default=None, validation_alias="AWS_SECRET_ACCESS_KEY"
    )
    aws_region: str = Field(default="ap-south-1", validation_alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, validation_alias="S3_BUCKET")
    s3_endpoint: str | None = Field(default=None, validation_alias="S3_ENDPOINT")
    # SMTP fallback (used when provider == "smtp"); stdlib smtplib, no extra deps
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")


class SmsSettings(BaseSettings):
    """SMS provider settings."""
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    provider: str = Field(default="msg91", validation_alias="SMS_PROVIDER")
    api_key: SecretStr | None = Field(default=None, validation_alias="SMS_API_KEY")
    sender_id: str | None = Field(default=None, validation_alias="SMS_SENDER_ID")
    endpoint_url: str | None = Field(default=None, validation_alias="SMS_ENDPOINT_URL")
    enabled: bool = Field(default=False, validation_alias="SMS_ENABLED")


class ShippingSettings(BaseSettings):
    """Shipping carrier settings (DTDC/Delhivery/Blue Dart/Ecom Express)."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    api_key: SecretStr | None = Field(default=None, validation_alias="SHIPPING_API_KEY")
    provider: str = Field(default="dtdc", validation_alias="SHIPPING_PROVIDER")


class PosthogSettings(BaseSettings):
    """PostHog product analytics settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    api_key: str | None = Field(default=None, validation_alias="POSTHOG_API_KEY")
    host: str = Field(
        default="https://app.posthog.com", validation_alias="POSTHOG_HOST"
    )
    enabled: bool = Field(default=False, validation_alias="POSTHOG_ENABLED")


class S3Settings(BaseSettings):
    """S3 media storage settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    bucket: str | None = Field(default=None, validation_alias="S3_BUCKET")
    region: str = Field(default="ap-south-1", validation_alias="S3_REGION")
    # Fallback to AWS_REGION if S3_REGION not set — handled via property
    endpoint: str | None = Field(default=None, validation_alias="S3_ENDPOINT")
    cloudfront_domain: str | None = Field(
        default=None, validation_alias="CLOUDFRONT_DOMAIN"
    )
    presigned_expiry: int = Field(default=3600, validation_alias="S3_PRESIGNED_EXPIRY")
    max_upload_bytes: int = Field(
        default=10 * 1024 * 1024, validation_alias="S3_MAX_UPLOAD_BYTES"
    )
    # Optional: if using S3-compatible endpoint (MinIO) or custom
    force_path_style: bool = Field(default=False, validation_alias="S3_FORCE_PATH_STYLE")


class BotSettings(BaseSettings):
    """Bot protection settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    enabled: bool = Field(default=True, validation_alias="BOT_PROTECTION_ENABLED")
    # Header-based simple bot flag check (X-Bot header)
    check_x_bot_header: bool = Field(default=True, validation_alias="BOT_CHECK_X_BOT_HEADER")
    # reCAPTCHA verification
    recaptcha_secret_key: str | None = Field(
        default=None, validation_alias="RECAPTCHA_SECRET_KEY"
    )
    recaptcha_site_key: str | None = Field(
        default=None, validation_alias="RECAPTCHA_SITE_KEY"
    )
    recaptcha_header: str = Field(
        default="X-Recaptcha-Token", validation_alias="RECAPTCHA_HEADER"
    )
    recaptcha_min_score: float = Field(default=0.5, validation_alias="RECAPTCHA_MIN_SCORE")
    # Simple rate limiting for bots / per-IP
    rate_limit_requests: int = Field(default=60, validation_alias="BOT_RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(
        default=60, validation_alias="BOT_RATE_LIMIT_WINDOW"
    )
    block_unknown_bots: bool = Field(default=False, validation_alias="BOT_BLOCK_UNKNOWN")
    # Paths to exempt from bot checks (health, webhooks, docs)
    exempt_paths: list[str] = Field(
        default=["/health", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi", "/webhooks"],
    )


class OtelSettings(BaseSettings):
    """OpenTelemetry observability settings."""
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    enabled: bool = Field(default=False, validation_alias="OTEL_ENABLED")
    endpoint: str | None = Field(
        default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    service_name: str = Field(default="infalette-api", validation_alias="OTEL_SERVICE_NAME")
    traces_sampler_ratio: float = Field(
        default=0.1, validation_alias="OTEL_TRACES_SAMPLER_RATIO"
    )
    # Additional otel env vars are supported via otel-collector.yaml;
    # keep collector endpoint and sentry DSN referenced here for app wiring.
    exporter_protocol: str = Field(default="grpc", validation_alias="OTEL_EXPORTER_OTLP_PROTOCOL")
    insecure: bool = Field(default=True, validation_alias="OTEL_EXPORTER_OTLP_INSECURE")


class ClerkSettings(BaseSettings):
    """Clerk authentication settings.

    Frontend needs NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY; backend verifies
    Clerk session JWTs (RS256 via JWKS) and syncs users via webhooks.
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    secret_key: SecretStr | None = Field(default=None, validation_alias="CLERK_SECRET_KEY")
    publishable_key: str | None = Field(default=None, validation_alias="CLERK_PUBLISHABLE_KEY")
    # e.g. https://<your-clerk-domain>/.well-known/jwks.json — derived from
    # the publishable key's domain when unset (see infalette_auth.clerk).
    jwks_url: str | None = Field(default=None, validation_alias="CLERK_JWKS_URL")
    # Signing secret for the user-sync webhook (Svix). Endpoint:
    # POST /api/v1/webhooks/clerk
    webhook_secret: SecretStr | None = Field(default=None, validation_alias="CLERK_WEBHOOK_SECRET")

    @property
    def enabled(self) -> bool:
        return bool(self.secret_key and self.publishable_key)


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Infalette"
    app_env: str = Field(default="development", validation_alias="NODE_ENV")
    debug: bool = Field(default=True, validation_alias="DEBUG")
    api_url: str = Field(default="http://localhost:8000", validation_alias="API_URL")
    storefront_url: str = Field(
        default="http://localhost:3000", validation_alias="STOREFRONT_URL"
    )
    admin_url: str = Field(default="http://localhost:3001", validation_alias="ADMIN_URL")
    platform_admin_url: str = Field(
        default="http://localhost:3002", validation_alias="PLATFORM_ADMIN_URL"
    )
    rate_limit_per_minute: int = Field(
        default=60, validation_alias="RATE_LIMIT_PER_MINUTE"
    )
    rate_limit_fail_closed: bool = Field(
        default=False,
        validation_alias="RATE_LIMIT_FAIL_CLOSED",
        description="When true, return 503 if Redis is unavailable instead of skipping limits.",
    )

    # Observability
    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    otel_endpoint: str | None = Field(
        default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    posthog_api_key: str | None = Field(
        default=None, validation_alias="POSTHOG_API_KEY"
    )
    posthog_host: str | None = Field(default=None, validation_alias="POSTHOG_HOST")

    # CORS
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
        validation_alias="ALLOWED_ORIGINS",
    )

    # Nested settings
    database: DatabaseSettings = DatabaseSettings()

    redis: RedisSettings = RedisSettings()
    auth: AuthSettings = AuthSettings()
    payments: PaymentSettings = PaymentSettings()
    social: SocialSettings = SocialSettings()
    email: EmailSettings = EmailSettings()
    sms: SmsSettings = SmsSettings()
    shipping: ShippingSettings = ShippingSettings()
    s3: S3Settings = S3Settings()
    bot: BotSettings = BotSettings()
    otel: OtelSettings = OtelSettings()
    posthog: PosthogSettings = PosthogSettings()
    clerk: ClerkSettings = ClerkSettings()

    # Backward-compat helpers: resolve S3 region fallback to AWS_REGION if S3_REGION not explicitly set
    def s3_region_effective(self) -> str:
        """Return effective S3 region (S3_REGION or AWS_REGION)."""
        # If S3_REGION env was not set, S3Settings.region falls back to default ap-south-1;
        # we want to prefer AWS_REGION when S3_REGION is default and AWS_REGION differs.
        import os

        if os.getenv("S3_REGION"):
            return self.s3.region
        return self.email.aws_region or self.s3.region


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
