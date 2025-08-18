import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { rlCoordinator } from '@/lib/rl-coordinator';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Simple pattern extraction from correction text
function extractPattern(correction: string) {
  const lower = correction.toLowerCase();
  
  // Extract numerical values and what they refer to
  const patterns = {
    metric: '',
    value: '',
    rule: '',
    category: ''
  };
  
  // Identify the metric being corrected
  if (lower.includes('revenue')) patterns.metric = 'revenue';
  else if (lower.includes('wacc') || lower.includes('discount')) patterns.metric = 'wacc';
  else if (lower.includes('growth')) patterns.metric = 'growth_rate';
  else if (lower.includes('margin') || lower.includes('ebitda')) patterns.metric = 'margin';
  else if (lower.includes('tax')) patterns.metric = 'tax_rate';
  else if (lower.includes('multiple')) patterns.metric = 'valuation_multiple';
  
  // Extract numerical values
  const valueMatch = correction.match(/(\d+(?:\.\d+)?)\s*(%|M|B|x)?/);
  if (valueMatch) {
    patterns.value = valueMatch[1] + (valueMatch[2] || '');
  }
  
  // Categorize the type of correction
  if (lower.includes('should be') || lower.includes('use')) {
    patterns.category = 'specific_value';
    patterns.rule = correction;
  } else if (lower.includes('too high') || lower.includes('too aggressive')) {
    patterns.category = 'reduce_value';
    patterns.rule = `Reduce ${patterns.metric} - ${correction}`;
  } else if (lower.includes('too low') || lower.includes('conservative')) {
    patterns.category = 'increase_value';
    patterns.rule = `Increase ${patterns.metric} - ${correction}`;
  } else if (lower.includes('missing') || lower.includes('forgot') || lower.includes('add')) {
    patterns.category = 'missing_element';
    patterns.rule = `Add ${patterns.metric || 'element'} - ${correction}`;
  } else if (lower.includes('wrong')) {
    patterns.category = 'incorrect_value';
    patterns.rule = correction;
  }
  
  return patterns;
}

export async function POST(request: NextRequest) {
  try {
    const { 
      sessionId, 
      company, 
      modelType, 
      correction, 
      feedbackType,
      confidence,
      timestamp,
      commands 
    } = await request.json();
    
    console.log('Storing correction:', { company, modelType, correction, feedbackType });
    
    if (!correction) {
      return NextResponse.json({ 
        success: false, 
        error: 'No correction provided' 
      }, { status: 400 });
    }
    
    // Extract patterns from the correction
    const patterns = extractPattern(correction);
    
    // Update RL system with feedback
    await rlCoordinator.updateReward(
      sessionId || `session-${Date.now()}`,
      correction,
      confidence || 0.5,
      {
        company,
        modelType,
        patterns,
        feedbackType,
        originalCorrection: correction
      }
    );
    
    console.log(`🎯 RL system updated with feedback for ${company || 'general'} - ${modelType}`);
    
    // Store the correction
    const { data, error } = await supabase
      .from('model_corrections')
      .insert({
        company_name: company || 'general',
        model_type: modelType || 'General',
        correction_type: feedbackType,
        feedback: correction,
        learning_patterns: patterns,
        confidence: confidence || 0.8,
        metadata: {
          session_id: sessionId,
          commands_count: commands?.length || 0,
          timestamp: timestamp || new Date().toISOString()
        }
      })
      .select()
      .single();
    
    console.log('Insert result:', { data, error });
    
    if (error) {
      console.error('Failed to store correction:', error);
      return NextResponse.json({ 
        success: false, 
        error: error.message,
        details: error 
      }, { status: 500 });
    }
    
    // Get recent corrections for this model type to build learning context
    const { data: recentCorrections } = await supabase
      .from('model_corrections')
      .select('feedback, learning_patterns, correction_type, confidence')
      .eq('model_type', modelType || 'General')
      .order('created_at', { ascending: false })
      .limit(20);
    
    // Aggregate common patterns
    const commonPatterns = {};
    if (recentCorrections) {
      recentCorrections.forEach(c => {
        if (c.patterns?.metric) {
          if (!commonPatterns[c.patterns.metric]) {
            commonPatterns[c.patterns.metric] = [];
          }
          commonPatterns[c.patterns.metric].push(c.patterns.rule || c.correction_text);
        }
      });
    }
    
    return NextResponse.json({
      success: true,
      patterns: patterns,
      commonPatterns: commonPatterns,
      stored: !!data,
      rlUpdated: true,
      message: 'Feedback stored and RL system updated'
    });
    
  } catch (error) {
    console.error('Correction storage error:', error);
    // Don't fail the request - feedback is still useful even if storage fails
    return NextResponse.json({
      success: true,
      stored: false,
      message: 'Feedback received but not stored'
    });
  }
}

// GET endpoint to retrieve learned patterns for a model type
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const modelType = searchParams.get('modelType') || 'General';
    const company = searchParams.get('company');
    
    // Get recent corrections
    let query = supabase
      .from('model_corrections')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(50);
    
    if (modelType !== 'all') {
      query = query.eq('model_type', modelType);
    }
    
    if (company) {
      query = query.eq('company_name', company);
    }
    
    const { data: corrections, error } = await query;
    
    if (error) throw error;
    
    // Aggregate patterns
    const patterns = {
      common_mistakes: {},
      recommended_values: {},
      rules: []
    };
    
    corrections?.forEach(c => {
      // Count common feedback types
      if (c.correction_type) {
        patterns.common_mistakes[c.correction_type] = 
          (patterns.common_mistakes[c.correction_type] || 0) + 1;
      }
      
      // Extract recommended values
      if (c.learning_patterns?.metric && c.learning_patterns?.value) {
        if (!patterns.recommended_values[c.learning_patterns.metric]) {
          patterns.recommended_values[c.learning_patterns.metric] = [];
        }
        patterns.recommended_values[c.learning_patterns.metric].push(c.learning_patterns.value);
      }
      
      // Collect rules
      if (c.learning_patterns?.rule) {
        patterns.rules.push(c.learning_patterns.rule);
      }
    });
    
    // Build learning context string for prompt enhancement
    let learningContext = '\n\nLEARNED PATTERNS FROM USER FEEDBACK:\n';
    
    // Add common mistakes to avoid
    const topMistakes = Object.entries(patterns.common_mistakes)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    
    if (topMistakes.length > 0) {
      learningContext += '\nCommon issues to avoid:\n';
      topMistakes.forEach(([mistake, count]) => {
        learningContext += `- ${mistake} (reported ${count} times)\n`;
      });
    }
    
    // Add recommended values
    if (Object.keys(patterns.recommended_values).length > 0) {
      learningContext += '\nRecommended values based on feedback:\n';
      Object.entries(patterns.recommended_values).forEach(([metric, values]) => {
        const uniqueValues = [...new Set(values)].slice(0, 3);
        learningContext += `- ${metric}: ${uniqueValues.join(', ')}\n`;
      });
    }
    
    // Add specific rules
    const uniqueRules = [...new Set(patterns.rules)].slice(0, 10);
    if (uniqueRules.length > 0) {
      learningContext += '\nSpecific corrections to apply:\n';
      uniqueRules.forEach(rule => {
        learningContext += `- ${rule}\n`;
      });
    }
    
    return NextResponse.json({
      success: true,
      corrections: corrections,
      patterns: patterns,
      learningContext: learningContext
    });
    
  } catch (error) {
    console.error('Failed to retrieve corrections:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve learning patterns' },
      { status: 500 }
    );
  }
}