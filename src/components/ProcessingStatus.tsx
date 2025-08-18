'use client';

import { useState, useEffect } from 'react';

interface ProcessingEvent {
  type: 'status' | 'processing' | 'completed' | 'failed' | 'error';
  message: string;
  status?: string;
  summary?: any;
  data?: any;
  error?: string;
}

interface ProcessingStatusProps {
  documentId: string;
  onComplete?: (data: any) => void;
  onError?: (error: string) => void;
}

export default function ProcessingStatus({ documentId, onComplete, onError }: ProcessingStatusProps) {
  const [events, setEvents] = useState<ProcessingEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<string>('connecting');

  useEffect(() => {
    const eventSource = new EventSource(`/api/documents/${documentId}/stream`);

    eventSource.onopen = () => {
      setIsConnected(true);
      setCurrentStatus('connected');
    };

    eventSource.onmessage = (event) => {
      try {
        const data: ProcessingEvent = JSON.parse(event.data);
        setEvents(prev => [...prev, data]);
        
        if (data.type === 'completed') {
          setCurrentStatus('completed');
          onComplete?.(data.data);
          eventSource.close();
        } else if (data.type === 'failed') {
          setCurrentStatus('failed');
          onError?.(data.error || 'Processing failed');
          eventSource.close();
        } else if (data.type === 'processing') {
          setCurrentStatus('processing');
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      setCurrentStatus('error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [documentId, onComplete, onError]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'processing': return 'text-blue-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'processing': return '⏳';
      case 'error': return '⚠️';
      default: return '🔄';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center space-x-3 mb-4">
        <span className="text-2xl">{getStatusIcon(currentStatus)}</span>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Processing Status</h3>
          <p className={`text-sm ${getStatusColor(currentStatus)}`}>
            {currentStatus === 'connecting' && 'Connecting to processing stream...'}
            {currentStatus === 'connected' && 'Connected, waiting for updates...'}
            {currentStatus === 'processing' && 'Analysis in progress...'}
            {currentStatus === 'completed' && 'Analysis completed successfully!'}
            {currentStatus === 'failed' && 'Analysis failed'}
            {currentStatus === 'error' && 'Connection error'}
          </p>
        </div>
      </div>

      {events.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-gray-700">Processing Log:</h4>
          <div className="bg-gray-50 rounded-md p-3 max-h-40 overflow-y-auto">
            {events.map((event, index) => (
              <div key={index} className="text-sm mb-1">
                <span className="font-medium text-gray-600">
                  {new Date().toLocaleTimeString()}
                </span>
                <span className="ml-2 text-gray-800">{event.message}</span>
                {event.error && (
                  <div className="ml-4 text-red-600 text-xs">{event.error}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {currentStatus === 'processing' && (
        <div className="mt-4">
          <div className="flex items-center space-x-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span className="text-sm text-gray-600">Processing document...</span>
          </div>
        </div>
      )}

      {currentStatus === 'completed' && (
        <div className="mt-4 p-3 bg-green-50 rounded-md">
          <p className="text-green-800 text-sm">
            ✅ Analysis completed! You can now view the results.
          </p>
        </div>
      )}

      {currentStatus === 'failed' && (
        <div className="mt-4 p-3 bg-red-50 rounded-md">
          <p className="text-red-800 text-sm">
            ❌ Analysis failed. Please try again or contact support.
          </p>
        </div>
      )}
    </div>
  );
} 