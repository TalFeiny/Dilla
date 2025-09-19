'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { 
  ThumbsUp, 
  ThumbsDown, 
  Edit3, 
  MessageSquare,
  CheckCircle,
  X,
  Star
} from 'lucide-react';

interface UnifiedFeedbackProps {
  sessionId: string;
  prompt: string;
  response: any;
  outputFormat: string;
  onClose?: () => void;
}

export default function UnifiedFeedback({ 
  sessionId, 
  prompt, 
  response,
  outputFormat,
  onClose 
}: UnifiedFeedbackProps) {
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [corrections, setCorrections] = useState('');
  const [rating, setRating] = useState(0);
  const [showCorrections, setShowCorrections] = useState(false);

  const sendFeedback = async (feedbackType: string, score: number) => {
    try {
      // Use the EXISTING RL system that saves to model_corrections table
      const rlScore = feedbackType === 'good' ? 1.0 : 
                      feedbackType === 'bad' ? -1.0 : 
                      feedbackType === 'edit' ? 0.5 : 
                      (rating / 5); // Normalize star rating to 0-1
      
      await fetch('/api/rl/store', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          query: prompt,
          response: JSON.stringify(response),
          feedback: corrections || `${feedbackType} (rating: ${rating}/5)`,
          score: rlScore,
          company: outputFormat, // Use format as context
          agent: outputFormat
        })
      });
      
      // Also store corrections if user provided specific feedback
      if (corrections && corrections.trim()) {
        await fetch('/api/agent/corrections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId,
            company: outputFormat,
            modelType: 'qwen3:latest',
            correction: corrections,
            timestamp: new Date().toISOString()
          })
        });
      }
      
      setFeedbackSent(true);
      setTimeout(() => {
        setFeedbackSent(false);
        if (onClose) onClose();
      }, 2000);
      
    } catch (error) {
      console.error('Failed to send feedback:', error);
    }
  };

  if (feedbackSent) {
    return (
      <div className="fixed bottom-4 right-4 bg-green-500 text-white p-4 rounded-lg shadow-lg flex items-center gap-2 z-50">
        <CheckCircle className="h-5 w-5" />
        <span>Thank you for your feedback!</span>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-4 z-50 max-w-md">
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          How was this {outputFormat} generation?
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-6 w-6 p-0"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Star Rating */}
      <div className="flex gap-1 mb-3">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => setRating(star)}
            className="transition-colors"
          >
            <Star
              className={`h-5 w-5 ${
                star <= rating 
                  ? 'fill-yellow-400 text-yellow-400' 
                  : 'text-gray-300'
              }`}
            />
          </button>
        ))}
      </div>

      {/* Quick Feedback Buttons */}
      <div className="flex gap-2 mb-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => sendFeedback('good', rating || 5)}
          className="flex-1"
        >
          <ThumbsUp className="h-4 w-4 mr-1" />
          Good
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => sendFeedback('bad', rating || 2)}
          className="flex-1"
        >
          <ThumbsDown className="h-4 w-4 mr-1" />
          Poor
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowCorrections(!showCorrections)}
          className="flex-1"
        >
          <Edit3 className="h-4 w-4 mr-1" />
          Edit
        </Button>
      </div>

      {/* Corrections Input */}
      {showCorrections && (
        <div className="space-y-2">
          <Textarea
            placeholder="What should be improved? Be specific..."
            value={corrections}
            onChange={(e) => setCorrections(e.target.value)}
            rows={3}
            className="text-sm"
          />
          <Button
            onClick={() => sendFeedback('edit', rating || 3)}
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