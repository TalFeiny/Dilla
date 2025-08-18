import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * Intelligent correction detection using Claude
 * No regex, just understanding
 */
export class IntelligentCorrectionDetector {
  /**
   * Use Claude to detect if user is correcting the agent
   */
  static async detectCorrection(
    userMessage: string, 
    previousAgentMessage?: string
  ): Promise<{
    hasCorrection: boolean;
    corrections: Array<{
      field: string;
      oldValue: any;
      newValue: any;
      confidence: number;
      explanation: string;
    }>;
  }> {
    if (!previousAgentMessage) {
      return { hasCorrection: false, corrections: [] };
    }

    const prompt = `You are analyzing whether a user is correcting information from a previous message.

Previous agent message:
${previousAgentMessage}

User's new message:
${userMessage}

Determine if the user is correcting any information. Look for:
- Direct corrections ("actually", "no", "wrong")
- Providing different numbers or facts
- Contradicting previous statements
- Clarifying information

If corrections are found, extract:
1. What field/topic is being corrected
2. What the old incorrect value was
3. What the correct value should be
4. Confidence level (0-1)
5. Brief explanation

Return JSON:
{
  "hasCorrection": boolean,
  "corrections": [
    {
      "field": "revenue|valuation|employees|growth_rate|funding|other",
      "oldValue": "what was said before",
      "newValue": "corrected value",
      "confidence": 0.9,
      "explanation": "why this is a correction"
    }
  ]
}

Only return the JSON, no other text.`;

    try {
      const response = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307', // Fast model for detection
        max_tokens: 500,
        temperature: 0,
        messages: [{ role: 'user', content: prompt }]
      });

      const text = response.content[0].type === 'text' ? response.content[0].text : '';
      
      // Parse JSON response
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const result = JSON.parse(jsonMatch[0]);
        return result;
      }
    } catch (error) {
      console.error('Error detecting correction:', error);
    }

    return { hasCorrection: false, corrections: [] };
  }

  /**
   * Generate learning rules from corrections
   */
  static generateLearningRules(corrections: Array<any>): Array<{
    rule: string;
    pattern: string;
    application: string;
  }> {
    return corrections.map(correction => ({
      rule: `When discussing ${correction.field}, use ${correction.newValue} instead of ${correction.oldValue}`,
      pattern: correction.field,
      application: `automatic_correction`
    }));
  }

  /**
   * Apply learned corrections to new responses
   */
  static async applyLearnedCorrections(
    response: string,
    sessionId: string,
    supabase: any
  ): Promise<string> {
    // Fetch recent corrections for this session
    const { data: corrections } = await supabase
      .from('model_corrections')
      .select('*')
      .eq('session_id', sessionId)
      .order('created_at', { ascending: false })
      .limit(10);

    if (!corrections || corrections.length === 0) {
      return response;
    }

    // Use Claude to intelligently apply corrections
    const prompt = `Apply these corrections to the response:

Corrections to apply:
${corrections.map((c: any) => c.correction_text).join('\n')}

Original response:
${response}

Return the corrected response with the corrections applied. Only return the corrected text, nothing else.`;

    try {
      const correctedResponse = await anthropic.messages.create({
        model: 'claude-3-haiku-20240307',
        max_tokens: 2000,
        temperature: 0,
        messages: [{ role: 'user', content: prompt }]
      });

      const text = correctedResponse.content[0].type === 'text' 
        ? correctedResponse.content[0].text 
        : response;
      
      return text;
    } catch (error) {
      console.error('Error applying corrections:', error);
      return response;
    }
  }
}