"""OpenAPI schema customization."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI


def customize_openapi(app: FastAPI) -> Optional[dict[str, Any]]:
    """Build the OpenAPI schema with a bearerAuth security scheme.

    Returns None if the schema was already generated.
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    return openapi_schema


def install_openapi_customization(app: FastAPI) -> None:
    """Lazily apply `customize_openapi` when the schema is first requested.

    Install before routers are registered — the schema is generated on
    first request to /openapi.json, so every route is included.
    """

    def openapi_with_security() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = customize_openapi(app)
        return app.openapi_schema  # type: ignore[return-value]

    app.openapi = openapi_with_security  # type: ignore[method-assign]
