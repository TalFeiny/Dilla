import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  // Check environment variables
  const envStatus = {
    NODE_ENV: process.env.NODE_ENV,
    TAVILY_API_KEY: process.env.TAVILY_API_KEY ? "SET" : "NOT SET",
    CLAUDE_API_KEY: process.env.CLAUDE_API_KEY ? "SET" : "NOT SET",
    ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY ? "SET" : "NOT SET",
    OPENAI_API_KEY: process.env.OPENAI_API_KEY ? "SET" : "NOT SET",
    SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ? "SET" : "NOT SET",
    
    // Check if keys are actually present
    TAVILY_KEY_LENGTH: process.env.TAVILY_API_KEY?.length || 0,
    CLAUDE_KEY_LENGTH: process.env.CLAUDE_API_KEY?.length || 0,
    
    // List all env vars starting with certain prefixes
    ENV_KEYS: Object.keys(process.env).filter(k => 
      k.includes("API") || k.includes("KEY") || k.includes("TAVILY") || k.includes("CLAUDE")
    ).sort()
  };

  return NextResponse.json(envStatus);
}
