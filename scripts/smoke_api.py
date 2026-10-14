"""End-to-end HTTP smoke test — boots the real FastAPI app on SQLite.

Runs the full commerce loop over real HTTP (in-process TestClient):
  health -> auth wall -> product create/list -> guest cart -> checkout ->
  COD payment -> invoice download -> feature-gate check.

Usage:
    python scripts/smoke_api.py            # ephemeral sqlite db
Exits non-zero on any assertion failure. No Postgres/Redis required.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

# Isolated DB for this run (must be set before app imports).
# A developer .env (e.g. with a live Neon DSN) must NOT leak into this
# ephemeral sqlite run: remove every DATABASE_URL* override and point the
# settings loader away from .env so the app and the seed share one DB.
_tmpdir = tempfile.mkdtemp(prefix="infalette-smoke-")
for key in ("DATABASE_URL", "DATABASE_URL_POOLED", "DATABASE_URL_DIRECT"):
    os.environ.pop(key, None)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmpdir}/smoke.db"
os.environ["INFALETTE_ENV_FILE"] = os.devnull  # settings loader: ignore .env
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("RATE_LIMIT_FAIL_CLOSED", "false")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
for pkg in ["config", "validation", "database", "auth", "commerce",
            "automation", "analytics", "seo", "integrations"]:
    sys.path.insert(0, str(REPO / "packages" / pkg / "src"))

PASS = []
def ok(name: str, cond: bool, extra: str = ""):
    PASS.append((name, bool(cond)))
    print(f"{'✓' if cond else '✗ FAIL'} {name}{(' — ' + extra) if extra else ''}")
    if not cond:
        raise SystemExit(1)


def main() -> None:
    import asyncio

    from fastapi.testclient import TestClient

    import apps.api.main as appmod
    from infalette_auth.jwt import TokenManager
    from infalette_auth.security import PasswordHasher
    from infalette_database.base import Base
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.user import User
    from infalette_database.session import get_engine, get_session_factory

    app = appmod.create_app()

    with TestClient(app) as client:  # context enter triggers lifespan init_db
        # ---- seed tenant + user directly -------------------------------
        # NOTE: TestClient runs the app on its own event loop; the cached
        # global engine is bound to that loop. `asyncio.run` below would
        # create a second loop and crash with "attached to a different
        # loop" — so seed through a dedicated engine/session created on
        # this loop, disposed before the HTTP calls start.

        async def seed():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from infalette_config import get_settings

            db_url = get_settings().database.url
            if db_url.startswith("sqlite"):
                engine = create_async_engine(db_url)
            else:
                from infalette_database.session import _build_engine_kwargs

                kwargs = _build_engine_kwargs(db_url)
                engine = create_async_engine(
                    kwargs["url"], connect_args=kwargs.get("connect_args", {})
                )
            factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as s:
                t = Tenant(name="Smoke Tenant", slug="smoke-store", plan="store_automation")
                s.add(t)
                await s.flush()
                u = User(
                    email="owner@smoke.test",
                    password_hash=PasswordHasher().hash_password("secret123"),
                    first_name="Smoke", last_name="Owner",
                    role="tenant_owner", status="active", tenant_id=t.id,
                )
                s.add(u)
                await s.commit()
                tid, uid = t.id, u.id
            await engine.dispose()
            return tid, uid

        tenant_id, user_id = asyncio.run(seed())
        token = TokenManager().create_access_token(subject=str(user_id), tenant_id=tenant_id)
        H = {"Authorization": f"Bearer {token}"}
        GH = {"X-Tenant": "smoke-store", "X-Cart-Session-ID": str(uuid.uuid4())}

        # ---- health ------------------------------------------------------
        r = client.get("/health")
        ok("GET /health == 200", r.status_code == 200)

        # ---- auth wall ---------------------------------------------------
        r = client.get("/api/v1/products")
        ok("products unauthed -> 401", r.status_code == 401, r.text[:60])

        # ---- product create + list ---------------------------------------
        payload = {
            "name": "Organic Baby Lotion", "slug": "organic-baby-lotion",
            "sku": "LOTION-1", "price_cents": 49900,
            "inventory": 50, "tax_class": "standard",
            "ingredients": "Aloe, Shea", "safety_info": "External use only",
        }
        r = client.post("/api/v1/products/", json=payload, headers=H)
        ok("POST /products -> 201", r.status_code == 201, r.text[:80])
        pid = r.json()["id"]

        r = client.get("/api/v1/products/", headers=H)
        body = r.json()
        items = body["data"] if isinstance(body, dict) else body
        ok("GET /products lists created", any(p.get("id") == pid for p in items))

        # ---- variant CRUD -------------------------------------------------
        r = client.post(f"/api/v1/products/{pid}/variants/",
                        json={"sku": "LOTION-1-200ML", "price_cents": 69900,
                              "inventory_quantity": 20}, headers=H)
        ok("POST variant -> 201", r.status_code == 201, r.text[:80])

        # ---- guest cart ----------------------------------------------------
        r = client.post("/api/v1/cart/items", json={"product_id": pid, "quantity": 2},
                        headers=GH)
        ok("guest add-to-cart -> 201", r.status_code == 201, r.text[:80])
        r = client.get("/api/v1/cart/", headers=GH)
        cbody = r.json()
        ok("guest cart has item", len(cbody.get("items") or []) >= 1 and cbody.get("total_cents", 0) > 0,
           f"total={cbody.get('total_cents')}")

        # ---- checkout (guest) ----------------------------------------------
        addr = {"line1": "12 MG Road", "city": "Bengaluru", "state": "Karnataka",
                "postal_code": "560001", "country": "India"}
        co_payload = {
            "customer_data": {"email": "mom@example.com", "first_name": "Ananya"},
            "shipping_address": addr, "billing_address": addr,
        }
        r = client.post("/api/v1/checkout/", json=co_payload, headers=GH)
        ok("guest checkout -> 201", r.status_code == 201, r.text[:120])
        checkout_id = r.json()["id"]
        total = r.json().get("total_cents", 0)
        ok("checkout total includes GST+shipping", total > 99800, f"total={total}")

        # ---- COD payment -> order -------------------------------------------
        r = client.post(f"/api/v1/checkout/{checkout_id}/cod", headers={**H, **GH})
        ok("COD pay -> order", r.status_code == 200 and r.json().get("cod") is True, r.text[:160])
        order_id = (r.json().get("order_id") or "") if r.status_code == 200 else ""

        # ---- invoice ---------------------------------------------------------
        r = client.get(f"/api/v1/invoices/{order_id}/download?format=html", headers=H)
        ok("invoice HTML -> 200", r.status_code == 200 and "GST" in r.text.upper())

        # ---- feature gate: store_automation plan allows automation ----------
        r = client.get("/api/v1/automation/", headers=H)
        ok("automation list allowed on store_automation", r.status_code == 200, r.text[:60])

        # ---- quota sanity: second tenant-free guest cannot create product ----
        r = client.post("/api/v1/products/", json=payload)
        ok("product create unauthed -> 401", r.status_code == 401)

    passed = sum(1 for _, c in PASS if c)
    print(f"\nSMOKE RESULT: {passed}/{len(PASS)} checks passed")
    if passed != len(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
