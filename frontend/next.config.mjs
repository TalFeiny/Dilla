import { config } from 'dotenv';
import { join } from 'path';

// Load server-side environment variables
if (process.env.NODE_ENV !== 'production') {
  config({ path: join(process.cwd(), '.env.local.server') });
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXTAUTH_URL: process.env.NEXTAUTH_URL || 'http://localhost:3001',
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET || 'dev-secret-change-in-production',
  },
  async redirects() {
    return [
      { source: '/favicon.ico', destination: '/dilla-logo.svg', permanent: false },
      { source: '/matrix', destination: '/matrix-control-panel', permanent: false },
    ];
  },
  // Performance optimizations
  reactStrictMode: false, // Disable double rendering in dev
  swcMinify: true, // Use SWC for faster minification
  
  // Experimental features for speed
  // No experimental features
  
  // Module transpilation for faster builds
  transpilePackages: ['@supabase/ssr', '@supabase/supabase-js'],

  // Keep heavy server-only packages out of function bundles
  serverExternalPackages: ['@react-pdf/renderer'],
  
  // Enable type checking in build for production safety
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: './tsconfig.json',
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  
  // Compiler options for performance
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },
  
  webpack: (config, { isServer, dev }) => {
    // Dev-only: lighter watch options
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
        ignored: [
          '**/node_modules/**',
          '**/.git/**',
          '**/.next/**',
          '**/.turbo/**',
          '**/coverage/**',
          '**/dist/**',
          '**/.cache/**',
          join(process.cwd(), '..', 'backend', '**'),
          join(process.cwd(), '..', 'scripts', '**'),
          join(process.cwd(), '..', 'supabase', '**'),
        ],
      };
      config.performance = { hints: false };
    }
    // Client: avoid bundling Node builtins (no externals override - was breaking chunks)
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      };
    }
    return config;
  },
};

export default nextConfig;
