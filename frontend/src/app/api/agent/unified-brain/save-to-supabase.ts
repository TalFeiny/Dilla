import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function saveToSupabase(
  sessionId: string,
  prompt: string,
  result: any,
  format: string,
  metadata?: any
) {
  try {
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
      return false;
    }
    
    // All outputs are saved to model_corrections for unified RL learning
    // The learning_patterns field contains the full result data
    console.log(`✅ Saved ${format} output to model_corrections for RL learning`);
    
    return true;
  } catch (error) {
    console.error('Error saving to Supabase:', error);
    return false;
  }
}