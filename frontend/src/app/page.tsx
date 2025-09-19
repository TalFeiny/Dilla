'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import PaywallModal from '@/components/PaywallModal';
import { Sparkles, Brain, TrendingUp, Zap } from 'lucide-react';

export default function HomePage() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [showPaywall, setShowPaywall] = useState(false);
  const [hasUsedFreeGeneration, setHasUsedFreeGeneration] = useState(false);
  const router = useRouter();

  useEffect(() => {
    // Check if user has already used their free generation
    const sessionId = localStorage.getItem('dilla_session_id');
    if (!sessionId) {
      // Create new session ID
      const newSessionId = crypto.randomUUID();
      localStorage.setItem('dilla_session_id', newSessionId);
    } else {
      // Check if free generation was used
      const freeUsed = localStorage.getItem('dilla_free_used');
      if (freeUsed === 'true') {
        setHasUsedFreeGeneration(true);
      }
    }
  }, []);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;

    // Check if free generation already used
    if (hasUsedFreeGeneration) {
      setShowPaywall(true);
      return;
    }

    setLoading(true);
    try {
      const sessionId = localStorage.getItem('dilla_session_id');
      
      const response = await fetch('/api/agent/free-generation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          sessionId,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setResult(data.result);
        
        // Mark free generation as used
        localStorage.setItem('dilla_free_used', 'true');
        setHasUsedFreeGeneration(true);
        
        // Show paywall after 2 seconds to let user read result
        setTimeout(() => {
          setShowPaywall(true);
        }, 2000);
      } else if (response.status === 429) {
        // Already used free generation
        setShowPaywall(true);
      }
    } catch (error) {
      console.error('Generation failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      {/* Hero Section */}
      <div className="max-w-4xl mx-auto px-6 pt-20 pb-12">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center p-3 bg-indigo-100 rounded-2xl mb-6">
            <Brain className="w-10 h-10 text-indigo-600" />
          </div>
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            VC Intelligence, <span className="text-indigo-600">Instantly</span>
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Analyze companies, generate investment memos, and make data-driven decisions with AI
          </p>
        </div>

        {/* Main Input Section */}
        <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What would you like to analyze?
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="e.g., 'Analyze @Stripe's business model and competitive advantages' or 'Compare @Ramp vs @Brex for Series B investment'"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
              rows={3}
              disabled={loading}
            />
          </div>
          
          <button
            onClick={handleGenerate}
            disabled={loading || !prompt.trim()}
            className="w-full py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 mr-2" />
                Generate Analysis {!hasUsedFreeGeneration && '(1 Free)'}
              </>
            )}
          </button>
          
          {!hasUsedFreeGeneration && (
            <p className="text-center text-sm text-gray-500 mt-3">
              Try it free - no signup required for your first analysis
            </p>
          )}
        </div>

        {/* Result Section */}
        {result && (
          <div className="bg-white rounded-2xl shadow-xl p-8 mb-8 animate-fadeIn">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Zap className="w-5 h-5 mr-2 text-yellow-500" />
              Analysis Result
            </h3>
            <div className="prose prose-gray max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-gray-700">{result}</pre>
            </div>
          </div>
        )}

        {/* Features Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
          <FeatureCard
            icon={<Brain className="w-6 h-6 text-indigo-600" />}
            title="Deep Analysis"
            description="Institutional-grade research with financial metrics, market sizing, and competitive moats"
          />
          <FeatureCard
            icon={<TrendingUp className="w-6 h-6 text-green-600" />}
            title="Real-Time Data"
            description="Live market data, funding rounds, and company metrics updated continuously"
          />
          <FeatureCard
            icon={<Sparkles className="w-6 h-6 text-purple-600" />}
            title="Multiple Models"
            description="Access GPT-4, Claude 3.5, and specialized models based on your plan"
          />
        </div>
      </div>

      {/* Paywall Modal */}
      <PaywallModal
        isOpen={showPaywall}
        onClose={() => setShowPaywall(false)}
        prompt={prompt}
        result={result}
      />
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      <div className="mb-3">{icon}</div>
      <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600">{description}</p>
    </div>
  );
}