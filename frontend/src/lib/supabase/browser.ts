import { createBrowserClient } from '@supabase/ssr';

let client: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowser() {
  if (client) return client;

  client = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
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
