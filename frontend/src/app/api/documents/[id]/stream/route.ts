import { NextRequest } from 'next/server';
import { supabaseService } from '@/lib/supabase';

// STREAMING DISABLED - This endpoint is no longer functional
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return new Response(
    JSON.stringify({ 
      error: 'Streaming functionality has been disabled',
      message: 'Please use the non-streaming endpoints instead'
    }),
    { 
      status: 410, // Gone
      headers: { 'Content-Type': 'application/json' }
    }
  );
} 