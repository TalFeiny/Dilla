'use client';

import AgentFeedback from '@/components/agent/AgentFeedback';

export default function TestFeedbackPage() {
  return (
    <div className="container mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">Testing Feedback Component</h1>
      
      <div className="space-y-4">
        <div className="p-4 border rounded">
          <p className="mb-2">Test Message: OpenAI raised $6.6B at $157B valuation</p>
          <AgentFeedback
            sessionId="test-session"
            messageId="test-message-1"
            company="OpenAI"
            responseType="CIM"
            onFeedback={(feedback) => {
              console.log('Feedback:', feedback);
              alert(`Feedback submitted: ${JSON.stringify(feedback)}`);
            }}
          />
        </div>
        
        <div className="p-4 border rounded">
          <p className="mb-2">Test Message: Stripe revenue is $500M</p>
          <AgentFeedback
            sessionId="test-session"
            messageId="test-message-2"
            company="Stripe"
            responseType="Financial Analysis"
            onFeedback={(feedback) => {
              console.log('Feedback:', feedback);
              alert(`Feedback submitted: ${JSON.stringify(feedback)}`);
            }}
          />
        </div>
      </div>
    </div>
  );
}