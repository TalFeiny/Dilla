"""Email Composer Service — turns orchestrator output into formatted emails with attachments.

Converts memo sections, deck PDFs, and chart PNGs into Resend-compatible
email payloads. Handles both inline HTML body and file attachments.

Security:
- Sender allowlist per tenant
- Webhook signature verification
- No raw email storage — process in memory only
- Audit logging for all inbound/outbound
"""

import base64
import hashlib
import hmac
import logging
import re
from datetime import datetime
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tenant model — in production, move to DB
# ---------------------------------------------------------------------------

# Each tenant maps an email slug to their fund context + allowed senders.
# Example: "acme-capital" → emails to acme-capital@dilla.ai are routed here
TENANT_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Populated at startup from DB or config.
    # Structure:
    # "slug": {
    #     "fund_name": "Acme Capital",
    #     "allowed_senders": ["partner@acme.com", "analyst@acme.com"],
    #     "fund_context": { ... },  # Same shape as unified brain context
    # }
}


def register_tenant(slug: str, config: Dict[str, Any]) -> None:
    """Register a tenant for email routing."""
    TENANT_REGISTRY[slug] = config
    logger.info(f"[EMAIL] Registered tenant: {slug}")


def get_tenant(slug: str) -> Optional[Dict[str, Any]]:
    """Look up tenant by email slug."""
    return TENANT_REGISTRY.get(slug)


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------

def verify_webhook_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """Verify that the inbound webhook came from our Cloudflare Worker."""
    secret = secret or settings.EMAIL_WEBHOOK_SECRET
    if not secret:
        logger.warning("[EMAIL] No EMAIL_WEBHOOK_SECRET configured — skipping verification")
        return True  # Allow in dev mode; enforce in production

    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Email parsing
# ---------------------------------------------------------------------------

def parse_tenant_from_address(to_address: str, domain: Optional[str] = None) -> Optional[str]:
    """Extract tenant slug from To: address.

    'acme-capital@dilla.ai' → 'acme-capital'
    """
    domain = domain or settings.EMAIL_FROM_DOMAIN
    _, addr = parseaddr(to_address)
    if not addr:
        return None
    local, at_domain = addr.rsplit("@", 1) if "@" in addr else (addr, "")
    if at_domain.lower() != domain.lower():
        return None
    return local.lower().strip()


def extract_company_names(text: str) -> List[str]:
    """Best-effort extraction of company names from email body.

    Looks for patterns like 'Series B - Acme Corp' or capitalized words.
    The orchestrator's own entity extraction will refine this.
    """
    # Common email forwarding patterns
    patterns = [
        r"(?:Series [A-Z]|Seed|Pre-Seed|Growth)\s*[-–—]\s*(.+?)(?:\n|$)",
        r"(?:Re:|Fwd:|FW:)\s*(.+?)(?:\n|$)",
    ]
    names = []
    for pat in patterns:
        for match in re.finditer(pat, text):
            candidate = match.group(1).strip()
            if 3 < len(candidate) < 80:
                names.append(candidate)
    return names


# ---------------------------------------------------------------------------
# Memo → HTML conversion
# ---------------------------------------------------------------------------

EMAIL_STYLES = """
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 680px; margin: 0 auto; padding: 20px; }
    h1 { font-size: 22px; border-bottom: 2px solid #2563eb; padding-bottom: 8px; color: #111; }
    h2 { font-size: 17px; color: #2563eb; margin-top: 28px; margin-bottom: 8px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
    th { background: #f1f5f9; text-align: left; padding: 8px 12px; border: 1px solid #e2e8f0; font-weight: 600; }
    td { padding: 8px 12px; border: 1px solid #e2e8f0; }
    tr:nth-child(even) { background: #f8fafc; }
    .metric { font-size: 24px; font-weight: 700; color: #2563eb; }
    .label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
    .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; }
    code { background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
    blockquote { border-left: 3px solid #2563eb; margin: 12px 0; padding: 8px 16px; background: #f8fafc; }
</style>
"""


