import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Route performance tracking
interface RoutePerformance {
  intent: string;
  endpoint: string;
  success_rate: number;
  avg_confidence: number;
  avg_response_time: number;
  total_calls: number;
  positive_feedback: number;
  negative_feedback: number;
  corrections: number;
}

// Weight adjustment based on feedback
class RouteOptimizer {
  private readonly LEARNING_RATE = 0.1;
  private readonly MIN_WEIGHT = 0.1;
  private readonly MAX_WEIGHT = 1.0;

  async updateRoutePerformance(feedback: any) {
    const { routeId, type, metadata } = feedback;
    
    if (!metadata?.intent || !metadata?.endpoint) {
      return; // Can't update without routing info
    }

    // Get current performance
    const { data: current } = await supabase
      .from('route_performance')
      .select('*')
      .eq('intent', metadata.intent)
      .eq('endpoint', metadata.endpoint)
      .single();

    if (!current) {
      // Create new performance record
      await this.createPerformanceRecord(metadata, feedback);
      return;
    }

    // Update performance metrics
    const updates = this.calculateUpdates(current, feedback);
    
    await supabase
      .from('route_performance')
      .update(updates)
      .eq('id', current.id);

    // If this was a correction, store the pattern
    if (type === 'correction' && feedback.details) {
      await this.storeCorrection(feedback);
    }
  }

  private calculateUpdates(current: RoutePerformance, feedback: any): Partial<RoutePerformance> {
    const updates: Partial<RoutePerformance> = {
      total_calls: current.total_calls + 1
    };

    // Update feedback counts
    if (feedback.type === 'positive') {
      updates.positive_feedback = current.positive_feedback + 1;
    } else if (feedback.type === 'negative') {
      updates.negative_feedback = current.negative_feedback + 1;
    } else if (feedback.type === 'correction') {
      updates.corrections = current.corrections + 1;
      updates.negative_feedback = current.negative_feedback + 1; // Corrections count as negative
    }

    // Recalculate success rate
    const totalFeedback = (updates.positive_feedback || current.positive_feedback) + 
                         (updates.negative_feedback || current.negative_feedback);
    
    if (totalFeedback > 0) {
      updates.success_rate = (updates.positive_feedback || current.positive_feedback) / totalFeedback;
    }

    // Update confidence based on feedback
    if (feedback.metadata?.confidence) {
      updates.avg_confidence = (1 - this.LEARNING_RATE) * current.avg_confidence + 
                               this.LEARNING_RATE * feedback.metadata.confidence;
    }

    return updates;
  }

  private async createPerformanceRecord(metadata: any, feedback: any) {
    const record: RoutePerformance = {
      intent: metadata.intent,
      endpoint: metadata.endpoint,
      success_rate: feedback.type === 'positive' ? 1 : 0,
      avg_confidence: metadata.confidence || 0.5,
      avg_response_time: 0,
      total_calls: 1,
      positive_feedback: feedback.type === 'positive' ? 1 : 0,
      negative_feedback: feedback.type === 'negative' || feedback.type === 'correction' ? 1 : 0,
      corrections: feedback.type === 'correction' ? 1 : 0
    };

    await supabase
      .from('route_performance')
      .insert(record);
  }

  private async storeCorrection(feedback: any) {
    // Parse correction details
    const correction = this.parseCorrection(feedback.details);
    
    if (correction) {
      await supabase
        .from('agent_corrections')
        .insert({
          message_id: feedback.messageId,
          route_id: feedback.routeId,
          field: correction.field,
          incorrect_value: correction.incorrect,
          correct_value: correction.correct,
          source: feedback.metadata?.sources?.[0] || 'unknown',
          created_at: new Date()
        });

      // Create learning pattern
      await this.createLearningPattern(correction, feedback.metadata);
    }
  }

