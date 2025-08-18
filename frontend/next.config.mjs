/** @type {import('next').NextConfig} */
const nextConfig = {
  // Performance optimizations
  reactStrictMode: false, // Disable double rendering in dev
  swcMinify: true, // Use SWC for faster minification
  
  // Experimental features for speed
  experimental: {
    optimizeCss: true,
  },
  
  // Module transpilation for faster builds
  transpilePackages: ['@supabase/ssr', '@supabase/supabase-js'],
  
  // Disable type checking in build (run separately)
  typescript: {
    ignoreBuildErrors: true,
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
      
      config.externals = [...(config.externals || []), 'onnxruntime-node'];
    }
    
    // Handle binary files
    config.module.rules.push({
      test: /\.node$/,
      use: 'node-loader',
    });
    
    return config;
  },
};

export default nextConfig;
