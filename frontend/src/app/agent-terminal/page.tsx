'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ReactMarkdown from 'react-markdown';
import { 
  Terminal,
  Send,
  Copy,
  Download,
  FileText,
  Code,
  Hash,
  Brain,
  Zap,
  Search,
  Database,
  TrendingUp,
  Globe,
  ChevronRight,
  Command
} from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  format: 'markdown' | 'html' | 'text' | 'code';
  timestamp: Date;
  tools?: string[];
}

export default function AgentTerminalPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'system',
      content: `# Agent City Terminal v2.0
      
## Welcome, Quant. I am your alpha-seeking assistant.

I operate in **markdown**, **HTML**, and **raw text** - whatever helps us find alpha fastest.

### My Capabilities:
- 🔍 **Market Analysis**: Deep dive into any market, submarket, or niche
- 📊 **Portfolio Optimization**: Kelly Criterion, Sharpe ratios, correlation matrices
- 🎯 **Deal Sourcing**: Find companies before they're hot
- 💹 **Public Markets**: Yahoo Finance integration for liquid opportunities
- 🧮 **Quantitative Models**: PWERM, Monte Carlo, mean reversion
- 🌍 **Global Taxonomy**: Analyze $100T global GDP across all sectors

### Quick Commands:
- \`analyze [market]\` - Deep market analysis with subcategories
- \`find alpha\` - Discover undervalued opportunities
- \`portfolio optimize\` - Rebalance for maximum Sharpe
- \`hype check [company]\` - Detect overvaluation
- \`public [ticker]\` - Analyze public market position

### Output Formats:
- **Markdown**: Structured analysis with headers and lists
- **HTML**: Rich formatting with tables and styling
- **Text**: Raw data for processing
- **Code**: Python/SQL for further analysis

Ready to generate alpha. What's our target?`,
      format: 'markdown',
      timestamp: new Date()
    }
  ]);
  
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [outputFormat, setOutputFormat] = useState<'markdown' | 'html' | 'text' | 'code'>('markdown');
  const [showTools, setShowTools] = useState(true);
  const [showDebug, setShowDebug] = useState(false);
  const [sessionId] = useState(`session-${Date.now()}`);
  const [aum, setAum] = useState(300); // £300 starting AUM
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      format: 'text',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      const response = await fetch('/api/agent/claude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `Please respond in ${outputFormat} format. ${input}`,
          history: messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp,
            tools: m.tools
          })),
          sessionId,
          aum
        })
      });

      const data = await response.json();

      // If tools were used, add a system message showing what tools were called
      if (data.toolsUsed && data.toolsUsed.length > 0) {
        const toolMessage: Message = {
          id: Date.now().toString() + '-tools',
          role: 'system',
          content: `🔧 Tools Used: ${data.toolsUsed.join(', ')}`,
          format: 'text',
          timestamp: new Date(),
          tools: data.toolsUsed
        };
        setMessages(prev => [...prev, toolMessage]);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response || data.error || 'No response',
        format: outputFormat,
        timestamp: new Date(),
        tools: data.toolsUsed
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Error processing request. Please try again.',
        format: 'text',
        timestamp: new Date()
      }]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleQuickCommand = (command: string) => {
    setInput(command);
    inputRef.current?.focus();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const downloadContent = (content: string, format: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-output-${Date.now()}.${format}`;
    a.click();
  };

  const renderMessage = (message: Message) => {
    switch (message.format) {
      case 'markdown':
        return (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        );
      case 'html':
        return (
          <div 
            className="rendered-html"
            dangerouslySetInnerHTML={{ __html: message.content }}
          />
        );
      case 'code':
        return (
          <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto">
            <code>{message.content}</code>
          </pre>
        );
      default:
        return (
          <pre className="whitespace-pre-wrap font-mono text-sm">{message.content}</pre>
        );
    }
  };

  return (
    <div className="min-h-screen bg-black text-green-400 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6 border-b border-green-800 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Terminal className="h-8 w-8" />
              <div>
                <h1 className="text-2xl font-bold text-green-400">Agent Terminal</h1>
                <p className="text-green-600 text-sm">Quantitative Alpha Generation System</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-green-600">Output:</span>
                <select 
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value as any)}
                  className="bg-gray-900 text-green-400 px-2 py-1 rounded border border-green-800"
                >
                  <option value="markdown">Markdown</option>
                  <option value="html">HTML</option>
                  <option value="text">Text</option>
                  <option value="code">Code</option>
                </select>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowTools(!showTools)}
                className="bg-gray-900 text-green-400 border-green-800 hover:bg-gray-800"
              >
                <Command className="h-4 w-4 mr-2" />
                {showTools ? 'Hide' : 'Show'} Tools
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* Tools Panel */}
          {showTools && (
            <div className="col-span-3">
              <Card className="bg-gray-900 border-green-800">
                <div className="p-4">
                  <h3 className="text-green-400 font-semibold mb-3">Quick Commands</h3>
                  <div className="space-y-2">
                    <button
                      onClick={() => handleQuickCommand('analyze AI market with all subcategories')}
                      className="w-full text-left p-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-green-400"
                    >
                      <Search className="inline h-3 w-3 mr-2" />
                      Analyze AI Market
                    </button>
                    <button
                      onClick={() => handleQuickCommand('find alpha opportunities in undervalued sectors')}
                      className="w-full text-left p-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-green-400"
                    >
                      <TrendingUp className="inline h-3 w-3 mr-2" />
                      Find Alpha
                    </button>
                    <button
                      onClick={() => handleQuickCommand('optimize portfolio using Kelly Criterion')}
                      className="w-full text-left p-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-green-400"
                    >
                      <Database className="inline h-3 w-3 mr-2" />
                      Optimize Portfolio
                    </button>
                    <button
                      onClick={() => handleQuickCommand('analyze public market NVDA')}
                      className="w-full text-left p-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-green-400"
                    >
                      <Globe className="inline h-3 w-3 mr-2" />
                      Check NVDA
                    </button>
                    <button
                      onClick={() => handleQuickCommand('source deals in AI infrastructure')}
                      className="w-full text-left p-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-green-400"
                    >
                      <Zap className="inline h-3 w-3 mr-2" />
                      Source AI Deals
                    </button>
                  </div>

                  <h3 className="text-green-400 font-semibold mt-6 mb-3">Active Tools</h3>
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2 text-green-600">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      web_search
                    </div>
                    <div className="flex items-center gap-2 text-green-600">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      analyze_public_market
                    </div>
                    <div className="flex items-center gap-2 text-green-600">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      find_market_subcategories
                    </div>
                    <div className="flex items-center gap-2 text-green-600">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      calculate_expected_return
                    </div>
                  </div>

                  <h3 className="text-green-400 font-semibold mt-6 mb-3">Fund Status</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-green-600">Current AUM</span>
                      <span className="text-green-400 font-bold">£{aum}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-600">Target AUM</span>
                      <span className="text-green-400">£100K</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-600">Required IRR</span>
                      <span className="text-green-400">300%+</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-600">Session ID</span>
                      <span className="text-green-400 text-[8px]">{sessionId.slice(-8)}</span>
                    </div>
                  </div>

                  <h3 className="text-green-400 font-semibold mt-6 mb-3">Market Stats</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-green-600">Global GDP</span>
                      <span className="text-green-400">$100T</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-600">AI TAM</span>
                      <span className="text-green-400">$1.5T</span>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Main Terminal */}
          <div className={showTools ? 'col-span-9' : 'col-span-12'}>
            <Card className="bg-gray-900 border-green-800 h-[calc(100vh-200px)]">
              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-4 h-[calc(100%-120px)]">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`mb-4 ${
                      message.role === 'user' ? 'text-blue-400' : 
                      message.role === 'system' ? 'text-yellow-400' : 'text-green-400'
                    }`}
                  >
                    <div className="flex items-start gap-2 mb-1">
                      <span className="font-mono text-xs opacity-60">
                        [{message.timestamp.toLocaleTimeString()}]
                      </span>
                      <span className="font-bold">
                        {message.role === 'user' ? '>' : 
                         message.role === 'system' ? '$' : '#'}
                      </span>
                      {message.role === 'assistant' && message.tools && (
                        <div className="flex gap-1">
                          {message.tools.map(tool => (
                            <span key={tool} className="text-xs bg-gray-800 px-1 rounded">
                              {tool}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="pl-8">
                      {renderMessage(message)}
                      {message.role === 'assistant' && (
                        <div className="flex gap-2 mt-2">
                          <button
                            onClick={() => copyToClipboard(message.content)}
                            className="text-xs text-green-600 hover:text-green-400"
                          >
                            <Copy className="inline h-3 w-3 mr-1" />
                            Copy
                          </button>
                          <button
                            onClick={() => downloadContent(message.content, message.format)}
                            className="text-xs text-green-600 hover:text-green-400"
                          >
                            <Download className="inline h-3 w-3 mr-1" />
                            Download
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <form onSubmit={handleSubmit} className="border-t border-green-800 p-4">
                <div className="flex gap-2">
                  <span className="text-green-400 mt-2">{'>'}</span>
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit(e);
                      }
                    }}
                    placeholder="Enter command or question... (Shift+Enter for new line)"
                    className="flex-1 bg-transparent text-green-400 placeholder-green-800 outline-none resize-none"
                    rows={2}
                    disabled={isProcessing}
                  />
                  <Button
                    type="submit"
                    disabled={isProcessing || !input.trim()}
                    className="bg-green-800 hover:bg-green-700 text-black"
                  >
                    {isProcessing ? (
                      <Brain className="h-4 w-4 animate-pulse" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </form>
            </Card>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .prose pre {
          background-color: #111827;
          color: #10b981;
        }
        .prose code {
          color: #10b981;
        }
        .rendered-html table {
          width: 100%;
          border-collapse: collapse;
        }
        .rendered-html th,
        .rendered-html td {
          border: 1px solid #064e3b;
          padding: 8px;
        }
        .rendered-html th {
          background-color: #064e3b;
        }
      `}</style>
    </div>
  );
}