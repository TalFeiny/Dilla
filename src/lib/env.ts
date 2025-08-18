import fs from 'fs';
import path from 'path';

// Cache for environment variables
let envCache: { [key: string]: string } = {};
let lastLoaded = 0;
const CACHE_DURATION = 5000; // 5 seconds

export function getEnvVariable(key: string): string {
  const now = Date.now();
  
  // Reload if cache is expired or empty
  if (now - lastLoaded > CACHE_DURATION || Object.keys(envCache).length === 0) {
    loadEnvVariables();
    lastLoaded = now;
  }
  
  return envCache[key] || process.env[key] || '';
}

function loadEnvVariables() {
  // First, try to use process.env
  envCache = {};
  
  // List of keys we care about
  const keys = ['TAVILY_API_KEY', 'CLAUDE_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 
                'NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_ANON_KEY', 'SUPABASE_SERVICE_ROLE_KEY'];
  
  // Try to get from process.env first
  for (const key of keys) {
    if (process.env[key]) {
      envCache[key] = process.env[key];
    }
  }
  
  // Then try to read from .env.local file
  try {
    const envPath = path.join(process.cwd(), '.env.local');
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf8');
      const lines = content.split('\n');
      
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        
        const equalIndex = trimmed.indexOf('=');
        if (equalIndex === -1) continue;
        
        const key = trimmed.substring(0, equalIndex).trim();
        let value = trimmed.substring(equalIndex + 1).trim();
        
        // Remove surrounding quotes if present
        if ((value.startsWith('"') && value.endsWith('"')) || 
            (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        
        // Only override if we don't have it from process.env
        if (keys.includes(key) && !envCache[key]) {
          envCache[key] = value;
        }
      }
    }
  } catch (error) {
    console.error('Error loading .env.local:', error);
  }
}