def memo_sections_to_html(sections: List[Dict[str, Any]], title: str = "") -> str:
    """Convert memo sections (from LightweightMemoService) to email HTML."""
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        EMAIL_STYLES,
        "</head><body>",
    ]

    for section in sections:
        sec_type = section.get("type", "paragraph")
        content = section.get("content", "")

        if sec_type == "heading1":
            parts.append(f"<h1>{_escape(content)}</h1>")

        elif sec_type == "heading2":
            parts.append(f"<h2>{_escape(content)}</h2>")

        elif sec_type == "paragraph":
            # Memo narratives are markdown — convert basics to HTML
            parts.append(f"<div>{_markdown_to_html(content)}</div>")

        elif sec_type == "table":
            parts.append(_dict_table_to_html(section.get("rows", []), section.get("headers", [])))

        elif sec_type == "chart":
            # Charts can't render inline in email — note for attachment
            chart = section.get("chart", {})
            chart_type = chart.get("type", "chart")
            parts.append(
                f"<p><em>[{chart_type} chart attached as image]</em></p>"
            )

        elif sec_type == "code":
            parts.append(f"<pre><code>{_escape(content)}</code></pre>")

        elif sec_type == "metrics":
            # Render metric cards
            metrics = section.get("items", [])
            if metrics:
                parts.append("<table><tr>")
                for m in metrics[:6]:
                    parts.append(
                        f"<td style='text-align:center;padding:16px;'>"
                        f"<div class='metric'>{_escape(str(m.get('value', '')))}</div>"
                        f"<div class='label'>{_escape(str(m.get('label', '')))}</div>"
                        f"</td>"
                    )
                parts.append("</tr></table>")

    parts.append(
        "<div class='footer'>"
        f"Generated by Dilla AI &middot; {datetime.now().strftime('%B %d, %Y %H:%M UTC')}"
        "</div>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)


def _escape(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _markdown_to_html(text: str) -> str:
    """Minimal markdown → HTML for email bodies."""
    if not text:
        return ""
    lines = text.split("\n")
    html_lines = []
    in_table = False
    table_rows: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Markdown table row
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                table_rows = []
            # Skip separator rows (|---|---|)
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            table_rows.append(stripped)
            continue
        elif in_table:
            html_lines.append(_render_md_table(table_rows))
            in_table = False
            table_rows = []

        # Bold
        stripped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
        # Italic
        stripped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", stripped)
        # Inline code
        stripped = re.sub(r"`(.+?)`", r"<code>\1</code>", stripped)
        # Bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            stripped = f"&bull; {stripped[2:]}"

        if stripped:
            html_lines.append(f"<p>{stripped}</p>")
        else:
            html_lines.append("<br>")

    if in_table:
        html_lines.append(_render_md_table(table_rows))

    return "\n".join(html_lines)


def _render_md_table(rows: List[str]) -> str:
    """Convert markdown table rows to HTML table."""
    if not rows:
        return ""
    html = ["<table>"]
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row.strip("|").split("|")]
        tag = "th" if i == 0 else "td"
        html.append("<tr>" + "".join(f"<{tag}>{_escape(c)}</{tag}>" for c in cells) + "</tr>")
    html.append("</table>")
    return "\n".join(html)


def _dict_table_to_html(rows: List[Dict], headers: List[str]) -> str:
    """Convert list-of-dicts table to HTML."""
    if not rows:
        return ""
    if not headers and rows:
        headers = list(rows[0].keys())
    html = ["<table><tr>"]
    html.extend(f"<th>{_escape(h)}</th>" for h in headers)
    html.append("</tr>")
    for row in rows:
        html.append("<tr>")
        for h in headers:
            html.append(f"<td>{_escape(str(row.get(h, '')))}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


# ---------------------------------------------------------------------------
# Email composer — builds the final Resend payload
# ---------------------------------------------------------------------------

class EmailComposer:
    """Builds Resend-compatible email payloads from orchestrator output."""

    def compose_from_orchestrator_result(
        self,
        result: Dict[str, Any],
        to_address: str,
        from_address: str,
        subject: str,
        thread_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a complete email payload from an orchestrator result.

        Handles all output formats: docs/memo, deck, analysis, matrix.
        """
        attachments: List[Dict[str, Any]] = []

        # Extract the inner result if wrapped
        inner = result.get("result", result)
        fmt = inner.get("format", "analysis")

        # Build HTML body from whatever format we got
        if fmt == "docs" and "sections" in inner:
            # Memo output — rich HTML from sections
            html_body = memo_sections_to_html(
                inner["sections"], inner.get("title", subject)
            )
        elif fmt == "deck" and "slides" in inner:
            # Deck output — summary of slides as HTML + PDF attachment
            html_body = self._slides_to_summary_html(inner["slides"], subject)
        else:
            # Analysis / matrix / other — render data as structured HTML
            html_body = self._generic_result_to_html(inner, subject)

        # Collect PDF attachment if deck was generated
        if fmt == "deck" and inner.get("pdf_bytes"):
            attachments.append({
                "filename": self._safe_filename(subject, "pdf"),
                "content": list(inner["pdf_bytes"]),
            })

        # Collect any chart images
        for chart in inner.get("charts", []):
            if chart.get("png_bytes"):
                chart_name = chart.get("title", "chart").replace(" ", "_")
                attachments.append({
                    "filename": f"{chart_name}.png",
                    "content": list(chart["png_bytes"]),
                })

        payload = {
            "from": from_address,
            "to": to_address,
            "subject": subject,
            "html": html_body,
        }
        if attachments:
            payload["attachments"] = attachments
        if thread_message_id:
            payload["headers"] = {
                "In-Reply-To": thread_message_id,
                "References": thread_message_id,
            }

        return payload

    def compose_error_reply(
        self,
        to_address: str,
        from_address: str,
        subject: str,
        error_message: str,
    ) -> Dict[str, Any]:
        """Build a polite error reply when processing fails."""
        html = (
            f"<!DOCTYPE html><html><head>{EMAIL_STYLES}</head><body>"
            f"<h1>Couldn't process your request</h1>"
            f"<p>I received your email but wasn't able to complete the analysis:</p>"
            f"<blockquote>{_escape(error_message)}</blockquote>"
            f"<p>Try rephrasing your request or reply to this email with more context.</p>"
            f"<div class='footer'>Dilla AI &middot; {datetime.now().strftime('%B %d, %Y')}</div>"
            f"</body></html>"
        )
        return {
            "from": from_address,
            "to": to_address,
            "subject": f"Re: {subject}",
            "html": html,
        }

    def _slides_to_summary_html(self, slides: List[Dict], subject: str) -> str:
        """Render deck slides as an HTML summary (full PDF attached separately)."""
        parts = [
            f"<!DOCTYPE html><html><head>{EMAIL_STYLES}</head><body>",
            f"<h1>{_escape(subject)}</h1>",
            f"<p><strong>{len(slides)} slides</strong> — full deck attached as PDF.</p>",
            "<hr>",
        ]
        for i, slide in enumerate(slides, 1):
            title = slide.get("title", f"Slide {i}")
            parts.append(f"<h2>{i}. {_escape(title)}</h2>")
            # Include bullet points if present
            bullets = slide.get("bullets") or slide.get("content", [])
            if isinstance(bullets, list):
                for bullet in bullets[:5]:
                    if isinstance(bullet, str):
                        parts.append(f"<p>&bull; {_escape(bullet)}</p>")
                    elif isinstance(bullet, dict):
                        parts.append(f"<p>&bull; {_escape(str(bullet.get('text', '')))}</p>")
        parts.append(
            f"<div class='footer'>Generated by Dilla AI &middot; "
            f"{datetime.now().strftime('%B %d, %Y')}</div></body></html>"
        )
        return "\n".join(parts)

    def _generic_result_to_html(self, result: Dict[str, Any], subject: str) -> str:
        """Render a generic analysis result as HTML."""
        parts = [
            f"<!DOCTYPE html><html><head>{EMAIL_STYLES}</head><body>",
            f"<h1>{_escape(subject)}</h1>",
        ]

        # Companies summary
        companies = result.get("companies", [])
        if companies:
            parts.append("<h2>Companies Analyzed</h2><table><tr>"
                         "<th>Company</th><th>Stage</th><th>Revenue</th>"
                         "<th>Valuation</th></tr>")
            for c in companies[:10]:
                name = c.get("company", "Unknown")
                stage = c.get("stage", "—")
                rev = c.get("revenue") or c.get("inferred_revenue") or 0
                val = c.get("valuation", 0)
                rev_str = f"${rev / 1e6:,.1f}M" if rev and rev > 0 else "—"
                val_str = f"${val / 1e6:,.0f}M" if val and val > 0 else "—"
                parts.append(
                    f"<tr><td><strong>{_escape(name)}</strong></td>"
                    f"<td>{_escape(stage)}</td>"
                    f"<td>{rev_str}</td><td>{val_str}</td></tr>"
                )
            parts.append("</table>")

        # Investment analysis
        analysis = result.get("investment_analysis") or result.get("data", {})
        if isinstance(analysis, dict):
            for key, value in analysis.items():
                if isinstance(value, str) and len(value) > 20:
                    parts.append(f"<h2>{_escape(key.replace('_', ' ').title())}</h2>")
                    parts.append(f"<div>{_markdown_to_html(value)}</div>")

        parts.append(
            f"<div class='footer'>Generated by Dilla AI &middot; "
            f"{datetime.now().strftime('%B %d, %Y')}</div></body></html>"
        )
        return "\n".join(parts)

    @staticmethod
    def _safe_filename(subject: str, ext: str) -> str:
        """Create a filesystem-safe filename from email subject."""
        clean = re.sub(r"[^a-zA-Z0-9\s\-_]", "", subject)
        clean = re.sub(r"\s+", "_", clean.strip())[:60]
        return f"{clean or 'dilla_report'}.{ext}"


# ---------------------------------------------------------------------------
# Resend sender — thin wrapper
# ---------------------------------------------------------------------------

async def send_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send an email via Resend API."""
    api_key = settings.RESEND_API_KEY
    if not api_key:
        logger.error("[EMAIL] RESEND_API_KEY not configured")
        return {"success": False, "error": "Resend API key not configured"}

    try:
        import resend
        resend.api_key = api_key

        result = resend.Emails.send(payload)
        logger.info(f"[EMAIL] Sent to {payload.get('to')} — id: {result.get('id', 'unknown')}")
        return {"success": True, "id": result.get("id")}

    except Exception as e:
        logger.error(f"[EMAIL] Send failed: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Audit log — append-only, no email content stored
# ---------------------------------------------------------------------------

_audit_log: List[Dict[str, Any]] = []


def audit_log(action: str, **kwargs) -> None:
    """Log an email event (no message content stored)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        **{k: v for k, v in kwargs.items() if k not in ("body", "html", "raw", "attachments")},
    }
    _audit_log.append(entry)
    logger.info(f"[EMAIL-AUDIT] {action}: {entry}")


def get_audit_log(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent audit entries."""
    return _audit_log[-limit:]
