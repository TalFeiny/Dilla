'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { 
  ThumbsUp, 
  ThumbsDown, 
  Edit3, 
  AlertCircle, 
  MessageSquare,
  CheckCircle,
  X
} from 'lucide-react';

interface AgentFeedbackProps {
  sessionId: string;
  messageId: string;
  company?: string;
  responseType: string;
  onFeedback?: (feedback: FeedbackData) => void;
}

interface FeedbackData {
  sessionId: string;
  messageId: string;
  company?: string;
  responseType: string;
  feedbackType: 'approve' | 'wrong' | 'needs_edit' | 'fix_required' | 'specific';
  score: number;
  specificFeedback?: string;
  timestamp: string;
}

export default function AgentFeedback({ 
  sessionId, 
  messageId, 
  company, 
  responseType,
  onFeedback 
}: AgentFeedbackProps) {
  const [showFeedback, setShowFeedback] = useState(true); // ALWAYS SHOW by default
  const [specificFeedback, setSpecificFeedback] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [showSpecificInput, setShowSpecificInput] = useState(false);

  const sendFeedback = async (
    type: 'approve' | 'wrong' | 'needs_edit' | 'fix_required' | 'specific',
    score: number,
    specific?: string
  ) => {
    const feedbackData: FeedbackData = {
      sessionId,
      messageId,
      company,
      responseType,
      feedbackType: type,
      score,
      specificFeedback: specific || specificFeedback,
      timestamp: new Date().toISOString()
    };

    try {
      // Store in simplified RL system
      const rlResponse = await fetch('/api/rl/store', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          query: '', // Would need to pass this from parent
          response: '', // Would need to pass this from parent
          feedback: specific || specificFeedback || `Feedback: ${type}`,
          score,
          company: company || 'general',
          agent: responseType
        })
      });
      
      // Also send to corrections for pattern extraction
      const response = await fetch('/api/agent/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          company: company || 'general',
          modelType: responseType,
          correction: specific || specificFeedback || `Feedback: ${type} (score: ${score})`,
          timestamp: feedbackData.timestamp
        })
      });

      if (response.ok) {
        setFeedbackSent(true);
        if (onFeedback) {
          onFeedback(feedbackData);
        }
        
        // Hide feedback UI after 2 seconds
        setTimeout(() => {
          setShowFeedback(false);
          setFeedbackSent(false);
        }, 2000);
      }
    } catch (error) {
      console.error('Error sending feedback:', error);
    }
  };

  const feedbackButtons = [
    { 
      icon: ThumbsUp, 
      label: 'Approve', 
      type: 'approve' as const, 
      score: 1.0, 
      color: 'text-green-600 hover:bg-green-50' 
    },
    { 
      icon: ThumbsDown, 
      label: 'Wrong', 
      type: 'wrong' as const, 
      score: -0.8, 
      color: 'text-red-600 hover:bg-red-50' 
    },
    { 
      icon: Edit3, 
      label: 'Needs Edit', 
      type: 'needs_edit' as const, 
      score: -0.1, 
      color: 'text-yellow-600 hover:bg-yellow-50' 
    },
    { 
      icon: AlertCircle, 
      label: 'Fix Required', 
      type: 'fix_required' as const, 
      score: -0.6, 
      color: 'text-orange-600 hover:bg-orange-50' 
    },
    { 
      icon: MessageSquare, 
      label: 'Specific Feedback', 
      type: 'specific' as const, 
      score: 0, 
      color: 'text-blue-600 hover:bg-blue-50',
      action: () => setShowSpecificInput(true)
    }
  ];

  if (feedbackSent) {
    return (
      <div className="flex items-center gap-2 text-green-600 text-sm mt-2">
        <CheckCircle className="h-4 w-4" />
        <span>Feedback received! The agent will learn from this.</span>
      </div>
    );
  }

  return (
    <div className="mt-2">
      <div className="inline-flex items-center gap-1 p-1 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        <span className="text-xs text-gray-500 px-2">RL:</span>
        
        {!showSpecificInput ? (
          <>
            {feedbackButtons.map((button) => {
              const Icon = button.icon;
              return (
                <Button
                  key={button.type}
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (button.action) {
                      button.action();
                    } else {
                      sendFeedback(button.type, button.score);
                    }
                  }}
                  className={`h-7 px-2 ${button.color}`}
                >
                  <Icon className="h-3 w-3" />
                </Button>
              );
            })}
          </>
          ) : (
            <div className="space-y-2">
              <Textarea
                value={specificFeedback}
                onChange={(e) => setSpecificFeedback(e.target.value)}
                placeholder="e.g., 'Revenue should be 350M not 500M' or 'Growth rate should decay 10% per year' or 'Missing tax calculation'"
                className="min-h-Array.from(x) text-sm"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => sendFeedback('specific', 0, specificFeedback)}
                  disabled={!specificFeedback.trim()}
                >
                  Submit Feedback
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setShowSpecificInput(false);
                    setSpecificFeedback('');
                  }}
                >
                  Cancel
                </Button>
              </div>
              <div className="text-xs text-gray-500">
                <p className="font-medium mb-1">Examples of good feedback:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  <li>"Revenue should be $350M based on latest earnings"</li>
                  <li>"This company was acquired by Microsoft in 2023"</li>
                  <li>"Growth rate too high - use 20% declining by 5% yearly"</li>
                  <li>"Missing competitor: Anthropic"</li>
                  <li>"Valuation should be $2B not $5B"</li>
                </ul>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}