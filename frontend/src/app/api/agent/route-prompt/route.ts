import { NextResponse } from 'next/server';
import { advancedPromptRouter } from '@/lib/advanced-prompt-router';

export async function POST(request: Request) {
  try {
    const { prompt, context } = await request.json();
    
    if (!prompt) {
      return NextResponse.json(
        { error: 'Prompt is required' },
        { status: 400 }
      );
    }
    
    // Route the prompt
    const routingDecision = await advancedPromptRouter.route(prompt, context);
    
    // Log for debugging
    console.log('Routing decision:', {
      prompt: prompt.substring(0, 100),
      handler: routingDecision.handler,
      confidence: routingDecision.confidence,
      subtasks: routingDecision.decomposition.subTasks.length,
      complexity: routingDecision.decomposition.estimatedComplexity
    });
    
    return NextResponse.json({
      success: true,
      routing: routingDecision
    });
  } catch (error) {
    console.error('Error routing prompt:', error);
    return NextResponse.json(
      { error: 'Failed to route prompt', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request) {
  try {
    const { prompt, decision, outcome, feedback } = await request.json();
    
    if (!prompt || !decision || !outcome) {
      return NextResponse.json(
        { error: 'Prompt, decision, and outcome are required' },
        { status: 400 }
      );
    }
    
    // Learn from the routing outcome
    await advancedPromptRouter.learnFromOutcome(prompt, decision, outcome, feedback);
    
    return NextResponse.json({
      success: true,
      message: 'Learning data recorded'
    });
  } catch (error) {
    console.error('Error recording learning data:', error);
    return NextResponse.json(
      { error: 'Failed to record learning data', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}