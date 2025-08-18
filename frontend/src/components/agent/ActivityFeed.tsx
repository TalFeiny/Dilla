'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import {
  Activity,
  Search,
  Calculator,
  TrendingUp,
  Brain,
  Zap,
  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Eye,
  Target,
  BarChart3,
  FileSearch
} from 'lucide-react';
import { createClient } from '@supabase/supabase-js';

interface AgentActivity {
  id: number;
  activity_type: string;
  tool_name: string | null;
  description: string;
  input_data: any;
  output_data: any;
  confidence_score: number | null;
  timestamp: string;
  session_id: string;
}

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export default function ActivityFeed() {
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchActivities = async () => {
    try {
      const { data, error } = await supabase
        .from('agent_activities')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(50);

      if (error) throw error;
      if (data) setActivities(data);
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();

    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(fetchActivities, 3000); // Refresh every 3 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const getActivityIcon = (type: string, toolName?: string | null) => {
    switch (type) {
      case 'search':
        return <Search className="h-4 w-4" />;
      case 'calculation':
        return <Calculator className="h-4 w-4" />;
      case 'analysis':
        return <Brain className="h-4 w-4" />;
      case 'tool_call':
        if (toolName?.includes('pwerm')) return <BarChart3 className="h-4 w-4" />;
        if (toolName?.includes('search')) return <Search className="h-4 w-4" />;
        return <Zap className="h-4 w-4" />;
      case 'decision':
        return <Target className="h-4 w-4" />;
      default:
        return <Activity className="h-4 w-4" />;
    }
  };

  const getActivityColor = (type: string, confidence?: number | null) => {
    if (confidence !== null && confidence !== undefined) {
      if (confidence >= 0.8) return 'text-green-600 bg-green-50 border-green-200';
      if (confidence >= 0.6) return 'text-blue-600 bg-blue-50 border-blue-200';
      if (confidence >= 0.4) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      return 'text-red-600 bg-red-50 border-red-200';
    }

    switch (type) {
      case 'search':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'calculation':
        return 'text-purple-600 bg-purple-50 border-purple-200';
      case 'analysis':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'tool_call':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      case 'decision':
        return 'text-orange-600 bg-orange-50 border-orange-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    
    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffMins < 60) return `${diffMins}m ago`;
    return date.toLocaleTimeString();
  };

  const renderOutputSummary = (output: any, type: string) => {
    if (!output) return null;

    try {
      const parsed = typeof output === 'string' ? JSON.parse(output) : output;
      
      if (type === 'analysis' && parsed.recommendation) {
        return (
          <div className="mt-2 text-xs text-gray-600">
            <Badge variant="outline" className="text-xs">
              {parsed.recommendation}
            </Badge>
          </div>
        );
      }
      
      if (parsed.company || parsed.expectedIRR || parsed.alphaOpportunity) {
        return (
          <div className="mt-2 text-xs text-gray-600">
            {parsed.expectedIRR && <span className="font-medium">{parsed.expectedIRR} IRR</span>}
            {parsed.alphaOpportunity && parsed.alphaOpportunity.startsWith('YES') && (
              <Badge variant="outline" className="ml-2 text-xs text-green-600">Alpha</Badge>
            )}
          </div>
        );
      }

      if (typeof output === 'string' && output.length > 100) {
        return (
          <div className="mt-2 text-xs text-gray-600 font-mono bg-gray-100 p-2 rounded">
            {output.substring(0, 100)}...
          </div>
        );
      }

      return null;
    } catch {
      return null;
    }
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Live Agent Activity
            </CardTitle>
            <CardDescription>
              Real-time feed of all agent operations and analysis
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={autoRefresh ? 'text-green-600' : ''}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
              {autoRefresh ? 'Live' : 'Paused'}
            </Button>
            <Button variant="outline" size="sm" onClick={fetchActivities}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-500">Loading activities...</span>
          </div>
        ) : (
          <ScrollArea className="h-96">
            <div className="space-y-3">
              {activities.map((activity) => (
                <div
                  key={activity.id}
                  className={`p-3 rounded-lg border ${getActivityColor(activity.activity_type, activity.confidence_score)}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-2">
                      {getActivityIcon(activity.activity_type, activity.tool_name)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-medium truncate">
                            {activity.description}
                          </p>
                          {activity.confidence_score && (
                            <Badge variant="outline" className="text-xs">
                              {Math.round(activity.confidence_score * 100)}% confidence
                            </Badge>
                          )}
                        </div>
                        
                        {activity.tool_name && (
                          <p className="text-xs text-gray-500 mb-1">
                            Tool: {activity.tool_name}
                          </p>
                        )}
                        
                        {renderOutputSummary(activity.output_data, activity.activity_type)}
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className="text-xs text-gray-500">
                        {formatTimestamp(activity.timestamp)}
                      </div>
                      <Badge variant="secondary" className="text-xs mt-1">
                        {activity.activity_type}
                      </Badge>
                    </div>
                  </div>
                  
                  {/* Show input preview for debugging */}
                  {process.env.NODE_ENV === 'development' && activity.input_data && (
                    <details className="mt-2">
                      <summary className="text-xs text-gray-400 cursor-pointer">
                        Debug: View Input/Output
                      </summary>
                      <div className="text-xs text-gray-600 font-mono bg-gray-100 p-2 rounded mt-1">
                        <div><strong>Input:</strong> {JSON.stringify(activity.input_data, null, 2).substring(0, 200)}...</div>
                        {activity.output_data && (
                          <div className="mt-1"><strong>Output:</strong> {typeof activity.output_data === 'string' ? activity.output_data.substring(0, 200) : JSON.stringify(activity.output_data, null, 2).substring(0, 200)}...</div>
                        )}
                      </div>
                    </details>
                  )}
                </div>
              ))}
              
              {activities.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <Activity className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p>No agent activities yet</p>
                  <p className="text-sm">Start a conversation to see live updates</p>
                </div>
              )}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}