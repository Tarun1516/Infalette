"""WhatsApp webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.conversation import Conversation, ConversationChannel
from infalette_database.models.message import Message
from infalette_database.models.lead import Lead
from infalette_database.models.social_identity import SocialIdentity
from infalette_database.models.customer import Customer
from infalette_database.models.product import Product
from infalette_config import get_settings
from infalette_integrations.base import allow_unverified_webhooks

logger = logging.getLogger(__name__)


class WhatsAppWebhookHandler:
    """Handles WhatsApp webhook events."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._verify_token = self._settings.social.whatsapp_verify_token
        self._webhook_secret = self._settings.social.whatsapp_webhook_secret

    async def verify_webhook(
        self,
        mode: str,
        verify_token: str,
        challenge: str,
    ) -> Optional[str]:
        """Verify the webhook subscription."""
        if mode == "subscribe" and verify_token == self._verify_token:
            return challenge
        return None

    async def verify_webhook_hmac(
        self,
        payload: dict,
        signature: str | None,
        raw_body: str | bytes | None = None,
    ) -> bool:
        """Verify Meta's X-Hub-Signature-256 over the exact raw request bytes.

        WhatsApp Cloud API signs payloads with the app secret exactly like
        Instagram. Missing signature/secret is only tolerated outside
        production (see ``allow_unverified_webhooks``).
        """
        if not signature:
            # No signature header at all: only tolerated outside production.
            return allow_unverified_webhooks()

        if not self._webhook_secret:
            if not allow_unverified_webhooks():
                return False
            return True

        if raw_body is not None:
            body = raw_body.encode() if isinstance(raw_body, str) else raw_body
        else:
            body = json.dumps(payload, sort_keys=True).encode()

        expected = "sha256=" + hmac.new(
            self._webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_message_webhook(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a message webhook from WhatsApp."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        messages = value.get("messages", [])
        if not messages:
            return {"status": "ignored", "reason": "no_messages"}

        message = messages[0]
        message_type = message.get("type", "")
        from_phone = message.get("from", "")
        # wa user id: prefer the sender's wa id (messages[].from), fall back to entry id
        wa_user_id = from_phone or entry.get("id", "")
        phone_number_id = (value.get("metadata") or {}).get("phone_number_id")

        # --- Flow -> checkout bridge (GAP B) ---
        from infalette_integrations.whatsapp.flows import parse_flow_selections

        selections = parse_flow_selections(message)
        if selections is not None:
            return await self._handle_flow_checkout(
                session=session,
                selections=selections,
                wa_user_id=wa_user_id,
                from_phone=from_phone,
                phone_number_id=phone_number_id,
            )

        # Get message text
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")
        elif message_type == "button":
            message_text = message.get("button", {}).get("text", "")
        elif message_type == "interactive":
            message_text = message.get("interactive", {}).get("button", {}).get("title", "")
        else:
            message_text = f"[{message_type}]"

        # Find social identity
        result = await session.execute(
            select(SocialIdentity).where(
                SocialIdentity.provider == "whatsapp",
                SocialIdentity.provider_user_id == wa_user_id,
            )
        )
        identity = result.scalar_one_or_none()

        if not identity:
            return {"status": "error", "error": "Social identity not found"}

        # Find or create conversation (keyed by wa handle in participants_json)
        wa_handle = f"wa_{from_phone}"
        result = await session.execute(
            select(Conversation).where(
                Conversation.tenant_id == identity.tenant_id,
                Conversation.channel == ConversationChannel.WHATSAPP,
            )
        )
        conversation = None
        for candidate in result.scalars():
            participants = candidate.participants_json or []
            if wa_handle in participants:
                conversation = candidate
                break

        # Find or create lead FIRST so the conversation can link to it
        result = await session.execute(
            select(Lead).where(
                Lead.tenant_id == identity.tenant_id,
                Lead.email == f"{from_phone}@whatsapp.com",
            )
        )
        lead = result.scalar_one_or_none()

        if not lead:
            lead = Lead(
                tenant_id=identity.tenant_id,
                first_name=from_phone,
                email=f"{from_phone}@whatsapp.com",
                source="whatsapp",
                status="new",
            )
            session.add(lead)
            await session.flush()

        if not conversation:
            conversation = Conversation(
                tenant_id=identity.tenant_id,
                channel=ConversationChannel.WHATSAPP,
                participants_json=[wa_handle],
                customer_name=lead.first_name,
                lead_id=lead.id,
            )
            session.add(conversation)
            await session.flush()
        elif getattr(conversation, "lead_id", None) is None:
            conversation.lead_id = lead.id

        # Dedupe on the provider message id (Meta retries deliveries)
        provider_message_id = message.get("id")
        existing_msg = None
        if provider_message_id:
            result = await session.execute(
                select(Message).where(Message.external_id == provider_message_id)
            )
            existing_msg = result.scalar_one_or_none()
        if existing_msg is not None:
            return {
                "status": "duplicate_ignored",
                "conversation_id": str(conversation.id),
                "lead_id": str(lead.id),
                "message_id": str(existing_msg.id),
            }

        msg = Message(
            conversation_id=conversation.id,
            content=message_text,
            external_id=provider_message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

        # Persist the domain event: analytics funnel stage 1 + processor loop
        try:
            from infalette_analytics.event_bus import record_event

            await record_event(
                tenant_id=identity.tenant_id,
                actor_id=None,
                event_type="conversation.message_received",
                payload={
                    "conversation_id": str(conversation.id),
                    "lead_id": str(lead.id),
                    "text": message_text,
                    "channel": "whatsapp",
                    "sender_id": from_phone,
                    "phone": from_phone,
                    "message_id": provider_message_id,
                },
                session=session,
            )
        except Exception:
            pass

        # Trigger automation rules for this inbound WhatsApp message
        engine_result = {"status": "not_attempted"}
        try:
            from infalette_automation.schemas import TriggerEvent
            from infalette_automation.engine import AutomationEngine

            trigger = TriggerEvent(
                event_type="conversation.message_received",
                tenant_id=identity.tenant_id,
                actor_id=None,
                timestamp=datetime.utcnow(),
                payload={
                    "conversation_id": str(conversation.id),
                    "lead_id": str(lead.id),
                    "text": message_text,
                    "channel": "whatsapp",
                    "sender_id": from_phone,
                    "phone": from_phone,
                },
            )
            engine = AutomationEngine()
            results = await engine.process_event(trigger, session)
            engine_result = {"status": "ok", "rules_executed": len(results)}
        except Exception as exc:
            engine_result = {"status": "error", "error": str(exc)}

        return {
            "status": "processed",
            "conversation_id": str(conversation.id),
            "lead_id": str(lead.id),
            "message_id": str(msg.id),
            "automation": engine_result,
        }

    # ------------------------------------------------------------------
    # Flow -> checkout bridge
    # ------------------------------------------------------------------

    async def _handle_flow_checkout(
        self,
        session: AsyncSession,
        selections: list[dict],
        wa_user_id: str,
        from_phone: str,
        phone_number_id: Optional[str],
    ) -> dict:
        """Bridge a WhatsApp Flow submission into cart -> checkout -> payment.

        Never raises: any failure is logged and reported in the result so the
        webhook endpoint still returns a 200 response.
        """
        try:
            return await self._flow_checkout_inner(
                session=session,
                selections=selections,
                wa_user_id=wa_user_id,
                from_phone=from_phone,
                phone_number_id=phone_number_id,
            )
        except Exception as exc:
            logger.error(f"WhatsApp flow checkout bridge failed: {exc}", exc_info=True)
            await self._safe_reply(
                wa_user_id or from_phone,
                "Sorry, we could not complete your order right now. Please try again.",
            )
            return {"status": "error", "error": str(exc)}

    async def _flow_checkout_inner(
        self,
        session: AsyncSession,
        selections: list[dict],
        wa_user_id: str,
        from_phone: str,
        phone_number_id: Optional[str],
    ) -> dict:
        from infalette_database.models.cart import Cart
        from infalette_database.models.cart_item import CartItem
        from infalette_commerce.checkout import CheckoutService
        from infalette_validation.schemas import (
            AddressSchema,
            CheckoutCreate,
            CustomerDataSchema,
        )

        contact = from_phone or wa_user_id
        session_key = f"wa-{wa_user_id}" if wa_user_id else f"wa-{contact}"

        # 1) Resolve tenant from SocialIdentity (phone_number_id first)
        tenant_id = None
        for candidate_id in filter(None, [phone_number_id, wa_user_id]):
            result = await session.execute(
                select(SocialIdentity).where(
                    SocialIdentity.provider == "whatsapp",
                    SocialIdentity.provider_user_id == str(candidate_id),
                )
            )
            identity = result.scalar_one_or_none()
            if identity is not None:
                tenant_id = identity.tenant_id
                break
        if tenant_id is None:
            logger.info("WhatsApp checkout bridge skipped: no social identity/tenant")
            return {"status": "skipped", "reason": "no_tenant"}

        # 2) Find/create Customer by phone within tenant
        result = await session.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.phone == contact,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            customer = Customer(
                tenant_id=tenant_id,
                phone=contact,
                first_name=contact,
                status="active",
            )
            session.add(customer)
            await session.flush()

        # 3) Resolve selections to tenant-scoped Products (by id then sku)
        resolved: list[tuple[Product, int]] = []
        for selection in selections:
            try:
                quantity = max(1, int(selection.get("quantity") or 1))
            except (TypeError, ValueError):
                quantity = 1
            product: Optional[Product] = None
            raw_product_id = selection.get("product_id")
            raw_sku = selection.get("sku")
            if raw_product_id:
                try:
                    product_uuid = UUID(str(raw_product_id))
                except ValueError:
                    product_uuid = None
                if product_uuid is not None:
                    result = await session.execute(
                        select(Product).where(
                            Product.id == product_uuid,
                            Product.tenant_id == tenant_id,
                        )
                    )
                    product = result.scalar_one_or_none()
            if product is None and raw_sku:
                result = await session.execute(
                    select(Product).where(
                        Product.sku == str(raw_sku).strip(),
                        Product.tenant_id == tenant_id,
                    )
                )
                product = result.scalar_one_or_none()
            if product is not None:
                resolved.append((product, quantity))
            else:
                logger.warning(f"WhatsApp order: unresolved selection {selection}")

        if not resolved:
            return {"status": "skipped", "reason": "no_resolvable_products"}

        # 4) Build cart items (reuse API cart services when importable)
        try:
            from apps.api.modules.cart.services import add_to_cart, get_or_create_cart
        except Exception as exc:
            logger.debug(f"API cart services unavailable ({exc}); inline creation")
            add_to_cart = get_or_create_cart = None

        if add_to_cart is not None and get_or_create_cart is not None:
            from infalette_validation.schemas import CartItemCreate

            for product, quantity in resolved:
                item_data = CartItemCreate(product_id=product.id, quantity=quantity)
                await add_to_cart(
                    tenant_id, customer.id, item_data, session, session_key=session_key
                )
        else:
            result = await session.execute(
                select(Cart).where(
                    Cart.tenant_id == tenant_id,
                    Cart.customer_id == customer.id,
                )
            )
            cart = result.scalar_one_or_none()
            if not cart:
                cart = Cart(
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    session_key=session_key[:64],
                    total_cents=0,
                )
                session.add(cart)
                await session.flush()
            for product, quantity in resolved:
                result = await session.execute(
                    select(CartItem).where(
                        CartItem.cart_id == cart.id,
                        CartItem.product_id == product.id,
                    )
                )
                existing_item = result.scalar_one_or_none()
                if existing_item:
                    existing_item.quantity += quantity
                else:
                    price = product.sale_price_cents or product.price_cents
                    session.add(
                        CartItem(
                            cart_id=cart.id,
                            product_id=product.id,
                            quantity=quantity,
                            price_cents=price,
                        )
                    )
            await session.flush()

        # 5) Minimal valid CheckoutCreate (placeholders filled from conversation data)
        address = AddressSchema(
            line1=f"WhatsApp order - {customer.first_name or contact}",
            city="-",
            state="-",
            postal_code="000000",
            country="IN",
        )
        checkout_data = CheckoutCreate(
            customer_data=CustomerDataSchema(
                email=customer.email,
                phone=customer.phone or contact,
                first_name=customer.first_name,
                last_name=None,
            ),
            shipping_address=address,
            billing_address=AddressSchema(**address.model_dump()),
            discount_codes=[],
        )

        service = CheckoutService()
        checkout = await service.create_checkout(
            tenant_id, customer.id, checkout_data, session, session_key=session_key
        )

        # 6) Initiate payment (razorpay); fall back to COD-style note on failure
        payment_url = None
        payment_note = ""
        try:
            payment_result = await service.initiate_payment(
                tenant_id, checkout.id, "razorpay", session
            )
            payment_url = payment_result.get("payment_url") or None
            if not payment_url:
                payment_note = "Online payment is currently unavailable."
        except Exception as exc:
            logger.warning(
                f"WhatsApp order payment initiation failed for checkout "
                f"{checkout.id}: {exc}"
            )
            payment_note = "Online payment failed."

        if payment_url:
            reply_text = f"Complete your order: {payment_url}"
        else:
            amount_inr = checkout.total_cents / 100
            reply_text = (
                f"Order received! Total ₹{amount_inr:.2f}. {payment_note} "
                "You can pay on delivery — we will confirm shortly."
            ).replace("  ", " ")
        await self._safe_reply(wa_user_id or from_phone, reply_text)

        return {
            "status": "processed",
            "bridge": "whatsapp_flow_checkout",
            "checkout_id": str(checkout.id),
            "total_cents": checkout.total_cents,
            "item_count": sum(quantity for _, quantity in resolved),
            "payment_url_sent": bool(payment_url),
        }

    async def _safe_reply(self, to: Optional[str], text: str) -> None:
        """Send a best-effort WhatsApp reply; never raises."""
        if not to:
            return
        try:
            from infalette_integrations.whatsapp.client import WhatsAppClient

            await WhatsAppClient().send_message(to=to, message=text)
        except Exception as exc:
            logger.error(f"WhatsApp reply failed (to={to}): {exc}", exc_info=True)

    async def process_flow_submission(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a WhatsApp Flow submission."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        flow_id = value.get("flow_id", "")
        flow_data = value.get("flow_data", {})
        from_phone = value.get("from", "")

        # Process flow submission
        logger.info(f"WhatsApp Flow submission: flow_id={flow_id}, data={flow_data}")

        return {
            "status": "processed",
            "flow_id": flow_id,
            "data": flow_data,
        }

    async def deduplicate_messages(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> bool:
        """Check if a message has already been processed."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return False

        message_id = messages[0].get("id", "")
        if not message_id:
            return False

        result = await session.execute(
            select(Message).where(Message.external_id == message_id)
        )
        return result.scalar_one_or_none() is not None
