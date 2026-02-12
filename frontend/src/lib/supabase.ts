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
let supabaseInitialized = false;

function getSupabaseClient(): SupabaseClient<any, 'public', any> | null {
  // Only initialize once, even if called multiple times
  if (supabaseInitialized) {
    return supabase;
  }

  // Only initialize on client side
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const url = getSupabaseUrl();
    const anonKey = getSupabaseAnonKey();

    if (url && anonKey) {
      supabase = createClient(url, anonKey, clientOptions) as SupabaseClient<any, 'public', any>;
      supabaseInitialized = true;
    } else {
      console.warn('Supabase client not initialized: Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY');
      supabaseInitialized = true; // Mark as initialized to prevent retries
    }
  } catch (error) {
    console.error('Error initializing Supabase client:', error);
    supabaseInitialized = true; // Mark as initialized to prevent retries
  }

  return supabase;
}

// Initialize on module load for client-side (backward compatibility)
// But use lazy initialization to prevent issues during SSR
if (typeof window !== 'undefined') {
  getSupabaseClient();
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

// Default export - lazy initialization for backward compatibility
// This ensures the client is only created when accessed, preventing SSR/hydration issues
// and ensuring only one instance is ever created
export default getSupabaseClient();
