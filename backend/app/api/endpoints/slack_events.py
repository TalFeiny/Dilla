"""Slack Events API — receives messages from Slack, runs them through the
unified orchestrator, and replies in-thread via the Slack Web API.

Mirrors the email inbound flow:
- Slack Events API replaces Cloudflare Email Worker (no separate worker needed)
- Slack signing secret replaces HMAC webhook secret
- chat.postMessage replaces Resend send
- thread_ts replaces In-Reply-To header

Security:
- Slack request signature verification (signing secret)
- Per-workspace bot token via OAuth2 install flow
- No raw message stored — process in memory, audit log only
- Silent drop for unknown workspaces
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.slack_composer import (
    SlackComposer,
    exchange_oauth_code,
    get_slack_audit_log,
    get_slack_tenant,
    register_slack_tenant,
    send_slack_message,
    slack_audit_log,
    verify_slack_signature,
)
from app.services.unified_mcp_orchestrator import get_unified_orchestrator
from app.utils.json_serializer import clean_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

composer = SlackComposer()


# ---------------------------------------------------------------------------
# Slack Events API endpoint
# ---------------------------------------------------------------------------

@router.post("/events")
async def handle_slack_event(request: Request):
    """Handle inbound events from Slack Events API.

    Flow:
    1. Verify Slack request signature
    2. Handle URL verification challenge (one-time Slack setup)
    3. Extract message event
    4. Resolve tenant from team_id
    5. Run query through unified orchestrator
    6. Reply in thread via Slack Web API
    """
    raw_body = await request.body()

    # --- 1. Verify Slack signature ---
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if settings.SLACK_SIGNING_SECRET and not verify_slack_signature(
        raw_body, timestamp, signature
    ):
        slack_audit_log("REJECTED", reason="invalid_signature")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    # Parse payload
    try:
        import json
        payload = json.loads(raw_body)
    except Exception as e:
        logger.warning(f"[SLACK] Failed to parse event payload: {e}")
        slack_audit_log("REJECTED", reason="parse_error", error=str(e))
        return JSONResponse(content={"status": "ok"}, status_code=200)

    # --- 2. URL verification challenge ---
    # Slack sends this once when you configure the Events API URL
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload.get("challenge", "")})

    # --- 3. Extract message event ---
    event = payload.get("event", {})
    event_type = event.get("type")
    team_id = payload.get("team_id", "")

    # Only process new messages (not edits, bot messages, etc.)
    if event_type != "message":
        return JSONResponse(content={"status": "ok"})

    # Skip bot messages (prevents infinite loops)
    if event.get("bot_id") or event.get("subtype"):
        return JSONResponse(content={"status": "ok"})

    user_id = event.get("user", "")
    channel = event.get("channel", "")
    text = event.get("text", "").strip()
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    message_ts = event.get("ts", "")

    if not text:
        return JSONResponse(content={"status": "ok"})

    slack_audit_log("RECEIVED", team=team_id, user=user_id, channel=channel)

    # --- 4. Resolve tenant ---
    tenant = get_slack_tenant(team_id)
    if not tenant:
        slack_audit_log("REJECTED", team=team_id, reason="unknown_workspace")
        return JSONResponse(content={"status": "ok"})

    bot_token = tenant.get("bot_token")
    if not bot_token:
        slack_audit_log("REJECTED", team=team_id, reason="no_bot_token")
        return JSONResponse(content={"status": "ok"})

    # Optional: Check allowed channels
    allowed_channels = tenant.get("allowed_channels", [])
    if allowed_channels and channel not in allowed_channels:
        slack_audit_log("REJECTED", team=team_id, channel=channel, reason="channel_not_allowed")
        return JSONResponse(content={"status": "ok"})

    # Optional: Check allowed users
    allowed_users = tenant.get("allowed_users", [])
    if allowed_users and user_id not in allowed_users:
        slack_audit_log("REJECTED", team=team_id, user=user_id, reason="user_not_allowed")
        return JSONResponse(content={"status": "ok"})

    slack_audit_log("AUTHORIZED", team=team_id, user=user_id, channel=channel)

    # --- 5. Send thinking indicator, then run orchestrator ---
    # Post a "thinking" message that we'll update with the result
    thinking_blocks = composer.compose_thinking_message()
    thinking_result = await send_slack_message(
        token=bot_token,
        channel=channel,
        blocks=thinking_blocks,
        thread_ts=thread_ts,
        text="Analyzing...",
    )

    # Build context with tenant's fund params
    context = {
        "source": "slack",
        "tenant": tenant.get("slug", team_id),
        "sender": user_id,
        "sender_role": "partner",  # Default; extend with user lookup later
    }
    fund_context = tenant.get("fund_context")
    if fund_context:
        context["fund_context"] = fund_context

    try:
        orchestrator = get_unified_orchestrator()
        result = await orchestrator.process_request(
            prompt=text,
            output_format="analysis",
            context=context,
        )

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown error") if result else "No response"
            logger.warning(f"[SLACK] Orchestrator failed for {team_id}: {error_msg}")

            error_blocks = composer.compose_error_message(str(error_msg))
            await send_slack_message(
                token=bot_token,
                channel=channel,
                blocks=error_blocks,
                thread_ts=thread_ts,
                text=f"Error: {error_msg}",
            )
            slack_audit_log("REPLIED_ERROR", team=team_id, channel=channel, error=str(error_msg)[:200])
            return JSONResponse(content={"status": "processed", "success": False})

        # --- 6. Compose and send reply in thread ---
        blocks = composer.compose_from_orchestrator_result(result=result, query=text)
        send_result = await send_slack_message(
            token=bot_token,
            channel=channel,
            blocks=blocks,
            thread_ts=thread_ts,
            text="Dilla AI analysis complete",
        )

        slack_audit_log(
            "REPLIED",
            team=team_id,
            user=user_id,
            channel=channel,
            ts=send_result.get("ts"),
        )

        return JSONResponse(content={
            "status": "processed",
            "success": True,
            "ts": send_result.get("ts"),
        })

    except Exception as e:
        logger.error(f"[SLACK] Processing error for {team_id}: {e}", exc_info=True)
        slack_audit_log("ERROR", team=team_id, channel=channel, error=str(e)[:200])

        # Try to send an error reply
        try:
            error_blocks = composer.compose_error_message(
                "An internal error occurred. The team has been notified."
            )
            await send_slack_message(
                token=bot_token,
                channel=channel,
                blocks=error_blocks,
                thread_ts=thread_ts,
                text="An error occurred",
            )
        except Exception:
            pass

        return JSONResponse(content={"status": "error"}, status_code=200)


# ---------------------------------------------------------------------------
# OAuth2 Install Flow — tenant installs the Dilla Slack app
# ---------------------------------------------------------------------------

@router.get("/install")
async def slack_install():
    """Redirect to Slack's OAuth authorize page.

    The tenant clicks 'Add to Slack' which hits this endpoint.
    """
    if not settings.SLACK_CLIENT_ID:
        raise HTTPException(status_code=500, detail="SLACK_CLIENT_ID not configured")

    scopes = "chat:write,channels:history,groups:history,im:history,im:read"
    backend_url = settings.SLACK_REDIRECT_URI or f"{settings.BACKEND_URL}/api/slack/oauth/callback"

    authorize_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={settings.SLACK_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={backend_url}"
    )

    return RedirectResponse(url=authorize_url)


@router.get("/oauth/callback")
async def slack_oauth_callback(code: str = "", error: str = ""):
    """Handle the OAuth callback from Slack after install.

    Exchanges the auth code for a bot token and registers the workspace.
    """
    if error:
        logger.warning(f"[SLACK] OAuth denied: {error}")
        return JSONResponse(content={"status": "error", "error": error}, status_code=400)

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Exchange code for bot token
    oauth_result = await exchange_oauth_code(code)

    if not oauth_result.get("success"):
        slack_audit_log("OAUTH_FAILED", error=oauth_result.get("error"))
        return JSONResponse(
            content={"status": "error", "error": oauth_result.get("error")},
            status_code=400,
        )

    team_id = oauth_result["team_id"]
    team_name = oauth_result["team_name"]

    # Register the workspace as a tenant
    register_slack_tenant(team_id, {
        "team_name": team_name,
        "bot_token": oauth_result["bot_token"],
        "bot_user_id": oauth_result.get("bot_user_id"),
        "slug": team_name.lower().replace(" ", "-") if team_name else team_id,
        "allowed_channels": [],  # Empty = all channels
        "allowed_users": [],  # Empty = all users
        "fund_context": {},  # Configure via tenant API
    })

    slack_audit_log("INSTALLED", team=team_id, team_name=team_name)

    # In production, redirect to a success page in the frontend
    return JSONResponse(content={
        "status": "installed",
        "team_id": team_id,
        "team_name": team_name,
        "message": f"Dilla AI has been installed in {team_name}! "
                   f"Message the bot in any channel to get started.",
    })


# ---------------------------------------------------------------------------
# Tenant management endpoints
# ---------------------------------------------------------------------------

class SlackTenantUpdate(BaseModel):
    """Update a Slack tenant's configuration."""
    fund_name: Optional[str] = Field(None, description="Fund display name")
    allowed_channels: Optional[list] = Field(None, description="Restrict to specific channel IDs")
    allowed_users: Optional[list] = Field(None, description="Restrict to specific user IDs")
    fund_context: Optional[Dict[str, Any]] = Field(None, description="Fund params for orchestrator")
    slug: Optional[str] = Field(None, description="Fund slug (for linking with email tenant)")


