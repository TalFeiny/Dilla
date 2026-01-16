import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const deckId = params.id;
    
    console.log(`[DECK_DATA_API] Request for deck ID: ${deckId}`);
    
    if (!deckId) {
      console.error('[DECK_DATA_API] No deck ID provided');
      return NextResponse.json(
        { error: 'Deck ID is required' },
        { status: 400 }
      );
    }

    // Fetch deck data from backend storage service
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    const backendEndpoint = `${backendUrl}/api/deck-storage/${deckId}`;
    
    console.log(`[DECK_DATA_API] Fetching from backend: ${backendEndpoint}`);
    
    const response = await fetch(backendEndpoint, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      // Add timeout to prevent hanging
      signal: AbortSignal.timeout(10000), // 10 second timeout
    });

    console.log(`[DECK_DATA_API] Backend response status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[DECK_DATA_API] Backend error: ${response.status} - ${errorText}`);
      
      if (response.status === 404) {
        return NextResponse.json(
          { error: 'Deck not found', deckId },
          { status: 404 }
        );
      }
      throw new Error(`Backend responded with ${response.status}: ${errorText}`);
    }

    const deckData = await response.json();
    console.log(`[DECK_DATA_API] Successfully retrieved deck with ${deckData.slides?.length || 0} slides`);
    
    return NextResponse.json(deckData);
  } catch (error) {
    console.error('[DECK_DATA_API] Error retrieving deck:', error);
    
    // Handle different types of errors
    if (error instanceof Error) {
      if (error.name === 'TimeoutError') {
        return NextResponse.json(
          { error: 'Backend request timed out', deckId: params.id },
          { status: 504 }
        );
      }
      if (error.message.includes('fetch')) {
        return NextResponse.json(
          { error: 'Cannot connect to backend service', deckId: params.id },
          { status: 503 }
        );
      }
    }
    
    return NextResponse.json(
      { error: 'Failed to retrieve deck data', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
