'use client';

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Send, 
  Loader2, 
  Brain, 
  Search, 
  FileText, 
  Shield, 
  TrendingUp,
  Users,
  BarChart3,
  AlertCircle,
  Sparkles,
  Bot
} from 'lucide-react';

// Agent modes with icons
const AGENT_MODES = [
  { id: 'quick_chat', name: 'Quick Chat', icon: Bot, color: 'blue' },
  { id: 'market_research', name: 'Market Research', icon: Search, color: 'purple' },
  { id: 'financial_analysis', name: 'Financial Analysis', icon: TrendingUp, color: 'green' },
  { id: 'pwerm_analysis', name: 'PWERM Analysis', icon: BarChart3, color: 'orange' },
  { id: 'compliance_kyc', name: 'KYC & Compliance', icon: Shield, color: 'red' },
  { id: 'document_analysis', name: 'Document Analysis', icon: FileText, color: 'indigo' },
  { id: 'multi_agent', name: 'Full Multi-Agent', icon: Users, color: 'pink' }
];

// Sample queries for each mode
const SAMPLE_QUERIES = {
  quick_chat: "What's a good SaaS valuation multiple for Series B?",
  market_research: "Research the payments infrastructure market and key players",
  financial_analysis: "Analyze unit economics for a B2B SaaS with $10M ARR growing 150% YoY",
  pwerm_analysis: "Run PWERM analysis for Stripe",
  compliance_kyc: "Run KYC check on Sequoia Capital",
  document_analysis: "Analyze the pitch deck for key metrics",
  multi_agent: "Complete analysis of Anthropic as an investment opportunity"
};

export default function AgentTestPage() {
  const [query, setQuery] = useState('');
  const [selectedMode, setSelectedMode] = useState('auto');
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const [currentResponse, setCurrentResponse] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSubmit = async () => {
    if (!query.trim() || isStreaming) return;
    
    const userMessage = {
      role: 'user',
      content: query,
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setQuery('');
    setIsStreaming(true);
    setStreamingContent('');
    setCurrentResponse('');
    
    try {
      // Call streaming endpoint
      const response = await fetch('/api/agent/orchestrator/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          mode: selectedMode === 'auto' ? null : selectedMode,
          stream: true
        })
      });
      
      if (!response.ok) throw new Error('Failed to connect to agent');
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      let fullResponse = '';
      let currentMode = '';
      
      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'status':
                  setStreamingContent(prev => prev + `\n**${data.message}**\n\n`);
                  currentMode = data.mode;
                  break;
                  
                case 'progress':
                  setStreamingContent(prev => prev + `${data.message}\n`);
                  break;
                  
                case 'agent':
                  setStreamingContent(prev => prev + `\n${data.message}\n`);
                  break;
                  
                case 'partial':
                  setStreamingContent(prev => prev + data.content);
                  break;
                  
                case 'token':
                  fullResponse += data.content;
                  setCurrentResponse(fullResponse);
                  break;
                  
                case 'result':
                  fullResponse = data.content;
                  setCurrentResponse(fullResponse);
                  break;
                  
                case 'complete':
                  // Finalize the message
                  const agentMessage = {
                    role: 'assistant',
                    content: fullResponse || streamingContent,
                    mode: currentMode,
                    timestamp: new Date().toISOString()
                  };
                  setMessages(prev => [...prev, agentMessage]);
                  setStreamingContent('');
                  setCurrentResponse('');
                  break;
                  
                case 'error':
                  setStreamingContent(prev => prev + `\n❌ Error: ${data.message}\n`);
                  break;
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Agent error:', error);
      setStreamingContent(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSampleQuery = (mode: string) => {
    const sampleQuery = SAMPLE_QUERIES[mode as keyof typeof SAMPLE_QUERIES];
    if (sampleQuery) {
      setQuery(sampleQuery);
      setSelectedMode(mode);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">AI Agent Testing Platform</h1>
        <p className="text-muted-foreground">
          Multi-mode intelligent agent with streaming responses
        </p>
      </div>

      {/* Mode Selection */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Select Agent Mode</CardTitle>
          <CardDescription>
            Choose a specific mode or let the agent auto-select based on your query
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Button
              variant={selectedMode === 'auto' ? 'default' : 'outline'}
              onClick={() => setSelectedMode('auto')}
              className="justify-start"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Auto-Select
            </Button>
            {AGENT_MODES.map(mode => {
              const Icon = mode.icon;
              return (
                <Button
                  key={mode.id}
                  variant={selectedMode === mode.id ? 'default' : 'outline'}
                  onClick={() => setSelectedMode(mode.id)}
                  className="justify-start"
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {mode.name}
                </Button>
              );
            })}
          </div>

          {/* Sample Queries */}
          {selectedMode !== 'auto' && SAMPLE_QUERIES[selectedMode as keyof typeof SAMPLE_QUERIES] && (
            <Alert className="mt-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <span className="font-medium">Sample query:</span>{' '}
                <Button
                  variant="link"
                  className="p-0 h-auto font-normal"
                  onClick={() => handleSampleQuery(selectedMode)}
                >
                  {SAMPLE_QUERIES[selectedMode as keyof typeof SAMPLE_QUERIES]}
                </Button>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Chat Interface */}
      <Card className="h-[600px] flex flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            Agent Console
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto mb-4 p-4 border rounded-lg bg-muted/10">
            {messages.length === 0 && !streamingContent && (
              <div className="text-center text-muted-foreground py-8">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Start a conversation with the agent</p>
                <p className="text-sm mt-2">
                  Try different modes to see specialized capabilities
                </p>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}
              >
                <div
                  className={`inline-block max-w-[80%] p-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  }`}
                >
                  {msg.mode && (
                    <Badge className="mb-2" variant="secondary">
                      {msg.mode}
                    </Badge>
                  )}
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  <div className="text-xs opacity-70 mt-1">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            
            {/* Streaming Content */}
            {(streamingContent || currentResponse) && (
              <div className="mb-4">
                <div className="inline-block max-w-[80%] p-3 rounded-lg bg-muted">
                  <div className="whitespace-pre-wrap">
                    {currentResponse || streamingContent}
                    {isStreaming && <span className="animate-pulse">▊</span>}
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="Ask anything... (KYC checks, market research, PWERM analysis, etc.)"
              disabled={isStreaming}
              className="flex-1"
            />
            <Button
              onClick={handleSubmit}
              disabled={!query.trim() || isStreaming}
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Mode Descriptions */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Available Modes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div><Badge>Quick Chat</Badge> - Fast Q&A responses</div>
            <div><Badge>Market Research</Badge> - Deep market analysis with Tavily</div>
            <div><Badge>Financial Analysis</Badge> - Metrics and unit economics</div>
            <div><Badge>PWERM</Badge> - Full probability-weighted valuation</div>
            <div><Badge>KYC</Badge> - Compliance and beneficial ownership checks</div>
            <div><Badge>Multi-Agent</Badge> - CrewAI comprehensive analysis</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Streaming Features</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>✨ Real-time text generation</div>
            <div>📊 Progress updates for long operations</div>
            <div>🤖 Multi-agent collaboration visibility</div>
            <div>⚡ Instant feedback and status updates</div>
            <div>🎯 Mode auto-selection based on query</div>
            <div>🔄 Parallel tool execution</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}