'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { 
  ThumbsUp, 
  ThumbsDown, 
  Edit3, 
  MessageSquare,
  CheckCircle,
  X,
  Star,
  Brain,
  TrendingUp
} from 'lucide-react';
import UnifiedRLSystem, { OutputFormat } from '@/lib/rl-system';

interface UnifiedFeedbackProps {
  sessionId?: string;
  prompt: string;
  response: any;
  outputFormat: OutputFormat;
  onClose?: () => void;
  experienceId?: string; // If already saved
  metadata?: any;
}

export default function UnifiedFeedback({ 
  sessionId, 
  prompt, 
  response,
  outputFormat,
  onClose,
  experienceId: providedExperienceId,
  metadata
}: UnifiedFeedbackProps) {
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [corrections, setCorrections] = useState('');
  const [rating, setRating] = useState(0);
  const [showCorrections, setShowCorrections] = useState(false);
  const [experienceId, setExperienceId] = useState(providedExperienceId);
  const [rlSystem] = useState(() => new UnifiedRLSystem(outputFormat));
  const [stats, setStats] = useState<any>(null);

  // Save the output when component mounts (if not already saved)
  useEffect(() => {
    const saveInitialOutput = async () => {
      if (!experienceId && response) {
        const result = await rlSystem.saveOutput({
          prompt,
          output: response,
          outputFormat,
          metadata: {
            ...metadata,
            sessionId,
            timestamp: new Date().toISOString()
          }
        });
        
        if (result.experienceId) {
          setExperienceId(result.experienceId);
          console.log('✅ Output saved to Supabase:', result.experienceId);
        }
      }
    };
    
    saveInitialOutput();
    
    // Load stats
    rlSystem.getStats(outputFormat).then(setStats);
  }, [experienceId, response, rlSystem, prompt, outputFormat, metadata, sessionId]);

  const sendFeedback = async (feedbackType: 'positive' | 'negative' | 'correction' | 'semantic', specificText?: string) => {
    if (!experienceId) {
      console.error('No experience ID to attach feedback to');
      return;
    }

    try {
      // Calculate reward score based on feedback type and rating
      let rewardScore = 0;
      if (feedbackType === 'positive') {
        rewardScore = rating ? rating / 5 : 1.0;
      } else if (feedbackType === 'negative') {
        rewardScore = rating ? (rating - 3) / 5 : -1.0;
      } else if (feedbackType === 'correction') {
        rewardScore = 0.3; // Corrections are valuable for learning
      } else if (feedbackType === 'semantic' && corrections) {
        rewardScore = 0.5; // Semantic feedback is very valuable
      }

      // Save feedback to Supabase
      const result = await rlSystem.saveFeedback({
        experienceId,
        feedbackType,
        feedbackText: specificText || corrections || `Rating: ${rating}/5`,
        correctedOutput: feedbackType === 'correction' ? corrections : undefined,
        rewardScore
      });

      if (result.success) {
        console.log('✅ Feedback saved:', result.feedbackId);
        setFeedbackSent(true);
        
        // Update stats
        const newStats = await rlSystem.getStats(outputFormat);
        setStats(newStats);
        
        setTimeout(() => {
          setFeedbackSent(false);
          if (onClose) onClose();
        }, 2000);
      }
    } catch (error) {
      console.error('Failed to send feedback:', error);
    }
  };

  if (feedbackSent) {
    return (
      <div className="fixed bottom-4 right-4 bg-green-500 text-white p-4 rounded-lg shadow-lg flex items-center gap-2 z-50 animate-pulse">
        <CheckCircle className="h-5 w-5" />
        <div>
          <div className="font-semibold">Thank you for your feedback!</div>
          <div className="text-xs opacity-90">Improving our AI models...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-4 z-50 max-w-md">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            How was this {outputFormat} generation?
          </h3>
          {experienceId && (
            <div className="text-xs text-gray-500 mt-1">
              Session: {experienceId.slice(0, 8)}...
            </div>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-6 w-6 p-0"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Stats Display */}
      {stats && (
        <div className="bg-gray-50 dark:bg-gray-900 rounded p-2 mb-3 grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1">
            <Brain className="h-3 w-3 text-blue-500" />
            <span className="text-gray-600 dark:text-gray-400">Total:</span>
            <span className="font-semibold">{stats.totalExperiences}</span>
          </div>
          <div className="flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-green-500" />
            <span className="text-gray-600 dark:text-gray-400">Positive:</span>
            <span className="font-semibold">{(stats.positiveFeedbackRate * 100).toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* Star Rating */}
      <div className="flex gap-1 mb-3">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => setRating(star)}
            className="transition-all transform hover:scale-110"
          >
            <Star
              className={`h-5 w-5 ${
                star <= rating 
                  ? 'fill-yellow-400 text-yellow-400' 
                  : 'text-gray-300 hover:text-gray-400'
              }`}
            />
          </button>
        ))}
        {rating > 0 && (
          <span className="text-xs text-gray-500 ml-2 self-center">
            {rating === 5 ? 'Perfect!' : 
             rating === 4 ? 'Good' : 
             rating === 3 ? 'OK' : 
             rating === 2 ? 'Poor' : 'Bad'}
          </span>
        )}
      </div>

      {/* Quick Feedback Buttons */}
      <div className="flex gap-2 mb-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => sendFeedback('positive')}
          className="flex-1 hover:bg-green-50 hover:text-green-600 hover:border-green-600"
        >
          <ThumbsUp className="h-4 w-4 mr-1" />
          Good
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => sendFeedback('negative')}
          className="flex-1 hover:bg-red-50 hover:text-red-600 hover:border-red-600"
        >
          <ThumbsDown className="h-4 w-4 mr-1" />
          Poor
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowCorrections(!showCorrections)}
          className="flex-1 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-600"
        >
          <Edit3 className="h-4 w-4 mr-1" />
          Edit
        </Button>
      </div>

      {/* Corrections Input */}
      {showCorrections && (
        <div className="space-y-2">
          <Textarea
            placeholder="What should be improved? Be specific... (e.g., 'Revenue should be $350M, not $300M')"
            value={corrections}
            onChange={(e) => setCorrections(e.target.value)}
            rows={3}
            className="text-sm"
          />
          <Button
            onClick={() => sendFeedback('semantic', corrections)}
            disabled={!corrections.trim()}
            className="w-full"
            size="sm"
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Submit Corrections
          </Button>
        </div>
      )}

      <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
        Your feedback helps improve our AI models
      </p>
    </div>
  );
}