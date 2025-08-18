import { NextRequest, NextResponse } from 'next/server';

export async function GET() {
  try {
    // Return empty scenarios array for now
    // This will be populated by the PWERM scenarios API
    const scenarios = [];
    
    return NextResponse.json({ scenarios });
  } catch (error) {
    console.error('Error in GET /api/scenarios:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 