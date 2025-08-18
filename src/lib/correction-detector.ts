/**
 * Detect corrections in user messages and automatically save them for RL
 */

interface CorrectionPattern {
  pattern: RegExp;
  type: string;
  extractor: (match: RegExpMatchArray) => any;
}

const CORRECTION_PATTERNS: CorrectionPattern[] = [
  // Revenue corrections
  {
    pattern: /(?:revenue|arr|mrr)\s+(?:is|should be|actually)\s+\$?([\d.]+)\s*(M|B|million|billion)/i,
    type: 'revenue',
    extractor: (match) => ({
      correctValue: parseFloat(match[1]) * (match[2].toLowerCase().startsWith('b') ? 1000000000 : 1000000),
      field: 'revenue'
    })
  },
  // Valuation corrections
  {
    pattern: /(?:valuation|valued at|worth)\s+(?:is|should be|actually)\s+\$?([\d.]+)\s*(M|B|million|billion)/i,
    type: 'valuation',
    extractor: (match) => ({
      correctValue: parseFloat(match[1]) * (match[2].toLowerCase().startsWith('b') ? 1000000000 : 1000000),
      field: 'valuation'
    })
  },
  // Growth rate corrections
  {
    pattern: /growth\s+(?:rate)?\s+(?:is|should be|actually)\s+([\d.]+)%/i,
    type: 'growth_rate',
    extractor: (match) => ({
      correctValue: parseFloat(match[1]) / 100,
      field: 'growth_rate'
    })
  },
  // Multiple corrections
  {
    pattern: /(?:multiple|trading at|valued at)\s+([\d.]+)x\s+(?:revenue|arr)/i,
    type: 'valuation_multiple',
    extractor: (match) => ({
      correctValue: parseFloat(match[1]),
      field: 'revenue_multiple'
    })
  },
  // Funding corrections
  {
    pattern: /(?:raised|funding|funded)\s+\$?([\d.]+)\s*(M|B|million|billion)/i,
    type: 'funding',
    extractor: (match) => ({
      correctValue: parseFloat(match[1]) * (match[2].toLowerCase().startsWith('b') ? 1000000000 : 1000000),
      field: 'total_funding'
    })
  },
  // Employee count corrections
  {
    pattern: /(?:has|employs|employees)\s+([\d,]+)\s+(?:employees|people|staff)/i,
    type: 'employees',
    extractor: (match) => ({
      correctValue: parseInt(match[1].replace(/,/g, '')),
      field: 'employee_count'
    })
  },
  // Negation corrections
  {
    pattern: /(?:no|not|wrong|incorrect|actually not|definitely not)\s+(.+)/i,
    type: 'negation',
    extractor: (match) => ({
      negatedStatement: match[1],
      field: 'negation'
    })
  },
  // "Actually" corrections
  {
    pattern: /actually\s+(.+)/i,
    type: 'correction',
    extractor: (match) => ({
      correctedStatement: match[1],
      field: 'general'
    })
  }
];

export class CorrectionDetector {
  /**
   * Detect if a user message contains a correction
   */
  static detectCorrection(userMessage: string, previousAgentMessage?: string): {
    hasCorrection: boolean;
    corrections: Array<{
      type: string;
      data: any;
      confidence: number;
    }>;
  } {
    const corrections: Array<{
      type: string;
      data: any;
      confidence: number;
    }> = [];
    
    // Check each pattern
    for (const pattern of CORRECTION_PATTERNS) {
      const match = userMessage.match(pattern.pattern);
      if (match) {
        corrections.push({
          type: pattern.type,
          data: pattern.extractor(match),
          confidence: this.calculateConfidence(userMessage, pattern.type)
        });
      }
    }
    
    // Check for contradictory language
    const contradictionWords = [
      'wrong', 'incorrect', 'no ', 'not ', 'actually', 'should be',
      'supposed to be', 'really', 'in fact', 'correction'
    ];
    
    const hasContradiction = contradictionWords.some(word => 
      userMessage.toLowerCase().includes(word)
    );
    
    if (hasContradiction && corrections.length === 0) {
      // Generic correction detected
      corrections.push({
        type: 'general_correction',
        data: { message: userMessage },
        confidence: 0.5
      });
    }
    
    return {
      hasCorrection: corrections.length > 0,
      corrections
    };
  }
  
  /**
   * Calculate confidence based on message characteristics
   */
  private static calculateConfidence(message: string, type: string): number {
    let confidence = 0.7; // Base confidence
    
    // Higher confidence for specific numeric corrections
    if (type === 'revenue' || type === 'valuation' || type === 'growth_rate') {
      confidence = 0.9;
    }
    
    // Higher confidence if message is short and direct
    if (message.length < 100) {
      confidence += 0.1;
    }
    
    // Lower confidence for negations
    if (type === 'negation') {
      confidence = 0.6;
    }
    
    return Math.min(1.0, confidence);
  }
  
  /**
   * Format correction for storage
   */
  static formatCorrectionForStorage(
    correction: any,
    company?: string,
    sessionId?: string
  ): {
    correction_text: string;
    semantic_analysis: any;
    company?: string;
    session_id?: string;
  } {
    let correctionText = '';
    
    // Build human-readable correction text
    switch (correction.type) {
      case 'revenue':
        correctionText = `Revenue should be $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
        break;
      case 'valuation':
        correctionText = `Valuation should be $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
        break;
      case 'growth_rate':
        correctionText = `Growth rate should be ${(correction.data.correctValue * 100).toFixed(0)}%`;
        break;
      case 'valuation_multiple':
        correctionText = `Revenue multiple should be ${correction.data.correctValue}x`;
        break;
      case 'funding':
        correctionText = `Total funding should be $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
        break;
      case 'employees':
        correctionText = `Employee count should be ${correction.data.correctValue}`;
        break;
      default:
        correctionText = JSON.stringify(correction.data);
    }
    
    return {
      correction_text: correctionText,
      semantic_analysis: {
        type: correction.type,
        specifics: correction.data,
        confidence: correction.confidence,
        learning_rule: this.generateLearningRule(correction)
      },
      company,
      session_id: sessionId
    };
  }
  
  /**
   * Generate a learning rule from the correction
   */
  private static generateLearningRule(correction: any): string {
    switch (correction.type) {
      case 'revenue':
        return `Set revenue to $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
      case 'valuation':
        return `Set valuation to $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
      case 'growth_rate':
        return `Use ${(correction.data.correctValue * 100).toFixed(0)}% growth rate`;
      case 'valuation_multiple':
        return `Apply ${correction.data.correctValue}x revenue multiple`;
      case 'funding':
        return `Total funding is $${(correction.data.correctValue / 1000000).toFixed(1)}M`;
      case 'employees':
        return `Company has ${correction.data.correctValue} employees`;
      default:
        return 'Apply correction to future responses';
    }
  }
}

export default CorrectionDetector;