@router.put("/tenants/{team_id}")
async def update_slack_tenant(team_id: str, update: SlackTenantUpdate):
    """Update a Slack workspace tenant's configuration."""
    tenant = get_slack_tenant(team_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if update.fund_name is not None:
        tenant["fund_name"] = update.fund_name
    if update.allowed_channels is not None:
        tenant["allowed_channels"] = update.allowed_channels
    if update.allowed_users is not None:
        tenant["allowed_users"] = update.allowed_users
    if update.fund_context is not None:
        tenant["fund_context"] = update.fund_context
    if update.slug is not None:
        tenant["slug"] = update.slug

    return {"status": "updated", "team_id": team_id}


@router.get("/tenants/{team_id}")
async def get_slack_tenant_info(team_id: str):
    """Get Slack tenant config (without sensitive data)."""
    tenant = get_slack_tenant(team_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "team_id": team_id,
        "team_name": tenant.get("team_name"),
        "slug": tenant.get("slug"),
        "allowed_channels_count": len(tenant.get("allowed_channels", [])),
        "allowed_users_count": len(tenant.get("allowed_users", [])),
        "has_fund_context": bool(tenant.get("fund_context")),
    }


# ---------------------------------------------------------------------------
# Audit & Health
# ---------------------------------------------------------------------------

@router.get("/audit")
async def get_slack_audit(limit: int = 50):
    """Return recent Slack audit log entries."""
    return {"entries": get_slack_audit_log(limit)}


@router.get("/health")
async def slack_health():
    """Health check for Slack integration."""
    return {
        "status": "healthy",
        "slack_client_configured": bool(settings.SLACK_CLIENT_ID),
        "signing_secret_configured": bool(settings.SLACK_SIGNING_SECRET),
        "workspaces_registered": len(
            __import__("app.services.slack_composer", fromlist=["SLACK_TENANT_REGISTRY"]).SLACK_TENANT_REGISTRY
        ),
    }
