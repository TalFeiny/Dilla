'use client';

import { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, Edit, RotateCcw, TrendingUp, MessageSquare, Send } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RLFeedbackPanelProps {
  sessionId?: string;
  company?: string;
  modelType?: string;
  onFeedback?: (reward: number, specificFeedback?: string) => void;
  isEnabled?: boolean;
  commands?: string[];
  waitingForFeedback?: boolean;
}

export default function RLFeedbackPanel({ 
  sessionId, 
  company, 
  modelType,
  onFeedback,
  isEnabled = true,
  commands = [],
  waitingForFeedback = false,
  rewardBreakdown
}: RLFeedbackPanelProps & { rewardBreakdown?: any }) {
  const [rewards, setRewards] = useState<number[]>([]);
  const [learningStats, setLearningStats] = useState<any>(null);
  const [showStats, setShowStats] = useState(false);
  const [showFeedbackInput, setShowFeedbackInput] = useState(true);
  const [specificFeedback, setSpecificFeedback] = useState('');
  const [feedbackHistory, setFeedbackHistory] = useState<string[]>([]);
  const [showRewardDetails, setShowRewardDetails] = useState(false);

  useEffect(() => {
    loadLearningStats();
  }, []);

  const loadLearningStats = async () => {
    // const stats = await rlSystem.getLearningStats();
    // setLearningStats(stats);
    // Mock stats for now
    setLearningStats({
      totalEpisodes: 0,
      averageScore: 0,
      improvement: {}
    });
  };

  const giveFeedback = async (action: string, value: number) => {
    // Use the value parameter directly as the reward
    const reward = value;
    
    // Update local state
    setRewards([...rewards, reward]);
    
    // Callback with reward
    onFeedback?.(reward);
    
    // Visual feedback
    const button = document.getElementById(`feedback-${action}`);
    if (button) {
      button.classList.add('animate-pulse');
      setTimeout(() => button.classList.remove('animate-pulse'), 500);
    }
    
    // Store correction for learning
    await storeCorrection(`Feedback: ${action} (reward: ${reward})`);
  };

  const submitSpecificFeedback = async () => {
    if (!specificFeedback.trim()) return;
    
    // Send semantic feedback directly - let the RL system parse it
    onFeedback?.(specificFeedback, specificFeedback);
    
    // Store in history
    setFeedbackHistory([...feedbackHistory, specificFeedback]);
    
    // Clear input
    setSpecificFeedback('');
    
    // Store for training
    await storeCorrection(specificFeedback);
    
    return;
    
    // Old parsing code below (kept for reference)
    const lower = specificFeedback.toLowerCase();
    let reward = 0;
    let reason = specificFeedback;
    
    // Enhanced semantic analysis for financial model feedback
    if (lower.includes('perfect') || lower.includes('excellent') || lower.includes('great')) {
      reward = 1.0;
    } else if (lower.includes('good') || lower.includes('correct') || lower.includes('right')) {
      reward = 0.7;
    } else if (lower.includes('almost') || lower.includes('close')) {
      reward = 0.4;
    }
    // Financial metric specific feedback
    else if (lower.match(/revenue.*should.*be|sales.*should|turnover/)) {
      reward = -0.5;
      reason = `Revenue correction: ${specificFeedback}`;
    } else if (lower.match(/growth.*rate|cagr|compound/)) {
      reward = -0.4;
      reason = `Growth rate adjustment: ${specificFeedback}`;
    } else if (lower.match(/discount.*rate|wacc|cost.*capital/)) {
      reward = -0.4;
      reason = `Discount rate correction: ${specificFeedback}`;
    } else if (lower.match(/margin|ebitda|profit/)) {
      reward = -0.4;
      reason = `Margin correction: ${specificFeedback}`;
    } else if (lower.match(/tax|depreciation|amortization/)) {
      reward = -0.3;
      reason = `Tax/D&A adjustment: ${specificFeedback}`;
    }
    // Calculation issues
    else if (lower.includes('formula') || lower.includes('calculation')) {
      reward = -0.6;
      reason = `Formula error: ${specificFeedback}`;
    } else if (lower.includes('wrong') || lower.includes('incorrect')) {
      reward = -0.8;
    } else if (lower.includes('missing') || lower.includes('forgot') || lower.includes('add')) {
      reward = -0.4;
      reason = `Missing element: ${specificFeedback}`;
    } else if (lower.includes('should be') || lower.includes('change to') || lower.includes('use')) {
      reward = -0.3;
      reason = `Correction needed: ${specificFeedback}`;
    }
    // Model structure feedback
    else if (lower.includes('format') || lower.includes('layout') || lower.includes('structure')) {
      reward = -0.2;
      reason = `Formatting: ${specificFeedback}`;
    }
    
    // Record the specific feedback (local for now)
    // await rlSystem.recordReward(reward, reason);
    
    // Store feedback for training
    setFeedbackHistory([...feedbackHistory, specificFeedback]);
    setRewards([...rewards, reward]);
    
    // Clear input
    setSpecificFeedback('');
    setShowFeedbackInput(false);
    
    // Callback with specific feedback
    onFeedback?.(reward, specificFeedback);
    
    // Store the specific correction for fine-tuning
    await storeCorrection(specificFeedback);
  };

  const storeCorrection = async (correction: string) => {
    // Send to backend for storage
    try {
      await fetch('/api/agent/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          company,
          modelType,
          correction,
          timestamp: new Date()
        })
      });
    } catch (error) {
      console.error('Failed to store correction:', error);
    }
  };

  // Add local calculateReward function
  const calculateReward = (action: string): number => {
    const rewards: Record<string, number> = {
      'approve': 1.0,
      'good': 0.8,
      'correct': 0.7,
      'keep': 0.5,
      'delete': -1.0,
      'wrong': -0.8,
      'fix': -0.6,
      'change': -0.4,
      'why': -0.2,
      'edit': -0.1,
    };
    
    for (const [key, reward] of Object.entries(rewards)) {
      if (action.toLowerCase().includes(key)) {
        return reward;
      }
    }
    return 0;
  };

  const finishSession = async () => {
    // Calculate final score from all rewards
    const finalScore = rewards.length > 0 
      ? rewards.reduce((a, b) => a + b, 0) / rewards.length 
      : 0;
    
    // Learn from this trajectory (disabled for now)
    // await rlSystem.learnFromTrajectory(finalScore);
    
    // Store feedback summary
    if (feedbackHistory.length > 0) {
      await storeCorrection(`Session completed with score ${finalScore.toFixed(2)}. Feedback: ${feedbackHistory.join('; ')}`);
    }
    
    // Reset all states
    setRewards([]);
    setFeedbackHistory([]);
    setShowFeedbackInput(false);
    setSpecificFeedback('');
    
    // Reload stats
    await loadLearningStats();
    
    // Notify parent that session is finished
    onFeedback?.(finalScore, `Session completed with ${feedbackHistory.length} corrections`);
  };

  const getScoreColor = (score: number) => {
    if (score > 0.5) return 'text-green-500';
    if (score > 0) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getImprovementIcon = (improvement: number) => {
    if (improvement > 10) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (improvement > 0) return <TrendingUp className="w-4 h-4 text-yellow-500 rotate-45" />;
    return <TrendingUp className="w-4 h-4 text-red-500 rotate-90" />;
  };

  return (
    <div className={cn(
      "bg-gray-800 text-gray-100 rounded p-2 space-y-2 border",
      isEnabled ? "border-green-500/20" : "border-gray-700/20"
    )}>
      {/* Status Indicator with Automatic Score */}
      {isEnabled && (
        <div className="flex items-center justify-between mb-2 text-xs">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-2 h-2 rounded-full",
              waitingForFeedback ? "bg-yellow-400 animate-pulse" : "bg-green-400"
            )} />
            <span className="text-gray-400">
              {waitingForFeedback ? "Waiting for feedback..." : "RL System Active"}
            </span>
          </div>
          {rewardBreakdown && (
            <button
              onClick={() => setShowRewardDetails(!showRewardDetails)}
              className={cn(
                "px-2 py-1 rounded text-xs font-mono",
                rewardBreakdown.totalReward > 0.5 ? "bg-green-900 text-green-400" :
                rewardBreakdown.totalReward > 0 ? "bg-yellow-900 text-yellow-400" :
                "bg-red-900 text-red-400"
              )}
            >
              Auto: {(rewardBreakdown.totalReward * 100).toFixed(0)}%
            </button>
          )}
        </div>
      )}
      
      {/* Reward Breakdown Details */}
      {showRewardDetails && rewardBreakdown && (
        <div className="mb-2 p-2 bg-gray-900 rounded text-xs space-y-1">
          <div className="font-bold text-gray-300 mb-1">Automatic Scoring:</div>
          {Object.entries(rewardBreakdown.components).map(([key, value]: [string, any]) => (
            <div key={key} className="flex justify-between">
              <span className="text-gray-500 capitalize">{key}:</span>
              <div className="flex items-center gap-1">
                <div className="w-16 bg-gray-700 rounded-full h-2">
                  <div 
                    className={cn(
                      "h-2 rounded-full",
                      value > 0.5 ? "bg-green-500" :
                      value > 0 ? "bg-yellow-500" :
                      "bg-red-500"
                    )}
                    style={{ width: `${Math.abs(value) * 100}%` }}
                  />
                </div>
                <span className={cn(
                  "font-mono w-10 text-right",
                  value > 0.5 ? "text-green-400" :
                  value > 0 ? "text-yellow-400" :
                  "text-red-400"
                )}>
                  {(value * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
          <div className="border-t border-gray-700 pt-1 mt-1">
            <div className="flex justify-between font-bold">
              <span className="text-gray-300">Total Score:</span>
              <span className={cn(
                "font-mono",
                rewardBreakdown.totalReward > 0.5 ? "text-green-400" :
                rewardBreakdown.totalReward > 0 ? "text-yellow-400" :
                "text-red-400"
              )}>
                {(rewardBreakdown.totalReward * 100).toFixed(0)}%
              </span>
            </div>
            <div className="text-gray-500 text-xs mt-1">
              Confidence: {(rewardBreakdown.confidence * 100).toFixed(0)}%
            </div>
          </div>
          {rewardBreakdown.explanation && rewardBreakdown.explanation.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-700">
              {rewardBreakdown.explanation.map((exp: string, i: number) => (
                <div key={i} className="text-gray-400 text-xs">• {exp}</div>
              ))}
            </div>
          )}
        </div>
      )}
      
      {/* Compact Feedback */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-green-400">Feedback:</span>
        <div className="flex gap-1 flex-1">
          <button
            onClick={() => giveFeedback('perfect', 1.0)}
            className="px-2 py-1 bg-green-900 hover:bg-green-800 rounded text-xs"
            title="Perfect (100%)">
            💯
          </button>
          
          <button
            onClick={() => giveFeedback('good', 0.7)}
            className="px-2 py-1 bg-green-900 hover:bg-green-800 rounded text-xs"
            title="Good (70%)">
            👍
          </button>
          
          <button
            onClick={() => giveFeedback('okay', 0.4)}
            className="px-2 py-1 bg-yellow-900 hover:bg-yellow-800 rounded text-xs"
            title="Okay (40%)">
            👌
          </button>
          
          <button
            onClick={() => giveFeedback('poor', -0.3)}
            className="px-2 py-1 bg-orange-900 hover:bg-orange-800 rounded text-xs"
            title="Poor (-30%)">
            👎
          </button>
          
          <button
            onClick={() => giveFeedback('wrong', -0.8)}
            className="px-2 py-1 bg-red-900 hover:bg-red-800 rounded text-xs"
            title="Wrong (-80%)">
            ❌
          </button>
        
          <input
            type="text"
            value={specificFeedback}
            onChange={(e) => setSpecificFeedback(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submitSpecificFeedback()}
            placeholder="e.g. Revenue should be 350M"
            className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-xs focus:outline-none focus:border-green-400"
          />
          <button
            onClick={submitSpecificFeedback}
            disabled={!specificFeedback.trim()}
            className="px-2 py-1 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 rounded text-xs">
            Send
          </button>
        </div>
      </div>
        
        {/* Feedback History */}
        {feedbackHistory.length > 0 && (
          <div className="p-2 bg-gray-800 rounded space-y-1">
            <div className="text-xs text-gray-500">Your corrections:</div>
            {feedbackHistory.map((fb, i) => (
              <div key={i} className="text-xs text-gray-300 pl-2 border-l-2 border-gray-600">
                {fb}
              </div>
            ))}
          </div>
        )}
        
        {/* Current Session Rewards */}
        {rewards.length > 0 && (
          <div className="mt-2 p-2 bg-gray-800 rounded">
            <div className="flex items-center justify-between text-xs">
              <span>Session Rewards: {rewards.length}</span>
              <span className={cn(
                "font-mono",
                getScoreColor(rewards.reduce((a, b) => a + b, 0) / rewards.length)
              )}>
                Avg: {(rewards.reduce((a, b) => a + b, 0) / rewards.length).toFixed(2)}
              </span>
            </div>
            
            <div className="flex gap-1 mt-1">
              {rewards.map((r, i) => (
                <div
                  key={i}
                  className={cn(
                    "w-2 h-4 rounded-sm",
                    r > 0.5 ? "bg-green-500" :
                    r > 0 ? "bg-yellow-500" :
                    "bg-red-500"
                  )}
                  style={{ opacity: 0.5 + Math.abs(r) * 0.5 }}
                  title={`Reward: ${r.toFixed(2)}`}
                />
              ))}
            </div>
          </div>
        )}
        
        {/* Finish Session */}
        {rewards.length > 0 && (
          <button
            onClick={finishSession}
            className="w-full px-3 py-2 bg-blue-900 hover:bg-blue-800 rounded text-sm"
          >
            Finish & Train Model
          </button>
        )}

      {/* Learning Statistics */}
      <div className="border-t border-gray-700 pt-3">
        <button
          onClick={() => setShowStats(!showStats)}
          className="flex items-center justify-between w-full text-sm text-gray-400 hover:text-gray-300"
        >
          <span>Learning Progress</span>
          <span className="text-xs">{showStats ? '−' : '+'}</span>
        </button>
        
        {showStats && learningStats && (
          <div className="mt-3 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Total Episodes:</span>
              <span>{learningStats.totalEpisodes}</span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-gray-500">Avg Score:</span>
              <span className={getScoreColor(learningStats.averageScore)}>
                {learningStats.averageScore?.toFixed(2) || '0.00'}
              </span>
            </div>
            
            {/* Model-specific improvements */}
            {learningStats.improvement && Object.entries(learningStats.improvement).map(([type, improvement]) => (
              <div key={type} className="flex items-center justify-between">
                <span className="text-gray-500">{type}:</span>
                <div className="flex items-center gap-1">
                  {getImprovementIcon(improvement as number)}
                  <span className={cn(
                    "font-mono",
                    (improvement as number) > 0 ? "text-green-500" : "text-red-500"
                  )}>
                    {(improvement as number) > 0 ? '+' : ''}{(improvement as number).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
            
            {/* Learning Curves Mini Chart */}
            {learningStats.learningCurves && (
              <div className="mt-2 p-2 bg-gray-800 rounded">
                <div className="text-gray-500 mb-1">Learning Curves</div>
                {Object.entries(learningStats.learningCurves).map(([type, scores]) => (
                  <div key={type} className="flex items-center gap-2 mb-1">
                    <span className="text-gray-400 text-xs w-20 truncate">{type}:</span>
                    <div className="flex gap-px flex-1">
                      {(scores as number[]).slice(-20).map((score, i) => (
                        <div
                          key={i}
                          className="flex-1 bg-blue-500"
                          style={{
                            height: `${score * 20}px`,
                            opacity: 0.3 + score * 0.7
                          }}
                          title={`Episode ${i + 1}: ${score.toFixed(2)}`}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}