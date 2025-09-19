'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
// import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';
import { 
  Send, 
  Bot, 
  User, 
  Sparkles,
  Search,
  TrendingUp,
  BarChart3,
  Calculator,
  FileSearch,
  Activity,
  Loader2,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Zap,
  Target,
  DollarSign,
  GitBranch,
  Globe
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import AgentFeedback from './AgentFeedback';
import dynamic from 'next/dynamic';
import { MCPBackendConnector } from '@/lib/mcp-backend-connector';

// Dynamically import TableauLevelCharts to avoid SSR issues
const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { 
  ssr: false,
  loading: () => <div className="h-64 bg-gray-50 animate-pulse rounded-lg" />
});

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolsUsed?: string[];
  confidence?: number;
  processing?: boolean;
  charts?: Array<{
    type: string;
    title?: string;
    data: any;
  }>;
  analysisData?: any;
}

interface AgentChatProps {
  sessionId?: string;
  onMessageSent?: (message: string) => void;
}

const TOOL_ICONS: Record<string, React.ElementType> = {
  'web_search': Search,
  'discover_new_companies': Globe,
  'screen_investment_opportunity': FileSearch,
  'monitor_transactions': Activity,
  'track_exit_activity': GitBranch,
  'search_companies': Search,
  'calculate_expected_return': Calculator,
  'calculate_public_comps_valuation': BarChart3,
  'analyze_market_comparables': TrendingUp,
  'calculate_hype_vs_value': Zap,
  'run_pwerm_analysis': Target,
  'get_portfolio_metrics': DollarSign,
  'predict_exit_timing': Activity,
};

const SUGGESTED_PROMPTS = [
  { icon: Globe, text: "Find new AI companies that raised funding this week", category: "Discovery" },
  { icon: Calculator, text: "Calculate expected return for a $100M SaaS company with $10M ARR", category: "Valuation" },
  { icon: Zap, text: "Is Anthropic overhyped at $18B valuation?", category: "Analysis" },
  { icon: Activity, text: "Monitor recent acquisitions in fintech", category: "Transactions" },
  { icon: Target, text: "Screen OpenAI competitors for investment", category: "Screening" },
  { icon: GitBranch, text: "Track AI sector exit multiples", category: "Exits" },
];

