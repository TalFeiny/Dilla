import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: path.join(process.cwd(), '.env.local') });

export const maxDuration = 300;

// STREAMING DISABLED - This endpoint is no longer functional
export async function POST(request: NextRequest) {
  return new Response(
    JSON.stringify({ 
      error: 'Streaming functionality has been disabled',
      message: 'Please use the non-streaming PWERM analysis endpoints instead'
    }),
    { 
      status: 410, // Gone
      headers: { 'Content-Type': 'application/json' }
    }
  );
}