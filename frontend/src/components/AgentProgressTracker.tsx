'use client';

import React, { useState, useEffect } from 'react';
import { AgentProgress } from '@/lib/agent-observability';
import { 
  Activity, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Zap,
  Database,
  Code,
  Brain,
  Loader2,
  ChevronDown,
  ChevronUp,
  BarChart3
} from 'lucide-react';

interface AgentProgressTrackerProps {
  taskId: string;
  onClose?: () => void;
}

export default function AgentProgressTracker({ taskId, onClose }: AgentProgressTrackerProps) {
  const [progress, setProgress] = useState<AgentProgress | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Connect to SSE stream
    const eventSource = new EventSource(`/api/agent/progress/${taskId}`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== 'connected') {
          setProgress(data);
        }
      } catch (err) {
        console.error('Failed to parse progress:', err);
      }
    };
    
    eventSource.onerror = () => {
      setError('Connection lost');
      eventSource.close();
    };
    
    return () => {
      eventSource.close();
    };
  }, [taskId]);

  if (!progress) {
    return (
      <div className="fixed bottom-4 right-4 bg-white rounded-lg shadow-xl border border-gray-200 p-4 w-96">
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          <span className="text-sm font-medium">Initializing agent...</span>
        </div>
      </div>
    );
  }

  const stageIcons = {
    initializing: <Clock className="w-4 h-4" />,
    analyzing: <Brain className="w-4 h-4" />,
    gathering: <Database className="w-4 h-4" />,
    processing: <Code className="w-4 h-4" />,
    generating: <Zap className="w-4 h-4" />,
    finalizing: <BarChart3 className="w-4 h-4" />,
    complete: <CheckCircle className="w-4 h-4" />,
    error: <AlertCircle className="w-4 h-4" />
  };

  const stageColors = {
    initializing: 'text-gray-600',
    analyzing: 'text-purple-600',
    gathering: 'text-blue-600',
    processing: 'text-indigo-600',
    generating: 'text-green-600',
    finalizing: 'text-teal-600',
    complete: 'text-green-600',
    error: 'text-red-600'
  };

  return (
    <div className="fixed bottom-4 right-4 bg-white rounded-lg shadow-xl border border-gray-200 w-[400px] max-h-[600px] overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`${stageColors[progress.stage]}`}>
              {stageIcons[progress.stage]}
            </div>
            <div>
              <h3 className="font-semibold text-sm">Agent Processing</h3>
              <p className="text-xs text-gray-500">{progress.elapsed} elapsed</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
            <span className="capitalize">{progress.stage}</span>
            <span>{progress.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className={`h-2 rounded-full transition-all duration-500 ${
                progress.stage === 'error' ? 'bg-red-500' : 
                progress.stage === 'complete' ? 'bg-green-500' : 'bg-blue-500'
              }`}
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        </div>

        {/* Current Message */}
        <p className="text-xs text-gray-600 mt-2 truncate">{progress.message}</p>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 space-y-4 overflow-y-auto max-h-[400px]">
          {/* Current Activity */}
          {(progress.currentSkill || progress.currentTool) && (
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-blue-700">
                <Activity className="w-4 h-4" />
                <span className="text-xs font-medium">Current Activity</span>
              </div>
              {progress.currentSkill && (
                <p className="text-xs mt-1">Skill: {progress.currentSkill}</p>
              )}
              {progress.currentTool && (
                <p className="text-xs mt-1">Tool: {progress.currentTool}</p>
              )}
            </div>
          )}

          {/* Metrics */}
          {progress.metrics && (
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500">API Calls</p>
                <p className="text-sm font-semibold">{progress.metrics.apiCalls}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500">Data Points</p>
                <p className="text-sm font-semibold">{progress.metrics.dataPoints}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500">Cache Hits</p>
                <p className="text-sm font-semibold">{progress.metrics.cacheHits}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500">Tokens Used</p>
                <p className="text-sm font-semibold">{progress.metrics.tokensUsed}</p>
              </div>
            </div>
          )}

          {/* Subtasks */}
          {progress.subTasks && progress.subTasks.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2">Tasks</h4>
              <div className="space-y-1">
                {progress.subTasks.map((task, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      {task.status === 'complete' ? (
                        <CheckCircle className="w-3 h-3 text-green-500" />
                      ) : task.status === 'running' ? (
                        <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />
                      ) : task.status === 'failed' ? (
                        <AlertCircle className="w-3 h-3 text-red-500" />
                      ) : (
                        <Clock className="w-3 h-3 text-gray-400" />
                      )}
                      <span className={task.status === 'complete' ? 'text-gray-500' : ''}>
                        {task.name}
                      </span>
                    </div>
                    {task.duration && (
                      <span className="text-gray-400">{task.duration}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resources Used */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            {progress.skillsCompleted.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-700 mb-1">Skills Used</h4>
                <div className="space-y-0.5">
                  {progress.skillsCompleted.map((skill, idx) => (
                    <div key={idx} className="text-gray-600">• {skill}</div>
                  ))}
                </div>
              </div>
            )}
            
            {progress.dataSourcesAccessed.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-700 mb-1">Data Sources</h4>
                <div className="space-y-0.5">
                  {progress.dataSourcesAccessed.map((source, idx) => (
                    <div key={idx} className="text-gray-600">• {source}</div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Frameworks */}
          {progress.frameworksActivated.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-1">Frameworks</h4>
              <div className="flex flex-wrap gap-1">
                {progress.frameworksActivated.map((framework, idx) => (
                  <span key={idx} className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
                    {framework}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Errors */}
          {progress.errors && progress.errors.length > 0 && (
            <div className="bg-red-50 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-red-700 mb-1">Errors</h4>
              <div className="space-y-1">
                {progress.errors.map((error, idx) => (
                  <p key={idx} className="text-xs text-red-600">{error}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}