  private parseCorrection(details: string): any {
    // Parse common correction patterns
    const patterns = [
      /(\w+)\s+should\s+be\s+([\d.]+[MBK]?)\s+not\s+([\d.]+[MBK]?)/i,
      /(\w+)\s+is\s+actually\s+([\d.]+[MBK]?)/i,
      /wrong\s+(\w+):\s+([\d.]+[MBK]?)/i,
    ];

    for (const pattern of patterns) {
      const match = details.match(pattern);
      if (match) {
        return {
          field: match[1].toLowerCase(),
          correct: this.parseValue(match[2]),
          incorrect: match[3] ? this.parseValue(match[3]) : null
        };
      }
    }

    // Generic correction
    return {
      field: 'general',
      correct: details,
      incorrect: null
    };
  }

  private parseValue(str: string): number {
    const value = parseFloat(str.replace(/[^0-9.]/g, ''));
    if (str.includes('M')) return value * 1e6;
    if (str.includes('B')) return value * 1e9;
    if (str.includes('K')) return value * 1e3;
    return value;
  }

  private async createLearningPattern(correction: any, metadata: any) {
    // Create a pattern that can be used for future queries
    const pattern = {
      intent: metadata?.intent,
      field: correction.field,
      pattern_type: 'value_correction',
      pattern: {
        source: metadata?.sources?.[0],
        tends_to: correction.incorrect > correction.correct ? 'overestimate' : 'underestimate',
        factor: correction.correct / correction.incorrect
      },
      confidence: 0.5,
      created_at: new Date()
    };

    await supabase
      .from('learning_patterns')
      .insert(pattern);
  }
}

// Get best route for an intent based on performance
export async function getBestRoute(intent: string): Promise<string | null> {
  const { data: routes } = await supabase
    .from('route_performance')
    .select('*')
    .eq('intent', intent)
    .order('success_rate', { ascending: false })
    .limit(3);

  if (!routes || routes.length === 0) {
    return null;
  }

  // Weighted selection with exploration
  const EXPLORATION_RATE = 0.1;
  
  if (Math.random() < EXPLORATION_RATE && routes.length > 1) {
    // Explore: try second or third best route
    return routes[Math.floor(Math.random() * (routes.length - 1)) + 1].endpoint;
  } else {
    // Exploit: use best performing route
    return routes[0].endpoint;
  }
}

// Main feedback handler
export async function POST(request: NextRequest) {
  try {
    const feedback = await request.json();
    
    // Store raw feedback
    await supabase
      .from('agent_feedback')
      .insert({
        message_id: feedback.messageId,
        route_id: feedback.routeId,
        type: feedback.type,
        score: feedback.score,
        details: feedback.details,
        metadata: feedback.metadata,
        created_at: new Date()
      });

    // Update route performance
    const optimizer = new RouteOptimizer();
    await optimizer.updateRoutePerformance(feedback);

    // If negative feedback, log for review
    if (feedback.type === 'negative' || feedback.type === 'correction') {
      console.log('Negative feedback received:', {
        intent: feedback.metadata?.intent,
        endpoint: feedback.metadata?.endpoint,
        details: feedback.details
      });
    }

    return NextResponse.json({
      success: true,
      message: 'Feedback recorded'
    });

  } catch (error) {
    console.error('Feedback processing error:', error);
    return NextResponse.json(
      { error: 'Failed to process feedback' },
      { status: 500 }
    );
  }
}

// GET endpoint to view performance metrics
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const intent = searchParams.get('intent');

  if (intent) {
    const { data } = await supabase
      .from('route_performance')
      .select('*')
      .eq('intent', intent)
      .order('success_rate', { ascending: false });

    return NextResponse.json({ intent, routes: data });
  }

  // Get overall performance
  const { data } = await supabase
    .from('route_performance')
    .select('*')
    .order('total_calls', { ascending: false })
    .limit(20);

  // Calculate insights
  const insights = {
    best_performing: data?.filter(r => r.success_rate > 0.8),
    needs_improvement: data?.filter(r => r.success_rate < 0.5),
    most_corrected: data?.sort((a, b) => b.corrections - a.corrections).slice(0, 5)
  };

  return NextResponse.json({
    routes: data,
    insights
  });
}