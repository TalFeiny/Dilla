import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export interface SaveResult {
  success: boolean;
  error?: string;
  details?: any;
}

export async function saveToSupabase(
  sessionId: string,
  prompt: string,
  result: any,
  format: string,
  metadata?: any
): Promise<SaveResult> {
  try {
    // Validate inputs
    if (!sessionId) {
      return {
        success: false,
        error: 'Session ID is required',
        details: { sessionId, format }
      };
    }

    if (!result) {
      return {
        success: false,
        error: 'Result data is required',
        details: { sessionId, format }
      };
    }

    // Save to model_corrections table (existing RL table)
    const { data, error } = await supabase
      .from('model_corrections')
      .insert([{
        company_name: metadata?.company || format,
        model_type: 'qwen3:latest',
        correction_type: 'generation',
        feedback: `Generated ${format} output`,
        learning_patterns: {
          prompt,
          result: result,
          format,
          sessionId
        },
        confidence: 0.8, // Default confidence for generated content
        metadata: {
          ...metadata,
          session_id: sessionId,
          timestamp: new Date().toISOString()
        }
      }]);
    
    if (error) {
      console.error('Supabase save error:', error);
      return {
        success: false,
        error: error.message || 'Failed to save to Supabase',
        details: {
          code: error.code,
          hint: error.hint,
          details: error.details
        }
      };
    }
    
    // All outputs are saved to model_corrections for unified RL learning
    // The learning_patterns field contains the full result data
    console.log(`✅ Saved ${format} output to model_corrections for RL learning`);
    
    return {
      success: true,
      details: { data }
    };
  } catch (error) {
    console.error('Error saving to Supabase:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
      details: { originalError: error }
    };
  }
}