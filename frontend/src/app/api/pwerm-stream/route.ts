import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const runtime = 'nodejs';
export const maxDuration = 300; // 5 minutes

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