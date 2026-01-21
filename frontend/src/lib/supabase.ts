import { createClient } from '@supabase/supabase-js';

function getSupabaseUrl() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) {
    throw new Error('NEXT_PUBLIC_SUPABASE_URL environment variable is required');
  }
  return url;
}

function getSupabaseAnonKey() {
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!key) {
    throw new Error('NEXT_PUBLIC_SUPABASE_ANON_KEY environment variable is required');
  }
  return key;
}

function getSupabaseServiceRoleKey() {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) {
    throw new Error('SUPABASE_SERVICE_ROLE_KEY environment variable is required');
  }
  return key;
}

// Optimized client configuration
const clientOptions = {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false, // Disable for better performance
  },
  global: {
    headers: {
      'X-Client-Info': 'vc-platform',
    },
  },
  db: {
    schema: 'public',
  },
};

const supabase = createClient(getSupabaseUrl(), getSupabaseAnonKey(), clientOptions);

// Service role client (server-side only, never expose to client)
export const supabaseService = createClient(getSupabaseUrl(), getSupabaseServiceRoleKey(), {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
  global: {
    headers: {
      'X-Client-Info': 'vc-platform-service',
    },
  },
});

export default supabase;
