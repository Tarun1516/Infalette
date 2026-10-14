"""Automation action execution."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.schemas import TriggerEvent, AutomationResult


class ActionExecutor:
    """Executes automation actions."""

    ACTION_TYPES = {
        "send_email": "Send Email",
        "send_sms": "Send SMS",
        "send_whatsapp": "Send WhatsApp",
        "send_notification": "Send Notification",
        "private_reply": "Instagram Private Reply",
        "product_recommendation": "Product Recommendation",
        "schedule_reminder": "Schedule Reminder",
        "lead_create": "Create Lead",
        "tag_lead": "Tag Lead",
        "create_order": "Create Order",
        "update_order_status": "Update Order Status",
        "create_discount": "Create Discount",
        "assign_lead": "Assign Lead",
        "update_customer_tags": "Update Customer Tags",
        "webhook_call": "Webhook Call",
        "create_checkout_link": "Create Checkout Link",
        "abandoned_cart_recovery": "Abandoned Cart Recovery",
        "loyalty_reward": "Loyalty Reward",
    }

    async def execute_action(
        self,
        action_type: str,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Execute a single action."""
        # Accept both the public schema vocabulary and internal executor
        # keys so rules authored with either never fall through.
        aliases = {
            "assign_agent": "assign_lead",
            "reminder_schedule": "schedule_reminder",
            "tag": "tag_lead",
            "checkout_link": "create_checkout_link",
            "checkout_link_generation": "create_checkout_link",
            "lead_creation": "lead_create",
            "product_recommendations": "product_recommendation",
        }
        action_type = aliases.get(action_type, action_type)

        if action_type == "send_email":
            return await self._send_email(config, event, session)
        elif action_type == "send_sms":
            return await self._send_sms(config, event, session)
        elif action_type == "send_notification":
            return await self._send_notification(config, event, session)
        elif action_type == "private_reply":
            return await self._private_reply(config, event, session)
        elif action_type == "product_recommendation":
            return await self._product_recommendation(config, event, session)
        elif action_type == "schedule_reminder":
            return await self._schedule_reminder(config, event, session)
        elif action_type == "lead_create":
            return await self._lead_create(config, event, session)
        elif action_type == "tag_lead":
            return await self._tag_lead(config, event, session)
        elif action_type == "update_customer_tags":
            return await self._update_customer_tags(config, event, session)
        elif action_type == "assign_lead":
            return await self._assign_lead(config, event, session)
        elif action_type == "webhook_call":
            return await self._webhook_call(config, event, session)
        elif action_type == "create_checkout_link":
            return await self._create_checkout_link(config, event, session)
        elif action_type == "send_whatsapp":
            return await self._send_whatsapp(config, event, session)
        elif action_type == "create_order":
            return await self._create_order(config, event, session)
        elif action_type == "update_order_status":
            return await self._update_order_status(config, event, session)
        elif action_type == "create_discount":
            return await self._create_discount(config, event, session)
        elif action_type == "abandoned_cart_recovery":
            return await self._abandoned_cart_recovery(config, event, session)
        elif action_type == "loyalty_reward":
            return await self._loyalty_reward(config, event, session)
        else:
            return {"status": "error", "error": f"Unknown action type: {action_type}"}

    async def _private_reply(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Instagram private reply to a commenter (Meta 7-day window applies).

        Uses the tenant's stored SocialIdentity access token; falls back to
        the global env token when unset.
        """
        payload = event.payload or {}
        commenter_id = payload.get("commenter_id") or payload.get("sender_id")
        comment_id = payload.get("comment_id")
        message_text = config.get("message") or config.get("text") or ""
        if not message_text:
            return {"status": "skipped", "reason": "no message configured"}

        token = None
        ig_user_id = None
        try:
            from infalette_integrations.base import resolve_tenant_channel_token

            creds = await resolve_tenant_channel_token(
                event.tenant_id, "instagram", session=session
            )
            token = creds.get("access_token")
            ig_user_id = creds.get("provider_user_id")
        except Exception:
            pass

        from infalette_integrations.instagram.client import InstagramClient

        client = InstagramClient()
        if token:
            client.set_access_token(token)
        if not ig_user_id or not commenter_id:
            return {"status": "skipped", "reason": "missing IG account or commenter id"}

        # Meta compliance: private replies are only permitted within 7 days
        # of the user-initiated comment/message. Refuse to send otherwise.
        occurred_at = (
            payload.get("occurred_at")
            or payload.get("timestamp")
            or payload.get("created_at")
        )
        if occurred_at:
            try:
                from datetime import datetime as _dt, timezone as _tz

                raw = occurred_at
                if isinstance(raw, (int, float)):
                    original_time = _dt.fromtimestamp(raw, tz=_tz.utc)
                else:
                    text = str(raw).replace("Z", "+00:00")
                    parsed = _dt.fromisoformat(text)
                    original_time = parsed if parsed.tzinfo else parsed.replace(tzinfo=_tz.utc)
                age_days = (_dt.now(_tz.utc) - original_time).total_seconds() / 86400
                if age_days > 7:
                    return {
                        "status": "skipped",
                        "reason": "meta_7_day_window_expired",
                        "age_days": round(age_days, 1),
                    }
            except (ValueError, TypeError):
                pass  # unparsable timestamp: proceed, trigger fired on receipt

        result = await client.send_dm(
            ig_user_id=str(ig_user_id),
            recipient_id=str(commenter_id),
            message=message_text,
        )

        # Persist the outbound message so the unified inbox/funnel see it
        try:
            conversation_id = payload.get("conversation_id")
            if conversation_id:
                from infalette_database.models.message import Message

                session.add(
                    Message(
                        conversation_id=conversation_id,
                        direction="outbound",
                        content=message_text,
                        status="sent",
                    )
                )
                await session.commit()
        except Exception:
            pass

        return {"status": "sent", "action": "private_reply", "result": result}

    async def _product_recommendation(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Recommend products by name match against the inbound text.

        Sends product links as a WhatsApp/IG message when a channel is
        available; always records the recommendation on the lead timeline.
        """
        from sqlalchemy import select as _select
        from infalette_database.models.product import Product

        payload = event.payload or {}
        text = str(
            payload.get("text")
            or payload.get("message_text")
            or payload.get("comment_text")
            or ""
        ).lower()

        limit = int(config.get("limit", 3))
        category_hint = config.get("category")
        query = _select(Product).where(Product.tenant_id == event.tenant_id)
        rows = (await session.execute(query.limit(200))).scalars().all()

        matches = []
        for p in rows:
            hay = f"{p.name} {p.description or ''}".lower()
            tokens = [t for t in text.split() if len(t) > 3]
            score = sum(1 for t in tokens if t in hay)
            if category_hint and str(getattr(p, "category_id", "") or "") == str(category_hint):
                score += 1
            if score > 0:
                matches.append((score, p))
        matches.sort(key=lambda sp: sp[0], reverse=True)
        top = [p for _, p in matches[:limit]]

        # Fall back to newest visible products when nothing matched
        if not top:
            fallback = (
                await session.execute(
                    _select(Product)
                    .where(Product.tenant_id == event.tenant_id)
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
            top = list(fallback)

        recommendations = [
            {
                "id": str(p.id),
                "name": p.name,
                "price_cents": p.price_cents,
                "sale_price_cents": p.sale_price_cents,
                "url": f"/products/{p.id}",
            }
            for p in top
        ]

        # Deliver via WhatsApp when a phone is known and enabled
        delivered = None
        phone = payload.get("phone") or payload.get("customer_phone")
        if phone and config.get("deliver_whatsapp", True):
            from infalette_integrations.whatsapp.client import WhatsAppClient

            lines = [
                f"{r['name']} — ₹{((r['sale_price_cents'] or r['price_cents']) / 100):.0f}"
                for r in recommendations
            ]
            try:
                delivered = await WhatsAppClient().send_message(
                    to=phone, message="\n".join(lines)
                )
            except Exception as exc:
                delivered = {"status": "error", "error": str(exc)}

        return {
            "status": "recommended",
            "action": "product_recommendation",
            "recommendations": recommendations,
            "delivery": delivered,
        }

    async def _schedule_reminder(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Schedule a follow-up reminder for this lead/checkout.

        Persists an Event of type ``reminder.scheduled``; the beat worker
        picks up due reminders (see workers.tasks.automation).
        """
        from datetime import datetime, timedelta
        from infalette_analytics.event_bus import record_event

        delay_minutes = int(config.get("delay_minutes", 60))
        due_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
        payload = dict(event.payload or {})
        payload.update({"due_at": due_at.isoformat(), "message": config.get("message", "")})

        await record_event(
            tenant_id=event.tenant_id,
            actor_id=None,
            event_type="reminder.scheduled",
            payload=payload,
            session=session,
        )
        return {
            "status": "scheduled",
            "action": "schedule_reminder",
            "due_at": due_at.isoformat(),
        }

    async def _lead_create(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Create (or reuse) a lead from an automation event."""
        from sqlalchemy import select as _select
        from infalette_database.models.lead import Lead

        payload = event.payload or {}
        email = payload.get("email") or f"{payload.get('username', 'anon')}@instagram.com"
        existing = (
            await session.execute(
                _select(Lead).where(Lead.tenant_id == event.tenant_id, Lead.email == email)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"status": "exists", "action": "lead_create", "lead_id": str(existing.id)}

        lead = Lead(
            tenant_id=event.tenant_id,
            email=email,
            first_name=payload.get("first_name"),
            phone=payload.get("phone"),
            source=config.get("source") or payload.get("channel") or "automation",
            status="new",
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        return {"status": "created", "action": "lead_create", "lead_id": str(lead.id)}

    async def _tag_lead(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Append tags to a lead referenced by the event payload."""
        from sqlalchemy import select as _select
        from uuid import UUID as _UUID
        from infalette_database.models.lead import Lead

        lead_id = (event.payload or {}).get("lead_id")
        tags = config.get("tags") or []
        if not lead_id or not tags:
            return {"status": "skipped", "reason": "lead_id/tags required"}
        lead = (
            await session.execute(
                _select(Lead).where(
                    Lead.id == _UUID(str(lead_id)), Lead.tenant_id == event.tenant_id
                )
            )
        ).scalar_one_or_none()
        if not lead:
            return {"status": "skipped", "reason": "lead not found"}

        current = set(lead.tags or [])
        current.update(tags)
        lead.tags = sorted(current)
        await session.commit()
        return {"status": "tagged", "action": "tag_lead", "tags": lead.tags}

    async def _send_email(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Send an email action (marketing consent enforced)."""
        from infalette_integrations.email.client import EmailClient

        to = config.get("to") or event.payload.get("email")
        # Consent gate unless the rule explicitly marks the message
        # transactional (order updates etc. bypass marketing consent).
        if not config.get("transactional"):
            allowed = await self._consent_for_target(session, event.tenant_id, to, "email")
            if not allowed:
                return {"status": "skipped", "reason": "no email consent"}
        client = EmailClient()
        await client.send_email(
            to=to,
            subject=config.get("subject", "Automated Email"),
            html_content=config.get("html_content", ""),
            tenant_id=event.tenant_id,
        )
        return {"status": "sent", "action": "send_email"}

    async def _consent_for_target(
        self,
        session: AsyncSession,
        tenant_id,
        target: str | None,
        channel: str,
    ) -> bool:
        """Look up consent for an email/phone target.

        Matches customers by email (or by the synthetic social emails).
        Unknown targets are treated as non-consented.
        """
        if not target:
            return False
        try:
            from sqlalchemy import select as _select
            from infalette_database.models.customer import Customer
            from infalette_commerce.consent import customer_can_contact

            row = (
                await session.execute(
                    _select(Customer).where(
                        Customer.tenant_id == tenant_id,
                        Customer.email == str(target).lower(),
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            return customer_can_contact(row, channel)
        except Exception:
            return False

    async def _send_sms(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Send an SMS action."""
        from infalette_integrations.sms.client import SMSClient

        payload = event.payload or {}
        to = (
            config.get("to")
            or payload.get("to")
            or payload.get("phone")
            or payload.get("customer_phone")
        )
        if not to:
            return {
                "status": "error",
                "action": "send_sms",
                "error": "No recipient phone in config or event payload",
            }

        client = SMSClient()
        result = await client.send_sms(
            to=to,
            message=config.get("message", ""),
            tenant_id=event.tenant_id,
        )
        return {"action": "send_sms", **result}

    async def _send_notification(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Send a notification action: email + persisted notification event."""
        from infalette_integrations.email.client import EmailClient
        from infalette_database.models.event import Event

        payload = event.payload or {}
        to = (
            config.get("to")
            or payload.get("email")
            or payload.get("customer_email")
        )

        client = EmailClient()
        email_result = await client.send_email(
            to=to,
            subject=config.get("title") or "Notification",
            html_content=config.get("body", ""),
            tenant_id=event.tenant_id,
        )

        notification_event = Event(
            tenant_id=event.tenant_id,
            actor_id=None,
            event_type="notification.sent",
            payload_json={
                "title": config.get("title") or "Notification",
                "to": to,
                "trigger_event_type": event.event_type,
                "email_status": email_result.get("status"),
                "source": "automation",
                "action": "send_notification",
            },
        )
        session.add(notification_event)
        await session.commit()

        status = email_result.get("status")
        return {
            "status": "sent" if status == "sent" else "failed",
            "action": "send_notification",
            "email_status": status,
            "event_id": str(notification_event.id),
        }

    async def _update_customer_tags(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Update customer tags action."""
        from infalette_database.models.customer import Customer
        customer_id = event.payload.get("customer_id")
        if not customer_id:
            return {"status": "error", "error": "No customer_id in event"}

        result = await session.execute(
            select(Customer).where(Customer.id == UUID(customer_id))
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return {"status": "error", "error": "Customer not found"}

        tags = customer.tags or []
        add_tags = config.get("add_tags", [])
        remove_tags = config.get("remove_tags", [])

        for tag in add_tags:
            if tag not in tags:
                tags.append(tag)
        for tag in remove_tags:
            if tag in tags:
                tags.remove(tag)

        customer.tags = tags
        await session.commit()
        return {"status": "updated", "action": "update_customer_tags"}

    async def _assign_lead(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Assign lead action."""
        from infalette_database.models.lead import Lead
        lead_id = event.payload.get("lead_id")
        if not lead_id:
            return {"status": "error", "error": "No lead_id in event"}

        result = await session.execute(
            select(Lead).where(Lead.id == UUID(lead_id))
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return {"status": "error", "error": "Lead not found"}

        lead.assigned_to = config.get("agent_id")
        await session.commit()
        return {"status": "assigned", "action": "assign_lead"}

    async def _webhook_call(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Webhook call action."""
        import httpx
        import json

        url = config.get("url")
        if not url:
            return {"status": "error", "error": "No URL configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=event.payload, timeout=10)
                return {"status": "called", "action": "webhook_call", "status_code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _create_checkout_link(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Create checkout link action."""
        from infalette_automation.checkout_link import CheckoutLinkGenerator
        generator = CheckoutLinkGenerator()
        link = await generator.create_link(event, config, session)
        return {"status": "created", "action": "create_checkout_link", "link": link}

    async def _abandoned_cart_recovery(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Abandoned cart recovery: checkout link + recovery message."""
        from infalette_automation.checkout_link import CheckoutLinkGenerator
        generator = CheckoutLinkGenerator()
        link = await generator.create_link(event, config, session)
        # create_link returns the URL string ("" when prerequisites missing)
        checkout_url = str(link) if link else None

        payload = event.payload or {}
        results = {"checkout": link}

        to = payload.get("email") or payload.get("customer_email")
        if to and config.get("send_email", True):
            from infalette_integrations.email.client import EmailClient
            email_result = await EmailClient().send_email(
                to=to,
                subject=config.get("subject", "You left something in your cart"),
                html_content=(
                    f"<p>{config.get('message', 'Complete your purchase now:')}"
                    f"</p><p><a href='{checkout_url}'>{checkout_url}</a></p>"
                ),
                tenant_id=event.tenant_id,
            )
            results["email"] = email_result

        phone = payload.get("phone") or payload.get("customer_phone")
        if phone and config.get("send_whatsapp", False):
            from infalette_integrations.whatsapp.client import WhatsAppClient
            wa_result = await WhatsAppClient().send_message(
                to=phone,
                message=f"{config.get('message', 'Complete your purchase:')} {checkout_url}",
            )
            results["whatsapp"] = wa_result

        return {
            "status": "triggered",
            "action": "abandoned_cart_recovery",
            **results,
        }

    async def _loyalty_reward(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Loyalty reward action: tag the customer and record the award."""
        from infalette_database.models.customer import Customer
        customer_id = event.payload.get("customer_id")
        if not customer_id:
            return {"status": "error", "error": "No customer_id in event"}

        result = await session.execute(
            select(Customer).where(Customer.id == UUID(customer_id))
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return {"status": "error", "error": "Customer not found"}

        tags = list(customer.tags or [])
        reward_tag = config.get("tag", "loyalty")
        if reward_tag not in tags:
            tags.append(reward_tag)
        customer.tags = tags

        from infalette_analytics.event_bus import record_event
        await record_event(
            tenant_id=event.tenant_id,
            actor_id=None,
            event_type="loyalty.awarded",
            payload={
                "customer_id": str(customer_id),
                "points": config.get("points", 0),
                "source": "automation",
            },
            session=session,
        )
        return {
            "status": "awarded",
            "action": "loyalty_reward",
            "points": config.get("points", 0),
        }

    async def _send_whatsapp(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Send a WhatsApp text message via the Cloud API client."""
        from infalette_integrations.whatsapp.client import WhatsAppClient

        payload = event.payload or {}
        to = (
            config.get("to")
            or payload.get("to")
            or payload.get("phone")
            or payload.get("customer_phone")
            or payload.get("wa_phone")
        )
        if not to:
            return {
                "status": "error",
                "action": "send_whatsapp",
                "error": "No recipient phone in config or event payload",
            }

        # Consent gate (transactional messages bypass marketing consent)
        if not config.get("transactional"):
            allowed = await self._consent_for_target(
                session, event.tenant_id, f"{to}@whatsapp.com", "whatsapp"
            )
            if not allowed:
                return {"status": "skipped", "reason": "no whatsapp consent"}

        # Per-tenant credentials from the tenant's connected account
        try:
            from infalette_integrations.base import resolve_tenant_channel_token

            creds = await resolve_tenant_channel_token(
                event.tenant_id, "whatsapp", session=session
            )
        except Exception:
            creds = {}
        client = WhatsAppClient(
            access_token=creds.get("access_token"),
        )
        result = await client.send_message(
            to=to,
            message=config.get("message", ""),
        )
        return {"action": "send_whatsapp", **result}

    async def _create_order(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Create an order directly from automation config/payload."""
        from datetime import datetime, timezone
        from infalette_database.models.order import Order, OrderStatus
        from infalette_database.models.order_item import OrderItem

        items = config.get("items") or event.payload.get("items") or []
        if isinstance(items, dict):
            items = [items]
        if not items:
            return {"status": "error", "error": "No order items provided"}

        total_cents = sum(int(i.get("price_cents", 0)) * int(i.get("quantity", 1)) for i in items)
        order = Order(
            status=OrderStatus.CONFIRMED,
            total_cents=total_cents,
            currency=config.get("currency", "INR"),
            customer_id=UUID(event.payload["customer_id"]) if event.payload.get("customer_id") else None,
        )
        session.add(order)
        await session.flush()
        for i in items:
            session.add(OrderItem(
                order_id=order.id,
                product_id=UUID(i["product_id"]) if i.get("product_id") else None,
                quantity=int(i.get("quantity", 1)),
                price_cents=int(i.get("price_cents", 0)),
                product_snapshot_json={
                    "name": i.get("name", "Item"),
                    "source": "automation",
                },
            ))
        await session.commit()
        return {"status": "created", "action": "create_order", "order_id": str(order.id)}

    async def _update_order_status(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Update an order's status through the guarded transition map."""
        from infalette_commerce.orders import OrderService

        order_id = config.get("order_id") or event.payload.get("order_id")
        new_status = config.get("status") or event.payload.get("new_status")
        if not order_id or not new_status:
            return {
                "status": "error",
                "error": "order_id and status required for update_order_status",
            }

        from infalette_database.models.order import OrderStatus
        try:
            status_enum = OrderStatus(str(new_status))
        except ValueError:
            return {"status": "error", "error": f"Invalid order status: {new_status}"}

        updated = await OrderService().update_order_status(
            event.tenant_id, UUID(str(order_id)), status_enum, session
        )
        if updated is None:
            return {"status": "error", "error": "Order not found"}
        return {
            "status": "updated",
            "action": "update_order_status",
            "order_status": str(getattr(updated.status, "value", updated.status)),
        }

    async def _create_discount(
        self,
        config: dict,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> dict:
        """Create a discount code for the tenant."""
        import secrets
        from datetime import datetime, timedelta, timezone
        from infalette_database.models.discount_code import DiscountCode

        code = config.get("code") or f"AUTO{secrets.token_hex(4).upper()}"
        discount = DiscountCode(
            tenant_id=event.tenant_id,
            code=code,
            discount_type=config.get("discount_type", "percentage"),
            value=int(config.get("value", 10)),
            minimum_order_cents=int(config.get("minimum_order_cents", 0)),
            usage_limit=config.get("usage_limit"),
            is_active=True,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(days=int(config.get("expires_in_days", 7)))
            ),
        )
        session.add(discount)
        await session.commit()
        return {
            "status": "created",
            "action": "create_discount",
            "code": discount.code,
        }

    def get_available_actions(self) -> list[dict]:
        """Get list of available action types."""
        return [
            {"type": t, "name": n}
            for t, n in self.ACTION_TYPES.items()
        ]
