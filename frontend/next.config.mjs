import { config } from 'dotenv';
import { join } from 'path';

// Load server-side environment variables
if (process.env.NODE_ENV !== 'production') {
  config({ path: join(process.cwd(), '.env.local.server') });
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Performance optimizations
  reactStrictMode: false, // Disable double rendering in dev
  swcMinify: true, // Use SWC for faster minification
  
  // Experimental features for speed
  // No experimental features
  
  // Module transpilation for faster builds
  transpilePackages: ['@supabase/ssr', '@supabase/supabase-js'],
  
  // Disable type checking in build (run separately)
  typescript: {
    ignoreBuildErrors: true,
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
    // Dev-specific optimizations
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
        ignored: ['**/node_modules', '**/.git', '**/.next'],
      };
      
      // Reduce bundle size checks in dev
      config.performance = {
        hints: false,
      };
      
      // Use cache for faster rebuilds
      config.cache = {
        type: 'filesystem',
      };
    }
    
    // Exclude onnxruntime-node from client-side bundle
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      };
      
      // Safely handle externals configuration
      if (Array.isArray(config.externals)) {
        config.externals.push('onnxruntime-node');
      } else if (config.externals) {
        config.externals = [config.externals, 'onnxruntime-node'];
      } else {
        config.externals = ['onnxruntime-node'];
      }
    }
    
    // Handle binary files
    if (config.module && config.module.rules) {
      config.module.rules.push({
        test: /\.node$/,
        use: 'node-loader',
      });
    }
    
    return config;
  },
};

export default nextConfig;
