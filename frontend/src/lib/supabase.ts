import { createClient, SupabaseClient } from '@supabase/supabase-js';

function getSupabaseUrl(): string | null {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || null;
}

function getSupabaseAnonKey(): string | null {
  return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || null;
}

function getSupabaseServiceRoleKey(): string | null {
  return process.env.SUPABASE_SERVICE_ROLE_KEY || null;
}

// Optimized client configuration. Use 'public' as const for schema compatibility.
const clientOptions = {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
    // Use a unique storage key to prevent conflicts with other instances
    storageKey: 'dilla-ai-supabase-auth',
  },
  global: {
    headers: {
      'X-Client-Info': 'vc-platform',
    },
  },
  db: {
    schema: 'public' as const,
  },
};

// Singleton pattern for client-side Supabase client
// This ensures only one instance is created, preventing the "Multiple GoTrueClient instances" warning
let supabase: SupabaseClient<any, 'public', any> | null = null;

function getSupabaseClient(): SupabaseClient<any, 'public', any> {
  // Return cached instance if already created
  if (supabase) {
    return supabase;
  }

  // Server-side: return null — only browser clients can use this
  if (typeof window === 'undefined') {
    return null as any;
  }

  const url = getSupabaseUrl();
  const anonKey = getSupabaseAnonKey();

  if (!url || !anonKey) {
    throw new Error('Supabase client not initialized: Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY');
  }

  supabase = createClient(url, anonKey, clientOptions) as SupabaseClient<any, 'public', any>;
  return supabase;
}

// Service role client - lazy initialization (server-side only)
// This prevents the service client from trying to access server-only env vars in the browser bundle
let supabaseService: SupabaseClient<any, 'public', any> | null = null;

// Only initialize on server side - this check prevents browser bundle from executing this code
// When this module is bundled for browser, window is defined, so this block is never executed
if (typeof window === 'undefined') {
  // We're on the server - safe to access SUPABASE_SERVICE_ROLE_KEY
  try {
    const url = getSupabaseUrl();
    const serviceKey = getSupabaseServiceRoleKey();

    if (url && serviceKey) {
      supabaseService = createClient(url, serviceKey, {
        auth: {
          autoRefreshToken: false,
          persistSession: false,
        },
        global: {
          headers: {
            'X-Client-Info': 'vc-platform-service',
          },
        },
      }) as SupabaseClient<any, 'public', any>;
      console.log('Supabase service client initialized successfully');
    } else {
      const missing = [];
      if (!url) missing.push('NEXT_PUBLIC_SUPABASE_URL');
      if (!serviceKey) missing.push('SUPABASE_SERVICE_ROLE_KEY');
      console.error(`Supabase service client not initialized: Missing ${missing.join(' and ')}`);
    }
  } catch (error) {
    console.error('Error initializing Supabase service client:', error);
    if (error instanceof Error) {
      console.error('Error details:', error.message, error.stack);
    }
  }
}

// Service role client (server-side only, never expose to client)
export { supabaseService };

// Export the getter function for explicit client access
export { getSupabaseClient };

// Default export - a lazy proxy that defers to getSupabaseClient() on first property access.
// The old code did `export default getSupabaseClient()` which ran at module load during SSR,
// got null (no window), and that null was permanently locked in as the default export.
// This proxy waits until something actually accesses .auth, .from(), etc. — which only
// happens client-side in 'use client' components — then initializes the real client.
const lazySupabase = new Proxy({} as SupabaseClient<any, 'public', any>, {
  get(_, prop) {
    const client = getSupabaseClient();
    const value = (client as any)[prop];
    return typeof value === 'function' ? value.bind(client) : value;
  },
});

export default lazySupabase;
