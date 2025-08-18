import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: path.join(process.cwd(), '.env.local') });

export const maxDuration = 60; // 1 minute for testing

export async function POST(request: NextRequest) {
  console.log('PWERM Simple API called');
  
  try {
    const body = await request.json();
    console.log('Request body:', body);
    
    // For now, just test if we can return a response
    return NextResponse.json({
      success: true,
      message: 'PWERM Simple API is working',
      received: body,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('PWERM Simple API error:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}