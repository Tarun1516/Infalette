"""Infalette FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from infalette_config import get_settings
from infalette_config.logging import configure_logging

from infalette_auth.middleware import AuthMiddleware

# Observability:
# - Structured logging is configured via infalette_config/logging.py (structlog + JSON)
# - Sentry config lives in infrastructure/monitoring/sentry.yaml (DSN via env SENTRY_DSN)
# - OTEL Collector config lives in infrastructure/monitoring/otel-collector.yaml (endpoint via OTEL_EXPORTER_OTLP_ENDPOINT)
# This module wires both at runtime.

# API version
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()
    configure_logging(debug=settings.debug)

    # Initialize database
    from infalette_database.session import init_db
    await init_db()

    # Initialize Sentry
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )

    # Initialize OpenTelemetry (if configured)
    # OTEL endpoint can come from top-level `otel_endpoint` or nested `otel.endpoint`
    # Config example: infrastructure/monitoring/otel-collector.yaml
    otel_endpoint = getattr(settings, "otel_endpoint", None) or getattr(getattr(settings, "otel", None), "endpoint", None)
    otel_enabled = getattr(getattr(settings, "otel", None), "enabled", False) or bool(otel_endpoint)
    if otel_enabled and otel_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            service_name = getattr(getattr(settings, "otel", None), "service_name", "infalette-api")
            resource = Resource.create({"service.name": service_name, "service.version": "0.1.0", "deployment.environment": settings.app_env})
            provider = TracerProvider(resource=resource)
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True))
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning("OTEL init failed (optional): %s", e)

    # Event-driven CRM stage progression (spec §3 pipeline)
    try:
        from apps.api.modules.crm_listeners import register_crm_listeners

        register_crm_listeners()
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("CRM listeners init failed (optional): %s", e)

    yield

    # Cleanup
    from infalette_database.session import get_engine
    engine = get_engine()
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory function creating the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Infalette API",
        description="Multi-tenant, headless commerce SaaS for influencers",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    # Middleware - order matters (last added is outermost)
    # AuthMiddleware MUST run before IdempotencyMiddleware so tenant scoping
    # is available when building the idempotency cache key.
    # Starlette: last added = outermost, so we add Idempotency FIRST (innermost)
    # then RateLimit, RequestID, CORSMiddleware, Audit, Auth, Sentry outermost.
    from apps.api.core.idempotency import IdempotencyMiddleware
    from apps.api.core.middleware import RateLimitMiddleware, RequestIDMiddleware
    from apps.api.core.audit import AuditMiddleware
    from apps.api.core.bot_protection import BotProtectionMiddleware

    app.add_middleware(IdempotencyMiddleware)  # innermost, closest to handler
    app.add_middleware(RateLimitMiddleware, requests_per_minute=getattr(settings, "rate_limit_per_minute", 60))
    app.add_middleware(BotProtectionMiddleware)  # bot checks + stricter rate limit for bots
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditMiddleware)  # logs POST/PATCH/DELETE after auth
    app.add_middleware(AuthMiddleware)  # must wrap Idempotency for tenant scoping
    app.add_middleware(SentryAsgiMiddleware)  # outermost

    # Register exception handlers
    from apps.api.core.exceptions import register_exception_handlers
    register_exception_handlers(app)

    # OpenAPI customization: bearerAuth security scheme in /docs.
    # Installed before routers so the schema is generated lazily, after
    # all routes exist.
    from apps.api.core.openapi import install_openapi_customization
    install_openapi_customization(app)

    # Health check
    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/health/detailed", tags=["health"])
    async def health_detailed():
        """Component-level health: database and Redis connectivity."""
        components = {"database": "unknown", "redis": "unknown"}
        try:
            from infalette_database.session import get_engine
            from sqlalchemy import text

            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            components["database"] = "healthy"
        except Exception as e:
            components["database"] = f"error: {e.__class__.__name__}"

        try:
            from infalette_config import get_settings as _gs
            import redis.asyncio as aioredis

            r = aioredis.from_url(_gs().redis.url, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            components["redis"] = "healthy"
        except Exception as e:
            components["redis"] = f"error: {e.__class__.__name__}"

        healthy = all(v == "healthy" for v in components.values())
        return {
            "status": "healthy" if healthy else "degraded",
            "version": "0.1.0",
            "components": components,
        }

    # Register routers
    from apps.api.modules.tenant.routes import router as tenant_router
    from apps.api.modules.auth.routes import router as auth_router
    from apps.api.modules.store.routes import router as store_router
    from apps.api.modules.product.routes import router as product_router
    from apps.api.modules.category.routes import router as category_router
    from apps.api.modules.collection.routes import router as collection_router
    from apps.api.modules.cart.routes import router as cart_router
    from apps.api.modules.checkout.routes import router as checkout_router
    from apps.api.modules.order.routes import router as order_router
    from apps.api.modules.customer.routes import router as customer_router
    from apps.api.modules.conversation.routes import router as conversation_router
    from apps.api.modules.lead.routes import router as lead_router
    from apps.api.modules.automation.routes import router as automation_router
    from apps.api.modules.analytics.routes import router as analytics_router
    from apps.api.modules.integration.routes import router as integration_router
    from apps.api.modules.seo.routes import router as seo_router
    from apps.api.modules.webhook.routes import router as webhook_router
    from apps.api.modules.webhook.inbound import router as inbound_webhook_router
    from apps.api.modules.page.routes import router as page_router
    from apps.api.modules.theme.routes import router as theme_router
    from apps.api.modules.media.routes import router as media_router
    from apps.api.modules.invoice.routes import router as invoice_router
    from apps.api.modules.discount.routes import router as discount_router
    from apps.api.modules.campaigns.routes import router as campaign_router
    from apps.api.modules.reports.routes import router as reports_router
    from apps.api.modules.public.routes import router as public_router
    from apps.api.modules.platform.routes import router as platform_router

    app.include_router(auth_router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
    app.include_router(tenant_router, prefix=f"{API_PREFIX}/tenants", tags=["tenants"])
    app.include_router(store_router, prefix=f"{API_PREFIX}/stores", tags=["stores"])
    app.include_router(product_router, prefix=f"{API_PREFIX}/products", tags=["products"])
    app.include_router(category_router, prefix=f"{API_PREFIX}/categories", tags=["categories"])
    app.include_router(collection_router, prefix=f"{API_PREFIX}/collections", tags=["collections"])
    app.include_router(cart_router, prefix=f"{API_PREFIX}/cart", tags=["cart"])
    app.include_router(checkout_router, prefix=f"{API_PREFIX}/checkout", tags=["checkout"])
    app.include_router(order_router, prefix=f"{API_PREFIX}/orders", tags=["orders"])
    app.include_router(customer_router, prefix=f"{API_PREFIX}/customers", tags=["customers"])
    app.include_router(conversation_router, prefix=f"{API_PREFIX}/conversations", tags=["conversations"])
    app.include_router(lead_router, prefix=f"{API_PREFIX}/leads", tags=["leads"])
    app.include_router(automation_router, prefix=f"{API_PREFIX}/automation", tags=["automation"])
    app.include_router(analytics_router, prefix=f"{API_PREFIX}/analytics", tags=["analytics"])
    app.include_router(integration_router, prefix=f"{API_PREFIX}/integrations", tags=["integrations"])
    app.include_router(seo_router, prefix=f"{API_PREFIX}/seo", tags=["seo"])
    app.include_router(webhook_router, prefix=f"{API_PREFIX}/webhooks", tags=["webhooks"])
    # Inbound provider webhooks (unauthenticated, signature-verified):
    #   POST /api/v1/webhooks/payments/{razorpay|stripe}
    #   GET+POST /api/v1/webhooks/instagram | /whatsapp
    app.include_router(inbound_webhook_router, prefix=f"{API_PREFIX}/webhooks", tags=["webhooks-inbound"])
    app.include_router(page_router, prefix=f"{API_PREFIX}/pages", tags=["pages"])
    app.include_router(theme_router, prefix=f"{API_PREFIX}/themes", tags=["themes"])
    app.include_router(media_router, prefix=f"{API_PREFIX}/media", tags=["media"])
    app.include_router(invoice_router, prefix=f"{API_PREFIX}/invoices", tags=["invoices"])
    app.include_router(discount_router, prefix=f"{API_PREFIX}/discounts", tags=["discounts"])
    app.include_router(campaign_router, prefix=f"{API_PREFIX}/campaigns", tags=["campaigns"])
    app.include_router(reports_router, prefix=f"{API_PREFIX}/reports", tags=["reports"])
    # Public storefront endpoints (rate-limited; no auth)
    app.include_router(public_router, prefix=f"{API_PREFIX}/public", tags=["public"])
    # Platform billing surfaces: plans + subscriptions
    app.include_router(platform_router, prefix=f"{API_PREFIX}/platform", tags=["platform"])

    # Instrument with OpenTelemetry (if available)
    # Requires `opentelemetry-instrumentation-fastapi` and `opentelemetry-exporter-otlp`
    # Collector config: infrastructure/monitoring/otel-collector.yaml
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore

        # Only instrument if OTEL is configured — avoids overhead in dev without collector
        otel_endpoint = getattr(settings, "otel_endpoint", None) or getattr(getattr(settings, "otel", None), "endpoint", None)
        otel_enabled = getattr(getattr(settings, "otel", None), "enabled", False) or bool(otel_endpoint)
        if otel_enabled or otel_endpoint:
            FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/healthz,/ready")
    except ImportError:
        # OTEL not installed — log at debug and continue (e.g. local dev without otel deps)
        import logging

        logging.getLogger(__name__).debug("opentelemetry.instrumentation.fastapi not installed — skipping instrumentation")
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("FastAPI OTEL instrumentation failed: %s", e)

    return app


app = create_app()
