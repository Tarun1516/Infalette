"""Infalette Celery workers application."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from infalette_config import get_settings

settings = get_settings()

celery_app = Celery(
    "infalette_workers",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=[
        "apps.workers.tasks.automation",
        "apps.workers.tasks.analytics",
        "apps.workers.tasks.notifications",
        "apps.workers.tasks.social",
        "apps.workers.tasks.social_tokens",
        "apps.workers.tasks.payments",
        "apps.workers.tasks.abandoned",
        "apps.workers.tasks.exports",
        "apps.workers.tasks.sitemap",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-scheduled-reports": {
            "task": "apps.workers.tasks.exports.daily_scheduled_reports",
            "schedule": crontab(hour=2, minute=0),
        },
        "refresh-social-tokens": {
            "task": "apps.workers.tasks.social_tokens.refresh_expiring_social_tokens",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "aggregate-analytics": {
            "task": "apps.workers.tasks.analytics.aggregate_analytics",
            "schedule": crontab(minute=15),
        },
        "recover-abandoned-carts": {
            "task": "apps.workers.tasks.abandoned.recover_abandoned_carts",
            "schedule": crontab(minute=30),
        },
        "automation-processor-tick": {
            # Drain the AutomationProcessor one tick so time-based
            # automation rules still fire when no inbound webhook is
            # present. The processor uses an internal high-water mark.
            "task": "apps.workers.tasks.automation.run_automation_processor",
            "schedule": crontab(minute="*/5"),
        },
        "checkout-unpaid-reminders": {
            "task": "apps.workers.tasks.checkout_unpaid.checkout_unpaid_reminders",
            "schedule": crontab(minute="*/20"),
        },
        "release-expired-checkout-inventory": {
            "task": "apps.workers.tasks.checkout_expiry.release_expired_checkout_inventory",
            "schedule": crontab(minute=10),
        },
        "reconcile-payments": {
            "task": "apps.workers.tasks.payments.reconcile_payments",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "generate-sitemaps": {
            "task": "apps.workers.tasks.sitemap.generate_sitemaps",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


def create_celery_app() -> Celery:
    """Factory function for creating the Celery application."""
    return celery_app


app = celery_app
