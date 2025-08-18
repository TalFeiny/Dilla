import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: NextRequest) {
  try {
    const { query, company, agent } = await request.json();
    
    console.log(`🔍 Retrieving RL context for: ${company || query?.substring(0, 50)}`);
    
    // Get recent feedback to improve the model - BOTH positive and negative
    let relevantFeedback = [];
    
    // Get ALL recent feedback to learn from mistakes AND successes
    const { data: recentFeedback } = await supabase
      .from('model_corrections')
      .select('*')
      .eq('model_type', agent || 'reasoning-agent') // Same type of agent
      .order('created_at', { ascending: false })
      .limit(10);
    
    if (recentFeedback && recentFeedback.length > 0) {
      relevantFeedback = recentFeedback;
      console.log(`Found ${recentFeedback.length} recent feedback patterns to improve model`);
    }
    
    // If we have embeddings, also do similarity search
    if (query && process.env.NEXT_PUBLIC_SUPABASE_URL) {
      try {
        // Generate embedding for current query
        const { data: queryEmbedding } = await supabase.rpc(
          'generate_embedding',
          { input_text: query }
        );
        
        if (queryEmbedding) {
          // Find similar past queries using pgvector
          const { data: similarQueries } = await supabase.rpc(
            'match_rl_feedback',
            {
              query_embedding: queryEmbedding,
              match_threshold: 0.7,
              match_count: 3
            }
          );
          
          if (similarQueries) {
            relevantFeedback = [...relevantFeedback, ...similarQueries];
            console.log(`Found ${similarQueries.length} similar past queries`);
          }
        }
      } catch (error) {
        console.log('Similarity search failed, using keyword match only');
      }
    }
    
    // Build context from feedback to improve the model
    let enhancedContext = '';
    const corrections = [];
    
    if (relevantFeedback.length > 0) {
      enhancedContext = '\n\n📚 IMPROVING BASED ON RECENT FEEDBACK:\n';
      enhancedContext += 'Users have indicated these improvements:\n';
      
      relevantFeedback.forEach(fb => {
        if (fb.feedback) {
          const score = fb.learning_patterns?.score ?? fb.confidence ?? 0;
          corrections.push({
            feedback: fb.feedback,
            score: score,
            context: fb.learning_patterns
          });
          
          // Add feedback based on score
          if (score < 0) {
            // Negative feedback - this is a CORRECTION to apply
            enhancedContext += `- CORRECTION: ${fb.feedback}\n`;
          } else if (score > 0.8) {
            // Positive feedback - this worked well
            enhancedContext += `- GOOD PATTERN: ${fb.feedback}\n`;
          }
        }
      });
      
      enhancedContext += '\nUse this feedback to provide better, more accurate analysis.\n';
    }
    
    return NextResponse.json({
      success: true,
      hasContext: relevantFeedback.length > 0,
      contextCount: relevantFeedback.length,
      enhancedContext,
      corrections,
      company
    });
    
  } catch (error) {
    console.error('RL retrieval error:', error);
    return NextResponse.json({
      success: true,
      hasContext: false,
      enhancedContext: '',
      corrections: []
    });
  }
}