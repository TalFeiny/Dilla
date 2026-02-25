"""Email Inbound API — receives emails from Cloudflare Email Workers, runs them
through the unified orchestrator, and replies via Resend.

Security:
- Webhook signature verification (shared secret with CF worker)
- Per-tenant sender allowlist
- No raw email stored — process in memory, audit log only
- Silent drop for unknown tenants/senders (no bounce)
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.email_composer import (
    EmailComposer,
    audit_log,
    get_audit_log,
    get_tenant,
    parse_tenant_from_address,
    send_email,
    verify_webhook_signature,
)
from app.services.unified_mcp_orchestrator import get_unified_orchestrator
from app.utils.json_serializer import clean_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

composer = EmailComposer()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class InboundEmailPayload(BaseModel):
    """Payload sent by the Cloudflare Email Worker."""
    to: str = Field(..., description="Recipient address (tenant@dilla.ai)")
    from_addr: str = Field(..., alias="from", description="Sender address")
    subject: str = Field("", description="Email subject line")
    text: str = Field("", description="Plain text body")
    html: Optional[str] = Field(None, description="HTML body (optional)")
    message_id: Optional[str] = Field(None, description="Message-ID header for threading")
    attachments: Optional[list] = Field(None, description="List of attachment metadata")

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# Main inbound endpoint
# ---------------------------------------------------------------------------

@router.post("/inbound")
async def handle_inbound_email(request: Request):
    """Process an inbound email from Cloudflare Email Worker.

    Flow:
    1. Verify webhook signature
    2. Resolve tenant from To: address
    3. Verify sender is in tenant's allowlist
    4. Run query through unified orchestrator
    5. Compose and send reply via Resend
    """
    # --- 1. Verify webhook signature ---
    raw_body = await request.body()
    signature = request.headers.get("X-Email-Signature", "")

    if settings.EMAIL_WEBHOOK_SECRET and not verify_webhook_signature(raw_body, signature):
        audit_log("REJECTED", reason="invalid_signature")
        # Silent drop — don't reveal that the endpoint exists
        return JSONResponse(content={"status": "ok"}, status_code=200)

    # Parse payload
    try:
        import json
        payload_dict = json.loads(raw_body)
        payload = InboundEmailPayload(**payload_dict)
    except Exception as e:
        logger.warning(f"[EMAIL] Failed to parse inbound payload: {e}")
        audit_log("REJECTED", reason="parse_error", error=str(e))
        return JSONResponse(content={"status": "ok"}, status_code=200)

    to_addr = payload.to
    from_addr = payload.from_addr
    subject = payload.subject

    audit_log("RECEIVED", sender=from_addr, to=to_addr, subject=subject[:80])

    # --- 2. Resolve tenant ---
    tenant_slug = parse_tenant_from_address(to_addr)
    if not tenant_slug:
        audit_log("REJECTED", sender=from_addr, to=to_addr, reason="invalid_domain")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    tenant = get_tenant(tenant_slug)
    if not tenant:
        audit_log("REJECTED", sender=from_addr, tenant=tenant_slug, reason="unknown_tenant")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    # --- 3. Verify sender ---
    allowed = tenant.get("allowed_senders", [])
    sender_lower = from_addr.lower().strip()
    if allowed and sender_lower not in [s.lower() for s in allowed]:
        audit_log("REJECTED", sender=from_addr, tenant=tenant_slug, reason="sender_not_allowed")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    sender_role = "partner"  # Default; extend with role lookup later
    for entry in allowed:
        if isinstance(entry, dict) and entry.get("email", "").lower() == sender_lower:
            sender_role = entry.get("role", "partner")
            break

    audit_log("AUTHORIZED", sender=from_addr, tenant=tenant_slug, role=sender_role)

    # --- 4. Build query and run orchestrator ---
    # The email body IS the query. Subject provides context.
    query = payload.text.strip() or payload.subject
    if payload.subject and payload.text:
        # Combine subject + body for richer context
        query = f"{payload.subject}\n\n{payload.text.strip()}"

    # Build context with tenant's fund params
    context = {
        "source": "email",
        "tenant": tenant_slug,
        "sender": from_addr,
        "sender_role": sender_role,
    }
    fund_context = tenant.get("fund_context")
    if fund_context:
        context["fund_context"] = fund_context

    reply_from = f"{tenant_slug}@{settings.EMAIL_FROM_DOMAIN}"
    reply_subject = f"Re: {subject}" if not subject.lower().startswith("re:") else subject

    try:
        orchestrator = get_unified_orchestrator()
        result = await orchestrator.process_request(
            prompt=query,
            output_format="analysis",  # Let orchestrator auto-detect
            context=context,
        )

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown error") if result else "No response"
            logger.warning(f"[EMAIL] Orchestrator failed for {tenant_slug}: {error_msg}")

            error_payload = composer.compose_error_reply(
                to_address=from_addr,
                from_address=reply_from,
                subject=reply_subject,
                error_message=str(error_msg),
            )
            await send_email(error_payload)
            audit_log("REPLIED_ERROR", sender=from_addr, tenant=tenant_slug, error=str(error_msg)[:200])
            return JSONResponse(content={"status": "processed", "success": False})

        # --- 5. Compose and send reply ---
        email_payload = composer.compose_from_orchestrator_result(
            result=result,
            to_address=from_addr,
            from_address=reply_from,
            subject=reply_subject,
            thread_message_id=payload.message_id,
        )

        send_result = await send_email(email_payload)

        audit_log(
            "REPLIED",
            sender=from_addr,
            tenant=tenant_slug,
            resend_id=send_result.get("id"),
            has_attachments=bool(email_payload.get("attachments")),
        )

        return JSONResponse(content={
            "status": "processed",
            "success": True,
            "resend_id": send_result.get("id"),
        })

    except Exception as e:
        logger.error(f"[EMAIL] Processing error for {tenant_slug}: {e}", exc_info=True)
        audit_log("ERROR", sender=from_addr, tenant=tenant_slug, error=str(e)[:200])

        # Try to send an error reply
        try:
            error_payload = composer.compose_error_reply(
                to_address=from_addr,
                from_address=reply_from,
                subject=reply_subject,
                error_message="An internal error occurred. The team has been notified.",
            )
            await send_email(error_payload)
        except Exception:
            pass  # Don't fail the webhook if error reply fails

        return JSONResponse(content={"status": "error"}, status_code=200)


# ---------------------------------------------------------------------------
# Tenant management endpoints (admin only in production)
# ---------------------------------------------------------------------------

class TenantRegistration(BaseModel):
    slug: str = Field(..., description="Email slug (e.g. 'acme-capital')")
    fund_name: str = Field(..., description="Fund display name")
    allowed_senders: list = Field(default_factory=list, description="List of allowed email addresses")
    fund_context: Optional[Dict[str, Any]] = Field(None, description="Fund params for orchestrator")


@router.post("/tenants")
async def register_email_tenant(reg: TenantRegistration):
    """Register a new tenant for email routing."""
    from app.services.email_composer import register_tenant

    register_tenant(reg.slug, {
        "fund_name": reg.fund_name,
        "allowed_senders": reg.allowed_senders,
        "fund_context": reg.fund_context or {},
    })

    return {
        "status": "registered",
        "slug": reg.slug,
        "email": f"{reg.slug}@{settings.EMAIL_FROM_DOMAIN}",
    }


@router.get("/tenants/{slug}")
async def get_email_tenant(slug: str):
    """Get tenant config (without sensitive data)."""
    tenant = get_tenant(slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "slug": slug,
        "fund_name": tenant.get("fund_name"),
        "email": f"{slug}@{settings.EMAIL_FROM_DOMAIN}",
        "allowed_senders_count": len(tenant.get("allowed_senders", [])),
    }


@router.get("/audit")
async def get_email_audit(limit: int = 50):
    """Return recent email audit log entries."""
    return {"entries": get_audit_log(limit)}


@router.get("/health")
async def email_health():
    """Health check for email integration."""
    return {
        "status": "healthy",
        "resend_configured": bool(settings.RESEND_API_KEY),
        "webhook_secret_configured": bool(settings.EMAIL_WEBHOOK_SECRET),
        "domain": settings.EMAIL_FROM_DOMAIN,
    }
