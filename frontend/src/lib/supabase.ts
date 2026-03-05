/**
 * Backwards-compatibility shim.
 *
 * ALL Supabase client creation now lives in:
 *   - lib/supabase/browser.ts   (browser, cookie-based via @supabase/ssr)
 *   - lib/supabase/server.ts    (server components & route handlers)
 *   - lib/supabase/middleware.ts (session refresh in Next.js middleware)
 *
 * This file re-exports a service-role singleton so the 60+ API routes
 * that do `import { supabaseService } from '@/lib/supabase'` keep working
 * without any import changes.
 *
 * DO NOT add new client creation here.
 */

import { getSupabaseServiceRole } from './supabase/server';
import { getSupabaseBrowser } from './supabase/browser';

// ── Service-role singleton (server-side only, bypasses RLS) ──
// Lazy — created on first access so env vars are available.
let _serviceInstance: ReturnType<typeof getSupabaseServiceRole> | null = null;

function getServiceInstance() {
  if (typeof window !== 'undefined') {
    throw new Error(
      'supabaseService is server-only. Use getSupabaseBrowser() for client-side code.'
    );
  }
  if (!_serviceInstance) {
    _serviceInstance = getSupabaseServiceRole();
  }
  return _serviceInstance;
}

// Proxy so callers can do `supabaseService.from(...)` without calling a function.
export const supabaseService = new Proxy({} as ReturnType<typeof getSupabaseServiceRole>, {
  get(_, prop) {
    const client = getServiceInstance();
    const value = (client as any)[prop];
    return typeof value === 'function' ? value.bind(client) : value;
  },
});

// ── Default export = browser client (for lib/api.ts etc.) ──
// Uses the NEW cookie-based client, NOT the old localStorage one.
export default new Proxy({} as ReturnType<typeof getSupabaseBrowser>, {
  get(_, prop) {
    const client = getSupabaseBrowser();
    const value = (client as any)[prop];
    return typeof value === 'function' ? value.bind(client) : value;
  },
});