export default function AgentChat({ sessionId = 'default', onMessageSent }: AgentChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Extract company name from message content
  const extractCompanyFromMessage = (content: string): string | undefined => {
    // Look for company names in common patterns
    const patterns = [
      /(?:for|about|analyzing|CIM for|profile of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/,
      /^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:is|has|was)/,
      /company:\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/i
    ];
    
    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }
    
    return undefined;
  };
  
  // Determine the type of response for RL feedback
  const determineResponseType = (message: Message): string => {
    const content = message.content.toLowerCase();
    const tools = message.toolsUsed || [];
    
    if (tools.includes('generate_company_cim') || content.includes('cim')) {
      return 'CIM';
    }
    if (tools.includes('calculate_expected_return') || content.includes('return')) {
      return 'Valuation';
    }
    if (tools.includes('web_search') || content.includes('search')) {
      return 'Search';
    }
    if (content.includes('market') || content.includes('competitive')) {
      return 'Market Analysis';
    }
    if (content.includes('financial') || content.includes('revenue')) {
      return 'Financial Analysis';
    }
    
    return 'General';
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    onMessageSent?.(input);

    // Add a placeholder assistant message
    const placeholderId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: placeholderId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      processing: true,
    }]);

    try {
      // Use MCP Backend Connector for unified orchestration
      const mcpConnector = MCPBackendConnector.getInstance();
      
      const data = await mcpConnector.processPrompt(
        input,
        {
          sessionId,
          messageHistory: messages.slice(-5), // Last 5 messages for context
          company: input.match(/@(\w+)/)?.[1], // Extract company if @mentioned
        },
        {
          outputFormat: 'analysis',
          stream: false,
          useCache: false
        }
      );

      if (!data.success && data.error) {
        throw new Error(data.error || 'Failed to process request');
      }

      // Extract content from MCP response
      const content = data.analysis || data.synthesis || '';
      const toolsUsed = data.tool_calls?.map((tc: any) => tc.tool) || data.metadata?.tools_used || [];
      
      // Charts come from the results array if they were generated
      const charts = data.results?.find((r: any) => r.skill === 'chart-generator')?.data?.charts || [];

      // Update the placeholder message with the actual response
      setMessages(prev => prev.map(msg => 
        msg.id === placeholderId 
          ? {
              ...msg,
              content,
              toolsUsed,
              charts,
              analysisData: data.results || data,
              processing: false,
            }
          : msg
      ));
    } catch (error) {
      console.error('Error sending message:', error);
      // Update placeholder with error message
      setMessages(prev => prev.map(msg => 
        msg.id === placeholderId 
          ? {
              ...msg,
              content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`,
              processing: false,
            }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePromptClick = (prompt: string) => {
    setInput(prompt);
    textareaRef.current?.focus();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)] max-w-6xl mx-auto">
      {/* Chat Messages */}
      <Card className="flex-1 mb-4 overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
        <ScrollArea className="h-full p-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full space-y-6">
              <div className="relative">
                <div className="absolute inset-0 bg-gray-500 blur-3xl opacity-20 animate-pulse" />
                <Bot className="h-20 w-20 text-gray-600 relative z-10" />
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-2xl font-bold bg-gradient-to-r from-gray-700 to-gray-900 bg-clip-text text-transparent">
                  Agent City AI Assistant
                </h3>
                <p className="text-gray-600 dark:text-gray-400 max-w-md">
                  Your quantitative investment strategist powered by 14 specialized tools
                </p>
              </div>
              
              {/* Suggested Prompts */}
              <div className="grid grid-cols-2 gap-3 max-w-2xl mt-8">
                {SUGGESTED_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handlePromptClick(prompt.text)}
                    className="group relative overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 p-4 text-left transition-all hover:shadow-lg hover:scale-[1.02] bg-white dark:bg-gray-900"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-gray-500/10 to-gray-600/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="relative z-10">
                      <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-gradient-to-r from-gray-500/20 to-gray-600/20">
                          <prompt.icon className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                        </div>
                        <Badge variant="secondary" className="text-xs">
                          {prompt.category}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                        {prompt.text}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  {message.role === 'assistant' && (
                    <div className="h-8 w-8 border-2 border-gray-500/20 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center">
                      <Bot className="h-5 w-5 text-white" />
                    </div>
                  )}
                  
                  <div
                    className={`group relative max-w-[80%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-gradient-to-r from-gray-600 to-gray-700 text-white'
                        : 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800'
                    }`}
                  >
                    {message.processing ? (
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Analyzing...</span>
                      </div>
                    ) : (
                      <>
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <ReactMarkdown
                            components={{
                              code({ node, className, children, ...props }: any) {
                                const inline = node?.position === undefined;
                                const match = /language-(\w+)/.exec(className || '');
                                return !inline && match ? (
                                  <SyntaxHighlighter
                                    style={atomDark}
                                    language={match[1]}
                                    PreTag="div"
                                    {...props}
                                  >
                                    {String(children).replace(/\n$/, '')}
                                  </SyntaxHighlighter>
                                ) : (
                                  <code className={className} {...props}>
                                    {children}
                                  </code>
                                );
                              },
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>
                        
                        {/* Render charts if available */}
                        {message.charts && message.charts.length > 0 && (
                          <div className="mt-4 space-y-4">
                            {message.charts.map((chart, idx) => (
                              <div key={idx} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                                <TableauLevelCharts
                                  type={chart.type as any}
                                  data={chart.data}
                                  title={chart.title}
                                  interactive={true}
                                  height={400}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Tools Used */}
                        {message.toolsUsed && message.toolsUsed.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                            {message.toolsUsed.map((tool, idx) => {
                              const Icon = TOOL_ICONS[tool] || Sparkles;
                              return (
                                <Badge
                                  key={idx}
                                  variant="secondary"
                                  className="text-xs flex items-center gap-1"
                                >
                                  <Icon className="h-3 w-3" />
                                  {tool.replace(/_/g, ' ')}
                                </Badge>
                              );
                            })}
                          </div>
                        )}
                        
                        {/* RL Feedback Component */}
                        {console.log('Checking feedback render:', {
                          role: message.role,
                          processing: message.processing,
                          shouldShow: message.role === 'assistant' && !message.processing
                        })}
                        {message.role === 'assistant' && !message.processing && (
                          <AgentFeedback
                            sessionId={sessionId}
                            messageId={message.id}
                            company={extractCompanyFromMessage(message.content)}
                            responseType={determineResponseType(message)}
                            onFeedback={(feedback) => {
                              console.log('Feedback submitted:', feedback);
                            }}
                          />
                        )}
                        
                        {/* Message Actions */}
                        {message.role === 'assistant' && !message.processing && (
                          <div className="absolute -bottom-8 right-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-800 p-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 w-7 p-0"
                              onClick={() => copyToClipboard(message.content)}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  
                  {message.role === 'user' && (
                    <div className="h-8 w-8 border-2 border-gray-500/20 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center">
                      <User className="h-5 w-5 text-white" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>
      </Card>

      {/* Input Area */}
      <Card className="p-4 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm border-gray-200 dark:border-gray-800">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Ask about investments, valuations, or market analysis..."
              className="min-h-[60px] max-h-[200px] resize-none pr-12 bg-white dark:bg-gray-900"
              disabled={isLoading}
            />
            <div className="absolute bottom-2 right-2 text-xs text-gray-400">
              {input.length > 0 && `${input.length} chars`}
            </div>
          </div>
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="h-Array.from(x) px-6 bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>
        
        {/* Tool Capabilities Bar */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
          <span className="text-xs text-gray-500">Capabilities:</span>
          <div className="flex flex-wrap gap-2">
            {['Discovery', 'Valuation', 'Analysis', 'Monitoring', 'Portfolio'].map((cap) => (
              <Badge key={cap} variant="outline" className="text-xs">
                {cap}
              </Badge>
            ))}
          </div>
          <div className="ml-auto text-xs text-gray-500">
            14 tools • Powered by Claude
          </div>
        </div>
      </Card>
    </div>
  );
}