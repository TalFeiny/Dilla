/**
 * Enhanced Citation Manager with Signal/Noise Filtering
 * Ensures trustworthy data tracking throughout the entire pipeline
 * Date: August 31, 2025
 */

export interface Citation {
  id: string;
  source: string;
  sourceType: 'web' | 'database' | 'api' | 'calculation' | 'model' | 'scraper';
  content: string;
  url?: string;
  timestamp: string;
  confidence: number; // 0-1 score
  signalStrength: number; // 0-100 score for signal vs noise
  verificationStatus: 'verified' | 'unverified' | 'disputed';
  metadata: {
    company?: string;
    metric?: string;
    timeframe?: string;
    methodology?: string;
    dataQuality?: 'primary' | 'secondary' | 'tertiary';
    freshness?: 'real-time' | 'recent' | 'historical' | 'stale';
  };
  lineage: string[]; // Track citation through skill boundaries
}

export interface DataPoint {
  value: any;
  citations: Citation[];
  aggregatedConfidence: number;
  signalScore: number;
  noiseFiltered: boolean;
}

export class EnhancedCitationManager {
  private static instance: EnhancedCitationManager;
  private citations: Map<string, Citation> = new Map();
  private dataPoints: Map<string, DataPoint> = new Map();
  private skillBoundaries: Map<string, string[]> = new Map(); // Track citations across skills
  
  // Signal/Noise thresholds
  private readonly SIGNAL_THRESHOLD = 60; // Minimum signal strength to keep
  private readonly CONFIDENCE_THRESHOLD = 0.5; // Minimum confidence to trust
  private readonly FRESHNESS_WEIGHTS = {
    'real-time': 1.0,
    'recent': 0.8,
    'historical': 0.5,
    'stale': 0.2
  };
  
  // Source reliability scores
  private readonly SOURCE_RELIABILITY = {
    'SEC EDGAR': 0.95,
    'Company Website': 0.9,
    'Bloomberg': 0.85,
    'TechCrunch': 0.75,
    'Tavily Advanced Search': 0.7,
    'Web Scraper': 0.6,
    'Social Media': 0.4,
    'Unknown': 0.3
  };

  static getInstance(): EnhancedCitationManager {
    if (!EnhancedCitationManager.instance) {
      EnhancedCitationManager.instance = new EnhancedCitationManager();
    }
    return EnhancedCitationManager.instance;
  }

  /**
   * Add citation with signal/noise evaluation
   */
  addCitation(
    source: string,
    content: string,
    options: Partial<Citation> = {}
  ): Citation {
    const citation: Citation = {
      id: this.generateCitationId(),
      source,
      sourceType: options.sourceType || 'web',
      content,
      url: options.url,
      timestamp: options.timestamp || new Date().toISOString(),
      confidence: this.calculateConfidence(source, options),
      signalStrength: this.calculateSignalStrength(content, source, options),
      verificationStatus: options.verificationStatus || 'unverified',
      metadata: options.metadata || {},
      lineage: options.lineage || []
    };

    this.citations.set(citation.id, citation);
    
    // Log high-signal citations
    if (citation.signalStrength > 80) {
      console.log(`Array.from(ation) High-signal data: ${source} - ${content.substring(0, 100)}`);
    }
    
    return citation;
  }

