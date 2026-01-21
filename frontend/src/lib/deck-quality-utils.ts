/**
 * Deck Quality Utilities
 * Professional text processing, markdown removal, and data quality helpers
 */

/**
 * Strip all markdown syntax, JSON dumps, and AI-generated artifacts from text
 * for professional presentation
 */
export function stripMarkdown(text: string): string {
  if (!text || typeof text !== 'string') {
    return '';
  }

  let cleaned = text;

  // Remove JSON dumps and Python dict representations first
  // Pattern: {'key': 'value'} or {"key": "value"} or {key: value}
  cleaned = cleaned.replace(/\{[^{}]*['"]\w+['"]\s*:\s*[^{}]*\}/g, '');
  cleaned = cleaned.replace(/\{[^{}]*\w+\s*:\s*[^{}]*\}/g, '');
  
  // Remove JSON.stringify patterns
  cleaned = cleaned.replace(/JSON\.stringify\([^)]+\)/gi, '');
  
  // Remove code blocks (including filler code)
  cleaned = cleaned.replace(/```[\s\S]*?```/g, '');
  cleaned = cleaned.replace(/`[^`]+`/g, '');
  
  // Remove HTML tags
  cleaned = cleaned.replace(/<[^>]+>/g, '');
  
  // Remove common AI filler phrases
  const aiPhrases = [
    /Here is|Here's|Here are/gi,
    /Based on|According to|As per/gi,
    /Note that|Please note|It should be noted/gi,
    /In summary|To summarize|In conclusion/gi,
    /This shows|This indicates|This suggests/gi,
    /It is important to|It should be|It must be/gi,
    /Let me|Allow me|I will|I can/gi,
  ];
  aiPhrases.forEach(phrase => {
    cleaned = cleaned.replace(phrase, '');
  });
  
  // Remove markdown syntax
  cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');  // **bold**
  cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');      // *italic*
  cleaned = cleaned.replace(/__([^_]+)__/g, '$1');       // __bold__
  cleaned = cleaned.replace(/_([^_]+)_/g, '$1');         // _italic_
  cleaned = cleaned.replace(/#{1,6}\s/g, '');            // Headers
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1'); // Links, keep text
  
  // Remove list markers
  cleaned = cleaned.replace(/^\s*[-*+]\s+/gm, '');
  cleaned = cleaned.replace(/^\s*\d+\.\s+/gm, '');
  
  // Remove excessive whitespace
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');  // Max 2 newlines
  cleaned = cleaned.replace(/ {3,}/g, ' ');       // Max 2 spaces
  
  // Remove common AI filler words at start
  cleaned = cleaned.replace(/^(The|A|An)\s+/i, '');
  
  // Remove any remaining JSON-like structures
  cleaned = cleaned.replace(/^\s*[\{\[]/g, '');  // Remove leading { or [
  cleaned = cleaned.replace(/[\}\]]\s*$/g, '');  // Remove trailing } or ]
  
  // Remove filler code patterns
  cleaned = cleaned.replace(/filler|placeholder|dummy|test|example\.com/gi, '');
  
  return cleaned.trim();
}

/**
 * Format estimated values with professional indicators
 */
export function formatEstimatedValue(
  value: number | string,
  label: string,
  confidence?: 'high' | 'medium' | 'low',
  methodology?: string
): string {
  const formattedValue = typeof value === 'number' 
    ? formatCurrency(value)
    : value;
  
  const confidenceText = confidence 
    ? ` (${confidence} confidence)`
    : '';
  
  const methodologyText = methodology
    ? `, ${methodology}`
    : '';
  
  return `~${formattedValue} ${label} (estimated${confidenceText}${methodologyText})`;
}

/**
 * Format currency values (simple helper)
 */
function formatCurrency(value: number): string {
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  } else if (value >= 1_000) {
    return `$${(value / 1_000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

/**
 * Replace unprofessional empty state text
 */
export function formatEmptyState(
  value: any,
  type: 'financial' | 'operational' | 'general' = 'general'
): string | null {
  if (value !== null && value !== undefined && value !== '') {
    return null; // Not empty, return null to indicate should render
  }

  switch (type) {
    case 'financial':
      return 'Not disclosed';
    case 'operational':
      return 'Data unavailable';
    default:
      return 'Data unavailable';
  }
}

/**
 * Check if a value should be hidden (empty/null/zero with no context)
 */
export function shouldHideEmptyMetric(
  value: any,
  showIfZero: boolean = false
): boolean {
  if (value === null || value === undefined || value === '') {
    return true;
  }
  
  if (typeof value === 'number' && value === 0 && !showIfZero) {
    return true;
  }
  
  if (typeof value === 'string' && (
    value.toLowerCase() === 'n/a' ||
    value.toLowerCase() === 'na' ||
    value.toLowerCase() === 'unknown' ||
    value.toLowerCase() === 'none'
  )) {
    return true;
  }
  
  return false;
}

/**
 * Extract confidence level from data point metadata
 */
export function extractConfidence(
  dataPoint: any
): 'high' | 'medium' | 'low' | undefined {
  if (!dataPoint || typeof dataPoint !== 'object') {
    return undefined;
  }

  // Check various possible locations for confidence
  const confidence = 
    dataPoint.confidence ||
    dataPoint.metadata?.confidence ||
    dataPoint.source?.confidence ||
    dataPoint._confidence;

  if (typeof confidence === 'string') {
    const lower = confidence.toLowerCase();
    if (lower === 'high' || lower === 'medium' || lower === 'low') {
      return lower as 'high' | 'medium' | 'low';
    }
  }

  if (typeof confidence === 'number') {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
  }

  return undefined;
}

/**
 * Extract source information from data point
 */
export function extractSource(dataPoint: any): {
  primary?: string;
  type?: 'primary' | 'secondary' | 'inferred';
  url?: string;
  date?: string;
} | null {
  if (!dataPoint || typeof dataPoint !== 'object') {
    return null;
  }

  const source = 
    dataPoint.source ||
    dataPoint.metadata?.source ||
    dataPoint.citation?.source;

  if (!source) {
    return null;
  }

  if (typeof source === 'string') {
    return { primary: source };
  }

  if (typeof source === 'object') {
    return {
      primary: source.primary || source.name || source.source,
      type: source.type,
      url: source.url,
      date: source.date || source.verifiedDate
    };
  }

  return null;
}

/**
 * Check if value is estimated/inferred
 */
export function isEstimated(dataPoint: any): boolean {
  if (!dataPoint || typeof dataPoint !== 'object') {
    return false;
  }

  return !!(
    dataPoint.isEstimated ||
    dataPoint.metadata?.isEstimated ||
    dataPoint._isEstimated ||
    dataPoint.inferred ||
    dataPoint.metadata?.inferred ||
    dataPoint.source?.type === 'inferred' ||
    dataPoint.estimationMethod
  );
}

