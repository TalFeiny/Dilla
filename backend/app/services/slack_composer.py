"""Slack Composer Service — turns orchestrator output into Slack Block Kit messages.

Converts memo sections, deck summaries, and analysis results into Slack-compatible
Block Kit JSON payloads. Handles sending via the Slack Web API.

Security:
- Slack request signature verification (signing secret)
- Per-tenant bot token storage (OAuth2 install flow)
- No raw message storage — process in memory only
- Audit logging for all inbound/outbound
"""

import hashlib
import hmac
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tenant model for Slack — in production, move to DB
# ---------------------------------------------------------------------------
# Each tenant maps a Slack team_id to their fund context + bot token.
# Populated when a workspace installs the Dilla Slack app via OAuth.

SLACK_TENANT_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_slack_tenant(team_id: str, config: Dict[str, Any]) -> None:
    """Register a Slack workspace as a tenant."""
    SLACK_TENANT_REGISTRY[team_id] = config
    logger.info(f"[SLACK] Registered tenant: {team_id} ({config.get('team_name', 'unknown')})")


def get_slack_tenant(team_id: str) -> Optional[Dict[str, Any]]:
    """Look up tenant by Slack team ID."""
    return SLACK_TENANT_REGISTRY.get(team_id)


def get_slack_tenant_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Look up a Slack tenant by fund slug (for linking email + slack tenants)."""
    for _team_id, config in SLACK_TENANT_REGISTRY.items():
        if config.get("slug") == slug:
            return config
    return None


# ---------------------------------------------------------------------------
# Slack request signature verification
# ---------------------------------------------------------------------------

def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    signing_secret: Optional[str] = None,
) -> bool:
    """Verify that the request came from Slack using the signing secret.

    Slack signs requests with: v0=HMAC-SHA256(signing_secret, "v0:{timestamp}:{body}")
    """
    secret = signing_secret or settings.SLACK_SIGNING_SECRET
    if not secret:
        logger.warning("[SLACK] No SLACK_SIGNING_SECRET configured — skipping verification")
        return True  # Allow in dev mode; enforce in production

    # Reject requests older than 5 minutes (replay protection)
    try:
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("[SLACK] Request timestamp too old — possible replay")
            return False
    except (ValueError, TypeError):
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Block Kit composer — builds Slack message payloads
# ---------------------------------------------------------------------------

# Slack limits: 50 blocks per message, 3000 chars per text block
MAX_BLOCKS = 48  # Leave room for header/footer
MAX_TEXT_LENGTH = 2900  # Leave margin under 3000 char limit


def _truncate(text: str, max_len: int = MAX_TEXT_LENGTH) -> str:
    """Truncate text to fit Slack block limits."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _escape_mrkdwn(text: str) -> str:
    """Escape special characters for Slack mrkdwn format."""
    # Slack uses its own markdown variant
    # Don't double-escape if already escaped
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


