"""Infalette backend applications package.

This package contains the FastAPI HTTP API (``apps.api``) and the
Celery worker application (``apps.workers``). It exists so both can be
imported as ``apps.<sub>.main:app`` after editable installs.
"""

__all__ = ["api", "workers"]