  /**
   * Generate a unique citation ID
   */
  private generateCitationId(): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 9);
    return `cite-${timestamp}-${random}`;
  }

  /**
   * Calculate confidence based on source and metadata
   */
  private calculateConfidence(source: string, options: Partial<Citation>): number {
    let confidence = 0.5; // Base confidence
    
    // Source reliability
    const sourceKey = Object.keys(this.SOURCE_RELIABILITY).find(key => 
      source.toLowerCase().includes(key.toLowerCase())
    );
    if (sourceKey) {
      confidence = this.SOURCE_RELIABILITY[sourceKey as keyof typeof this.SOURCE_RELIABILITY];
    }
    
    // Adjust for freshness
    if (options.metadata?.freshness) {
      confidence *= this.FRESHNESS_WEIGHTS[options.metadata.freshness];
    }
    
    // Adjust for data quality
    if (options.metadata?.dataQuality === 'primary') {
      confidence *= 1.2;
    } else if (options.metadata?.dataQuality === 'tertiary') {
      confidence *= 0.7;
    }
    
    // Cap at 1.0
    return Math.min(confidence, 1.0);
  }

  /**
   * Calculate signal strength (how valuable/relevant the information is)
   */
  private calculateSignalStrength(
    content: string,
    source: string,
    options: Partial<Citation>
  ): number {
    let signalScore = 50; // Base score
    
    // Check for specific high-value metrics
    const highValueMetrics = [
      'valuation', 'revenue', 'growth rate', 'burn rate', 'runway',
      'CAC', 'LTV', 'market share', 'Series', 'funding round'
    ];
    
    const contentLower = content.toLowerCase();
    const matchedMetrics = highValueMetrics.filter(metric => 
      contentLower.includes(metric.toLowerCase())
    );
    
    signalScore += matchedMetrics.length * 10;
    
    // Check for specific numbers/data
    const hasNumbers = /\$[\d,]+[MBK]?|\d+%|\d+x/i.test(content);
    if (hasNumbers) signalScore += 20;
    
    // Check for recency
    const currentYear = new Date().getFullYear();
    const hasRecentDate = new RegExp(`${currentYear}|${currentYear - 1}`).test(content);
    if (hasRecentDate) signalScore += 15;
    
    // Penalize vague or promotional content
    const noiseIndicators = [
      'may', 'might', 'could', 'possibly', 'reportedly',
      'sources say', 'rumored', 'unconfirmed'
    ];
    const noiseCount = noiseIndicators.filter(indicator => 
      contentLower.includes(indicator)
    ).length;
    signalScore -= noiseCount * 10;
    
    // Boost for verified status
    if (options.verificationStatus === 'verified') {
      signalScore += 20;
    }
    
    // Cap between 0 and 100
    return Math.max(0, Math.min(100, signalScore));
  }

  /**
   * Track citation across skill boundary
   */
  trackAcrossSkillBoundary(
    citationId: string,
    fromSkill: string,
    toSkill: string
  ): void {
    const citation = this.citations.get(citationId);
    if (citation) {
      citation.lineage.push(`${fromSkill} → ${toSkill}`);
      
      // Track boundary crossing
      const key = `${fromSkill}->${toSkill}`;
      const existing = this.skillBoundaries.get(key) || [];
      existing.push(citationId);
      this.skillBoundaries.set(key, existing);
    }
  }

  /**
   * Filter citations by signal strength
   */
  filterHighSignalCitations(citations: Citation[]): Citation[] {
    return citations.filter(c => 
      c.signalStrength >= this.SIGNAL_THRESHOLD && 
      c.confidence >= this.CONFIDENCE_THRESHOLD
    );
  }

  /**
   * Aggregate data point with citations
   */
  aggregateDataPoint(
    key: string,
    value: any,
    citations: Citation[]
  ): DataPoint {
    // Filter out noise
    const highSignalCitations = this.filterHighSignalCitations(citations);
    
    // Calculate aggregated confidence
    const aggregatedConfidence = highSignalCitations.length > 0
      ? highSignalCitations.reduce((sum, c) => sum + c.confidence, 0) / highSignalCitations.length
      : 0;
    
    // Calculate overall signal score
    const signalScore = highSignalCitations.length > 0
      ? highSignalCitations.reduce((sum, c) => sum + c.signalStrength, 0) / highSignalCitations.length
      : 0;
    
    const dataPoint: DataPoint = {
      value,
      citations: highSignalCitations,
      aggregatedConfidence,
      signalScore,
      noiseFiltered: citations.length > highSignalCitations.length
    };
    
    this.dataPoints.set(key, dataPoint);
    
    // Log if we filtered noise
    if (dataPoint.noiseFiltered) {
      console.log(`Array.from(ation) Filtered ${citations.length - highSignalCitations.length} noisy citations for ${key}`);
    }
    
    return dataPoint;
  }

  /**
   * Get citation trace for debugging
   */
  getCitationTrace(citationId: string): string[] {
    const citation = this.citations.get(citationId);
    return citation ? citation.lineage : [];
  }

  /**
   * Verify citation across multiple sources
   */
  async verifyCitation(citationId: string, additionalSources: Citation[]): Promise<void> {
    const citation = this.citations.get(citationId);
    if (!citation) return;
    
    // Check if multiple sources confirm the same information
    const confirmations = additionalSources.filter(source => {
      // Simple similarity check (could be enhanced with NLP)
      return source.content.toLowerCase().includes(
        citation.content.toLowerCase().substring(0, 50)
      );
    });
    
    if (confirmations.length >= 2) {
      citation.verificationStatus = 'verified';
      citation.confidence = Math.min(1.0, citation.confidence * 1.2);
      citation.signalStrength = Math.min(100, citation.signalStrength + 10);
    } else if (confirmations.length === 0 && additionalSources.length > 2) {
      citation.verificationStatus = 'disputed';
      citation.confidence *= 0.7;
      citation.signalStrength = Math.max(0, citation.signalStrength - 20);
    }
  }

  /**
   * Export citations for API response
   */
  exportCitations(filters?: {
    minSignal?: number;
    minConfidence?: number;
    sourceTypes?: string[];
  }): Citation[] {
    let citations = Array.from(this.citations.values());
    
    if (filters) {
      if (filters.minSignal !== undefined) {
        citations = citations.filter(c => c.signalStrength >= filters.minSignal);
      }
      if (filters.minConfidence !== undefined) {
        citations = citations.filter(c => c.confidence >= filters.minConfidence);
      }
      if (filters.sourceTypes) {
        citations = citations.filter(c => filters.sourceTypes!.includes(c.sourceType));
      }
    }
    
    // Sort by signal strength and confidence
    return citations.sort((a, b) => {
      const scoreA = a.signalStrength * a.confidence;
      const scoreB = b.signalStrength * b.confidence;
      return scoreB - scoreA;
    });
  }

  /**
   * Get trust score for a data point
   */
  getTrustScore(key: string): number {
    const dataPoint = this.dataPoints.get(key);
    if (!dataPoint) return 0;
    
    // Trust score based on:
    // - Aggregated confidence (40%)
    // - Signal score (40%)
    // - Number of high-quality citations (20%)
    const citationBonus = Math.min(1, dataPoint.citations.length / 3) * 0.2;
    const trustScore = (
      dataPoint.aggregatedConfidence * 0.4 +
      (dataPoint.signalScore / 100) * 0.4 +
      citationBonus
    );
    
    return Math.round(trustScore * 100);
  }

  /**
   * Generate formatted citation text
   */
  formatCitation(citation: Citation): string {
    const date = new Date(citation.timestamp).toLocaleDateString();
    const confidence = Math.round(citation.confidence * 100);
    const signal = Math.round(citation.signalStrength);
    
    let formatted = `${citation.source} (${date})`;
    
    if (citation.url) {
      formatted = `[${citation.source}](${citation.url}) (${date})`;
    }
    
    formatted += ` | Trust: ${confidence}% | Signal: ${signal}`;
    
    if (citation.verificationStatus === 'verified') {
      formatted += ' ✓';
    } else if (citation.verificationStatus === 'disputed') {
      formatted += ' ⚠️';
    }
    
    return formatted;
  }

  /**
   * Clear low-signal citations to reduce noise
   */
  pruneNoisyCitations(): number {
    const beforeCount = this.citations.size;
    
    for (const [id, citation] of this.citations.entries()) {
      if (citation.signalStrength < 30 || citation.confidence < 0.3) {
        this.citations.delete(id);
      }
    }
    
    const pruned = beforeCount - this.citations.size;
    if (pruned > 0) {
      console.log(`Array.from(ation) Pruned ${pruned} noisy citations`);
    }
    
    return pruned;
  }
}

// Export singleton instance
export const enhancedCitationManager = EnhancedCitationManager.getInstance();

// Export alias for backward compatibility
export { EnhancedCitationManager as CitationManager };