class SlackComposer:
    """Builds Slack Block Kit payloads from orchestrator output."""

    def compose_from_orchestrator_result(
        self,
        result: Dict[str, Any],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks from an orchestrator result.

        Handles all output formats: docs/memo, deck, analysis, matrix.
        Returns a list of Slack blocks.
        """
        inner = result.get("result", result)
        fmt = inner.get("format", "analysis")

        blocks: List[Dict[str, Any]] = []

        if fmt == "docs" and "sections" in inner:
            blocks = self._memo_to_blocks(inner["sections"], inner.get("title", "Analysis"))
        elif fmt == "deck" and "slides" in inner:
            blocks = self._deck_to_blocks(inner["slides"], inner.get("title", "Deck"))
        else:
            blocks = self._analysis_to_blocks(inner, query)

        # Add footer
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_Dilla AI · {datetime.now().strftime('%B %d, %Y %H:%M UTC')}_",
            }],
        })

        return blocks[:MAX_BLOCKS]

    def compose_error_message(self, error_message: str) -> List[Dict[str, Any]]:
        """Build blocks for an error reply."""
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Couldn't process your request"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "I received your message but wasn't able to complete the analysis:\n\n"
                        f"> {_escape_mrkdwn(error_message)}\n\n"
                        "Try rephrasing your request or send another message with more context."
                    ),
                },
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"_Dilla AI · {datetime.now().strftime('%B %d, %Y')}_",
                }],
            },
        ]

    def compose_thinking_message(self) -> List[Dict[str, Any]]:
        """Build blocks for a 'thinking' acknowledgment."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":hourglass_flowing_sand: *Analyzing...* I'll reply in this thread when the analysis is ready.",
                },
            },
        ]

    # --- Format-specific renderers ---

    def _memo_to_blocks(
        self, sections: List[Dict[str, Any]], title: str
    ) -> List[Dict[str, Any]]:
        """Convert memo sections to Slack blocks."""
        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title[:150]},
            }
        ]

        for section in sections:
            if len(blocks) >= MAX_BLOCKS:
                break

            sec_type = section.get("type", "paragraph")
            content = section.get("content", "")

            if sec_type == "heading1":
                blocks.append({
                    "type": "header",
                    "text": {"type": "plain_text", "text": content[:150]},
                })

            elif sec_type == "heading2":
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{_escape_mrkdwn(content)}*"},
                })

            elif sec_type == "paragraph":
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": _truncate(_md_to_slack_mrkdwn(content))},
                })

            elif sec_type == "table":
                table_text = _dict_table_to_mrkdwn(
                    section.get("rows", []), section.get("headers", [])
                )
                if table_text:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": _truncate(table_text)},
                    })

            elif sec_type == "code":
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{_truncate(content)}```"},
                })

            elif sec_type == "metrics":
                metrics = section.get("items", [])
                if metrics:
                    fields = []
                    for m in metrics[:10]:  # Slack allows 10 fields
                        label = str(m.get("label", ""))
                        value = str(m.get("value", ""))
                        fields.append({
                            "type": "mrkdwn",
                            "text": f"*{_escape_mrkdwn(label)}*\n{_escape_mrkdwn(value)}",
                        })
                    blocks.append({"type": "section", "fields": fields})

            elif sec_type == "chart":
                chart = section.get("chart", {})
                chart_type = chart.get("type", "chart")
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"_[{chart_type} chart — view in Dilla dashboard for full visualization]_",
                    }],
                })

        return blocks

    def _deck_to_blocks(
        self, slides: List[Dict], title: str
    ) -> List[Dict[str, Any]]:
        """Render deck slides as a Slack summary."""
        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title[:150]},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(slides)} slides* — full deck available in the Dilla dashboard.",
                },
            },
            {"type": "divider"},
        ]

        for i, slide in enumerate(slides, 1):
            if len(blocks) >= MAX_BLOCKS:
                break
            slide_title = slide.get("title", f"Slide {i}")
            bullets = slide.get("bullets") or slide.get("content", [])
            bullet_text = ""
            if isinstance(bullets, list):
                for bullet in bullets[:5]:
                    if isinstance(bullet, str):
                        bullet_text += f"• {_escape_mrkdwn(bullet)}\n"
                    elif isinstance(bullet, dict):
                        bullet_text += f"• {_escape_mrkdwn(str(bullet.get('text', '')))}\n"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _truncate(f"*{i}. {_escape_mrkdwn(slide_title)}*\n{bullet_text}"),
                },
            })

        return blocks

    def _analysis_to_blocks(
        self, result: Dict[str, Any], query: str
    ) -> List[Dict[str, Any]]:
        """Render a generic analysis result as Slack blocks."""
        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": (query or "Analysis")[:150]},
            },
        ]

        # Companies summary table
        companies = result.get("companies", [])
        if companies:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Companies Analyzed*"},
            })
            for c in companies[:8]:
                name = c.get("company", "Unknown")
                stage = c.get("stage", "—")
                rev = c.get("revenue") or c.get("inferred_revenue") or 0
                val = c.get("valuation", 0)
                rev_str = f"${rev / 1e6:,.1f}M" if rev and rev > 0 else "—"
                val_str = f"${val / 1e6:,.0f}M" if val and val > 0 else "—"
                blocks.append({
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*{_escape_mrkdwn(name)}*\n{_escape_mrkdwn(stage)}"},
                        {"type": "mrkdwn", "text": f"*Revenue:* {rev_str}\n*Valuation:* {val_str}"},
                    ],
                })
                if len(blocks) >= MAX_BLOCKS:
                    break

        # Investment analysis narrative sections
        analysis = result.get("investment_analysis") or result.get("data", {})
        if isinstance(analysis, dict):
            for key, value in analysis.items():
                if len(blocks) >= MAX_BLOCKS:
                    break
                if isinstance(value, str) and len(value) > 20:
                    heading = key.replace("_", " ").title()
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": _truncate(f"*{_escape_mrkdwn(heading)}*\n{_md_to_slack_mrkdwn(value)}"),
                        },
                    })

        return blocks


# ---------------------------------------------------------------------------
# Markdown → Slack mrkdwn conversion
# ---------------------------------------------------------------------------

def _md_to_slack_mrkdwn(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn format."""
    if not text:
        return ""
    # Headers → bold
    text = re.sub(r"^###\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold (already compatible: **text** → *text* in Slack)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Inline code (already compatible)
    # Links: [text](url) → <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    # Bullet points: - item → • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text


def _dict_table_to_mrkdwn(rows: List[Dict], headers: List[str]) -> str:
    """Convert a list-of-dicts table to a Slack mrkdwn text table."""
    if not rows:
        return ""
    if not headers and rows:
        headers = list(rows[0].keys())

    # Build a simple text table (Slack doesn't support real tables in blocks)
    lines = ["*" + " | ".join(_escape_mrkdwn(h) for h in headers) + "*"]
    for row in rows[:15]:  # Limit rows to stay within text limits
        cells = [str(row.get(h, "")) for h in headers]
        lines.append(" | ".join(_escape_mrkdwn(c) for c in cells))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slack Web API — send messages
# ---------------------------------------------------------------------------

async def send_slack_message(
    token: str,
    channel: str,
    blocks: List[Dict[str, Any]],
    thread_ts: Optional[str] = None,
    text: str = "Dilla AI analysis",
) -> Dict[str, Any]:
    """Send a message to Slack via chat.postMessage.

    Args:
        token: Bot OAuth token (xoxb-...)
        channel: Channel or DM ID
        blocks: Block Kit blocks
        thread_ts: Thread timestamp to reply in (for threaded conversations)
        text: Fallback text for notifications
    """
    payload: Dict[str, Any] = {
        "channel": channel,
        "blocks": blocks,
        "text": text,  # Fallback for notifications / non-block-kit clients
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        data = resp.json()

    if not data.get("ok"):
        error = data.get("error", "unknown")
        logger.error(f"[SLACK] chat.postMessage failed: {error}")
        return {"success": False, "error": error}

    logger.info(f"[SLACK] Sent message to {channel} — ts: {data.get('ts', 'unknown')}")
    return {"success": True, "ts": data.get("ts"), "channel": data.get("channel")}


async def update_slack_message(
    token: str,
    channel: str,
    ts: str,
    blocks: List[Dict[str, Any]],
    text: str = "Dilla AI analysis",
) -> Dict[str, Any]:
    """Update an existing Slack message (e.g., replace 'thinking' with result)."""
    payload = {
        "channel": channel,
        "ts": ts,
        "blocks": blocks,
        "text": text,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.update",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        data = resp.json()

    if not data.get("ok"):
        error = data.get("error", "unknown")
        logger.error(f"[SLACK] chat.update failed: {error}")
        return {"success": False, "error": error}

    return {"success": True, "ts": data.get("ts")}


async def exchange_oauth_code(code: str) -> Dict[str, Any]:
    """Exchange an OAuth authorization code for a bot token.

    Called during the OAuth install callback.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
            },
            timeout=15.0,
        )
        data = resp.json()

    if not data.get("ok"):
        error = data.get("error", "unknown")
        logger.error(f"[SLACK] OAuth exchange failed: {error}")
        return {"success": False, "error": error}

    return {
        "success": True,
        "team_id": data.get("team", {}).get("id"),
        "team_name": data.get("team", {}).get("name"),
        "bot_token": data.get("access_token"),
        "bot_user_id": data.get("bot_user_id"),
        "scope": data.get("scope"),
    }


# ---------------------------------------------------------------------------
# Audit log — append-only, no message content stored
# ---------------------------------------------------------------------------

_slack_audit_log: List[Dict[str, Any]] = []


def slack_audit_log(action: str, **kwargs) -> None:
    """Log a Slack event (no message content stored)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        **{k: v for k, v in kwargs.items() if k not in ("text", "blocks", "raw")},
    }
    _slack_audit_log.append(entry)
    logger.info(f"[SLACK-AUDIT] {action}: {entry}")


def get_slack_audit_log(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent Slack audit entries."""
    return _slack_audit_log[-limit:]
