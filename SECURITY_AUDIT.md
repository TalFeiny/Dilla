# 🚨 CRITICAL SECURITY AUDIT - API Key Exposure

## Executive Summary
**CRITICAL**: Multiple API keys are exposed or accessible from the frontend, creating severe security vulnerabilities.

## Critical Issues Found

### 1. Direct API Key Access in Frontend Code ❌
These files should NEVER access API keys directly:

- `/lib/config/api-keys.ts` - Attempts to load API keys (even checking is bad)
- `/lib/intelligent-correction-detector.ts` - Line 4: Direct Anthropic key
- `/lib/self-learning-agent.ts` - Line 10: Direct API key access
- `/lib/firecrawl-scraper.ts` - Lines 4-5: Multiple API keys
- `/lib/rag-memory-system.ts` - Line 15: OpenAI key
- `/lib/mcp-tools-registry.ts` - Line 52: Tavily key
- `/lib/mcp/mcp-client.ts` - Line 297: Tavily key
- `/lib/mcp/mcp-server.ts` - Lines 20-22: Multiple keys

### 2. NEXT_PUBLIC_* Usage ❌
**NEVER use NEXT_PUBLIC_* for API keys!** These are bundled in client-side code:
- `NEXT_PUBLIC_ANTHROPIC_API_KEY` - Would expose Claude API key
- `NEXT_PUBLIC_TAVILY_API_KEY` - Would expose search API key
- `NEXT_PUBLIC_FIRECRAWL_API_KEY` - Would expose scraping API key

### 3. API Keys Sent to Backend ❌
Multiple routes send API keys from frontend to backend:
- `/api/pwerm-analysis/route.ts` - Lines 225-227
- `/api/companies/[id]/pwerm/route.ts` - Lines 177-179
- `/api/documents/process/route.ts` - Lines 116-119

## Security Best Practices

### ✅ CORRECT Approach:

1. **All API calls must go through backend API routes**
```typescript
// ❌ WRONG - Frontend calling external API
const response = await fetch('https://api.anthropic.com/v1/messages', {
  headers: { 'x-api-key': API_KEY } // EXPOSED!
});

// ✅ CORRECT - Frontend calls backend route
const response = await fetch('/api/agent/chat', {
  method: 'POST',
  body: JSON.stringify({ prompt })
});
// Backend route handles the external API call with server-side keys
```

2. **Never access process.env in frontend components**
```typescript
// ❌ WRONG - Frontend component
const key = process.env.ANTHROPIC_API_KEY;

// ✅ CORRECT - Backend API route only
export async function POST(request: Request) {
  const key = process.env.ANTHROPIC_API_KEY; // Server-side only
}
```

3. **Use environment variable validation**
```typescript
// Backend API route
if (!process.env.ANTHROPIC_API_KEY) {
  throw new Error('API key not configured');
}
```

## Immediate Actions Required

### Priority 1: Remove All Frontend API Key Access
1. Delete `/lib/config/api-keys.ts` entirely - it shouldn't exist
2. Remove all `process.env.*API_KEY` from `/lib/*` files
3. Move all external API calls to backend routes

### Priority 2: Create Secure Proxy Routes
All external API calls should go through backend proxies:

```typescript
// /app/api/proxy/anthropic/route.ts
export async function POST(request: Request) {
  const { prompt } = await request.json();
  
  // Server-side only
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    headers: {
      'x-api-key': process.env.ANTHROPIC_API_KEY!,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ 
      model: 'claude-3-5-sonnet-20241022',
      messages: [{ role: 'user', content: prompt }]
    })
  });
  
  return response;
}
```

### Priority 3: Environment Variable Security
1. **Never prefix sensitive keys with NEXT_PUBLIC_**
2. **Use .env.local for local development** (git ignored)
3. **Use secure environment variables in production** (Vercel, etc.)

### Priority 4: Code Review Checklist
- [ ] No API keys in frontend code
- [ ] No NEXT_PUBLIC_* for sensitive data
- [ ] All external APIs called through backend routes
- [ ] Environment variables validated on startup
- [ ] API routes check authentication before processing

## Production Deployment Checklist

### Before Deploying:
1. **Audit all environment variables**
   - Remove any NEXT_PUBLIC_* API keys
   - Ensure all keys are server-side only

2. **Review client bundle**
   ```bash
   npm run build
   # Check .next/static for any exposed keys
   grep -r "sk-" .next/static
   grep -r "claude-" .next/static
   ```

3. **Set up proper secrets management**
   - Use Vercel/AWS/Azure secret management
   - Rotate all potentially exposed keys
   - Set up key rotation schedule

4. **Monitor for exposures**
   - Set up GitHub secret scanning
   - Use tools like TruffleHog
   - Regular security audits

## Files Requiring Immediate Fix

### High Priority (Direct API key access):
1. `/lib/intelligent-correction-detector.ts`
2. `/lib/self-learning-agent.ts`
3. `/lib/firecrawl-scraper.ts`
4. `/lib/rag-memory-system.ts`
5. `/lib/config/api-keys.ts` - DELETE THIS FILE

### Medium Priority (Backend sending keys):
1. All `/app/api/**/route.ts` files sending keys to Python

### Low Priority (Already backend-only but needs review):
1. API routes that correctly use server-side keys

## Summary

**Current State**: INSECURE - API keys accessible from frontend
**Required State**: SECURE - All API keys server-side only
**Risk Level**: CRITICAL - Immediate action required

This is a production blocker and must be fixed before any deployment.