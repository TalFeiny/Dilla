/**
 * Cloudflare Email Worker — catches inbound emails and forwards
 * structured payload to Dilla AI backend.
 *
 * Setup:
 * 1. Cloudflare Dashboard → Email Routing → Enable
 * 2. Create catch-all rule → Worker → this worker
 * 3. Set environment variables:
 *    - BACKEND_URL: Your backend URL (e.g. https://api.dilla.ai)
 *    - WEBHOOK_SECRET: Shared secret for signature verification
 *
 * The worker parses the email, computes an HMAC signature, and POSTs
 * the payload to your backend's /api/email/inbound endpoint.
 */

export default {
  async email(message, env, ctx) {
    const to = message.to;
    const from = message.from;
    const subject = message.headers.get("subject") || "(no subject)";
    const messageId = message.headers.get("message-id") || "";

    // Read the raw email body
    let textBody = "";
    try {
      const rawEmail = await new Response(message.raw).arrayBuffer();
      const decoded = new TextDecoder().decode(rawEmail);

      // Extract plain text body from raw email (simplified MIME parsing)
      // For production, consider using a proper MIME parser
      textBody = extractTextBody(decoded);
    } catch (e) {
      console.error("Failed to read email body:", e);
    }

    // Fall back to subject if body is empty
    if (!textBody.trim()) {
      textBody = subject;
    }

    // Build payload
    const payload = JSON.stringify({
      to: to,
      from: from,
      subject: subject,
      text: textBody,
      message_id: messageId,
    });

    // Compute HMAC signature
    const signature = await computeHMAC(payload, env.WEBHOOK_SECRET || "");

    // Forward to backend
    const backendUrl = env.BACKEND_URL || "http://localhost:8000";
    const endpoint = `${backendUrl}/api/email/inbound`;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Email-Signature": signature,
          "User-Agent": "Dilla-Email-Worker/1.0",
        },
        body: payload,
      });

      if (!response.ok) {
        console.error(`Backend returned ${response.status}: ${await response.text()}`);
      }
    } catch (e) {
      console.error("Failed to forward email to backend:", e);
      // Don't throw — Cloudflare will retry and we don't want duplicate processing
    }
  },
};

/**
 * Extract plain text body from raw MIME email.
 * Simplified parser — handles common cases.
 */
function extractTextBody(rawEmail) {
  // Split headers from body
  const headerBodySplit = rawEmail.indexOf("\r\n\r\n");
  if (headerBodySplit === -1) {
    const altSplit = rawEmail.indexOf("\n\n");
    if (altSplit === -1) return rawEmail;
    return rawEmail.substring(altSplit + 2);
  }

  const headers = rawEmail.substring(0, headerBodySplit);
  const body = rawEmail.substring(headerBodySplit + 4);

  // Check if multipart
  const boundaryMatch = headers.match(/boundary="?([^";\r\n]+)"?/i);
  if (boundaryMatch) {
    const boundary = boundaryMatch[1];
    const parts = body.split(`--${boundary}`);

    for (const part of parts) {
      // Look for text/plain part
      if (part.includes("Content-Type: text/plain") ||
          part.includes("content-type: text/plain")) {
        // Find the content after the part headers
        const partBodyStart = part.indexOf("\r\n\r\n");
        if (partBodyStart !== -1) {
          return part.substring(partBodyStart + 4).trim();
        }
        const altStart = part.indexOf("\n\n");
        if (altStart !== -1) {
          return part.substring(altStart + 2).trim();
        }
      }
    }
  }

  // Not multipart — return body as-is
  return body.trim();
}

/**
 * Compute HMAC-SHA256 signature for webhook verification.
 */
async function computeHMAC(payload, secret) {
  if (!secret) return "";

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );

  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));

  // Convert to hex string
  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
