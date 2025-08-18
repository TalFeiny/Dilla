'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Check,
  AlertCircle,
  Edit3
} from 'lucide-react';

interface FeedbackPanelProps {
  messageId: string;
  routeId?: string;
  metadata?: {
    intent?: string;
    endpoint?: string;
    sources?: string[];
    confidence?: number;
  };
  onFeedback: (feedback: FeedbackData) => void;
}

export interface FeedbackData {
  messageId: string;
  routeId?: string;
  type: 'positive' | 'negative' | 'correction' | 'wrong_data';
  score?: number;
  details?: string;
  metadata?: any;
}

export default function FeedbackPanel({ 
  messageId, 
  routeId,
  metadata,
  onFeedback 
}: FeedbackPanelProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [details, setDetails] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const handleQuickFeedback = (type: 'positive' | 'negative') => {
    const feedback: FeedbackData = {
      messageId,
      routeId,
      type,
      score: type === 'positive' ? 1 : -1,
      metadata
    };
    
    onFeedback(feedback);
    setSelectedType(type);
    setSubmitted(true);
    
    // Reset after 3 seconds
    setTimeout(() => {
      setSubmitted(false);
      setSelectedType(null);
    }, 3000);
  };

  const handleDetailedFeedback = () => {
    if (!details.trim()) return;

    // Parse the details to detect correction type
    const isCorrection = details.toLowerCase().includes('should be') || 
                        details.toLowerCase().includes('actually') ||
                        details.toLowerCase().includes('wrong');
    
    const feedback: FeedbackData = {
      messageId,
      routeId,
      type: isCorrection ? 'correction' : 'negative',
      score: -0.5,
      details,
      metadata
    };
    
    onFeedback(feedback);
    setDetails('');
    setShowDetails(false);
    setSubmitted(true);
    setSelectedType('correction');
    
    setTimeout(() => {
      setSubmitted(false);
      setSelectedType(null);
    }, 3000);
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
        <Check className="h-4 w-4" />
        <span>Thanks for your feedback!</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Was this helpful?</span>
        
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 ${selectedType === 'positive' ? 'bg-green-100 dark:bg-green-900' : ''}`}
          onClick={() => handleQuickFeedback('positive')}
        >
          <ThumbsUp className="h-3 w-3 mr-1" />
          <span className="text-xs">Yes</span>
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 ${selectedType === 'negative' ? 'bg-red-100 dark:bg-red-900' : ''}`}
          onClick={() => handleQuickFeedback('negative')}
        >
          <ThumbsDown className="h-3 w-3 mr-1" />
          <span className="text-xs">No</span>
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          onClick={() => setShowDetails(!showDetails)}
        >
          <Edit3 className="h-3 w-3 mr-1" />
          <span className="text-xs">Correct</span>
        </Button>

        {metadata?.confidence && (
          <span className="ml-auto text-xs text-gray-400">
            Confidence: {(metadata.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {showDetails && (
        <div className="flex gap-2">
          <Textarea
            placeholder="E.g., 'Revenue should be 350M not 500M' or 'Missing competitor X'"
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            className="h-20 text-sm"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.metaKey) {
                handleDetailedFeedback();
              }
            }}
          />
          <Button
            size="sm"
            onClick={handleDetailedFeedback}
            disabled={!details.trim()}
          >
            <MessageSquare className="h-4 w-4" />
          </Button>
        </div>
      )}

      {metadata?.sources && metadata.sources.length > 0 && (
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <AlertCircle className="h-3 w-3" />
          <span>Sources: {metadata.sources.join(', ')}</span>
        </div>
      )}
    </div>
  );
}