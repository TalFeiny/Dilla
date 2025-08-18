import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Only log in development
if (process.env.NODE_ENV === 'development') {
  console.log('Supabase Config Debug:', {
    url: supabaseUrl,
    hasAnonKey: !!supabaseAnonKey,
    hasServiceKey: !!supabaseServiceRoleKey,
    nodeEnv: process.env.NODE_ENV
  });
}

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables:', {
    url: supabaseUrl,
    hasAnonKey: !!supabaseAnonKey
  });
  throw new Error('Missing Supabase environment variables. Please check your .env.local file.');
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

const supabase = createClient(supabaseUrl, supabaseAnonKey, clientOptions);

// Service role client (server-side only, never expose to client)
export const supabaseService = createClient(supabaseUrl, supabaseServiceRoleKey || supabaseAnonKey, {
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