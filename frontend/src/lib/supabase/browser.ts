import { createBrowserClient } from '@supabase/ssr';

let client: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowser() {
  if (typeof window === 'undefined') {
    // During SSR/prerender, return a dummy that won't blow up.
    // Real calls happen in useEffect (client-side only).
    return createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://localhost',
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'dummy',
    );
  }

  if (client) return client;

  client = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false, // callback handled server-side in /auth/callback
      },
      global: {
        headers: {
          'X-Client-Info': 'vc-platform',
        },
      },
      db: {
        schema: 'public' as const,
      },
      cookies: {
        encode: 'tokens-only',
        getAll() {
          return document.cookie
            .split('; ')
            .filter(Boolean)
            .map((pair) => {
              const idx = pair.indexOf('=');
              if (idx === -1) return { name: pair, value: '' };
              return {
                name: pair.substring(0, idx),
                value: decodeURIComponent(pair.substring(idx + 1)),
              };
            });
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            let str = `${name}=${encodeURIComponent(value)}`;
            if (options?.path) str += `; path=${options.path}`;
            if (options?.maxAge != null) str += `; max-age=${options.maxAge}`;
            if (options?.domain) str += `; domain=${options.domain}`;
            if (options?.sameSite) str += `; SameSite=${options.sameSite}`;
            if (options?.secure) str += `; Secure`;
            document.cookie = str;
          });
        },
      },
    }
  );

  return client;
}
