'use client';

import React, { useState, useRef, useEffect } from 'react';
import AgentProgressTracker from '@/components/AgentProgressTracker';
import CitationDisplay from '@/components/CitationDisplay';
import AgentChartGenerator from '@/components/AgentChartGenerator';
import { 
  Presentation, 
  Send,
  Download,
  Eye,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Layout,
  BarChart3,
  Users,
  Target,
  TrendingUp,
  DollarSign,
  Edit2,
  ThumbsUp,
  ThumbsDown,
  Star,
  MessageSquare,
  Brain
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';
import TableauLevelCharts from '@/components/charts/TableauLevelCharts';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  status?: 'pending' | 'complete' | 'error';
  deck?: GeneratedDeck;
}

interface Citation {
  text: string;
  source: string;
  url?: string;
}

interface SlideContent {
  title: string;
  subtitle?: string;
  body?: string;
  bullets?: string[];
  chart_data?: any;
  metrics?: Record<string, any>;
  notes?: string;
  citations?: Citation[];
  devices?: any[]; // Visual devices like timelines, matrices, textboxes, etc.
}

interface Slide {
  id: string;
  order: number;
  template: string;
  content: SlideContent;
  layout?: any;
  theme?: {
    background?: string;
    titleColor?: string;
    textColor?: string;
    accentColor?: string;
  };
}

interface DataSource {
  name: string;
  url?: string;
  date?: string;
}

interface GeneratedDeck {
  id: string;
  title: string;
  type: string;
  slides: Slide[];
  theme?: any;
  data_sources?: DataSource[];
  citations?: any[];
  charts?: any[];
}

interface DeckTemplate {
  id: string;
  name: string;
  description: string;
  slides: number;
  icon: React.ReactNode;
  color: string;
}

export default function DeckAgentPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Welcome to Deck Agent! I can help you create professional presentations, pitch decks, and investor materials. What kind of deck would you like to create today?',
      timestamp: new Date(),
      status: 'complete'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [currentDeck, setCurrentDeck] = useState<GeneratedDeck | null>(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [isEditingSlide, setIsEditingSlide] = useState(false);
  const [citations, setCitations] = useState<any[]>([]);
  const [charts, setCharts] = useState<any[]>([]);
  const [showCharts, setShowCharts] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | undefined>();
  const [editedContent, setEditedContent] = useState<SlideContent | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [executionSteps, setExecutionSteps] = useState<string[]>([]);
  const [userFeedback, setUserFeedback] = useState<{ rating: number; comment: string }>({ rating: 0, comment: '' });
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  
  // RL Feedback states
  const [useRL, setUseRL] = useState(true);
  const [semanticFeedback, setSemanticFeedback] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [sessionId] = useState<string>(() => `deck-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const templates: DeckTemplate[] = [
    {
      id: 'pitch',
      name: 'Pitch Deck',
      description: 'Perfect for startup fundraising',
      slides: 12,
      icon: <Target className="w-5 h-5" />,
      color: 'bg-purple-100 text-purple-600'
    },
    {
      id: 'investor',
      name: 'Investor Update',
      description: 'Monthly/quarterly investor reports',
      slides: 8,
      icon: <TrendingUp className="w-5 h-5" />,
      color: 'bg-blue-100 text-blue-600'
    },
    {
      id: 'sales',
      name: 'Sales Deck',
      description: 'Product demos and sales pitches',
      slides: 10,
      icon: <DollarSign className="w-5 h-5" />,
      color: 'bg-green-100 text-green-600'
    },
    {
      id: 'board',
      name: 'Board Meeting',
      description: 'Board presentations and updates',
      slides: 15,
      icon: <Users className="w-5 h-5" />,
      color: 'bg-orange-100 text-orange-600'
    },
    {
      id: 'cim',
      name: 'CIM Document',
      description: 'Confidential Information Memorandum',
      slides: 20,
      icon: <Layout className="w-5 h-5" />,
      color: 'bg-indigo-100 text-indigo-600'
    }
  ];

  const quickPrompts = [
    "Create a Series A pitch deck for a SaaS company",
    "Generate investor update for Q4 2024",
    "Build a product demo deck for enterprise clients",
    "Create a board presentation with financial metrics",
    "Generate a CIM for acquisition discussions",
    "Design a fundraising deck with market analysis"
  ];

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // RL Semantic Feedback submission function
  const submitRLFeedback = async (type: string, feedback: string) => {
    console.log('📝 Submitting RL feedback:', type, feedback);
    setFeedbackSent(false);
    
    try {
      const response = await fetch('/api/agent/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          prompt: lastPrompt,
          response: JSON.stringify(currentDeck),
          feedbackType: type,
          feedbackText: feedback,
          score: type === 'good' ? 1.0 : type === 'bad' ? -1.0 : type === 'edit' ? 0.5 : 0.0,
          modelType: 'deck-agent',
          timestamp: new Date().toISOString()
        })
      });
      
      if (response.ok) {
        setFeedbackSent(true);
        setTimeout(() => setFeedbackSent(false), 3000);
        
        if (type === 'semantic') {
          setSemanticFeedback('');
        }
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    console.log('🎯 handleSubmit Called with input:', input);

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
      status: 'complete'
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setIsGenerating(true);
    setGenerationProgress(0);
    setProgressMessage('🔍 Initializing deck generation...');
    setExecutionSteps([]);

    // Simulate deck generation with progress
    const progressInterval = setInterval(() => {
      setGenerationProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 200);

    try {
      // Let the unified brain handle company extraction with semantic analysis
      // No regex needed - it uses DeepRequestAnalyzer with Claude
      
      // Just send the raw prompt - unified brain will extract companies semantically
      const deckPrompt = input;
      
      // Call the unified brain STREAMING API for better UX
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: deckPrompt,
          outputFormat: 'deck',
          specificInstructions: `
            CRITICAL: Create a COMPLETE professional ${selectedTemplate || 'pitch'} deck with NO empty slides.
            
            MANDATORY for EVERY slide:
            1. Fill in REAL metrics with actual numbers (not placeholders)
            2. Include 3-5 detailed bullet points minimum
            3. Add relevant chart_data with proper structure
            4. Include citations from real sources
            5. Ensure all content fields are populated
            
            Required slides (ALL must have content):
            - Title: Company name, tagline, funding stage, key metrics
            - Problem: Quantify market pain with real statistics
            - Solution: Clear value prop with differentiation matrix
            - Market: TAM/SAM/SOM with sources, growth rates
            - Traction: Real ARR, growth %, customer count, NRR
            - Business Model: Unit economics, CAC, LTV, margins
            - Competition: Positioning matrix with 5+ competitors
            - Team: Backgrounds, credentials, past exits
            - Financials: Revenue projections, burn rate, runway
            - Ask: Specific amount, use of funds, milestones
            
            For charts, use proper format:
            {
              type: 'bar' | 'line' | 'pie',
              data: {
                labels: ['Q1', 'Q2', 'Q3', 'Q4'],
                datasets: [{
                  data: [10, 20, 30, 40],
                  label: 'Revenue ($M)'
                }]
              }
            }
            
            IMPORTANT: Extract and use REAL company data from searches.
            DO NOT use generic examples or sample data.
          `,
          context: {
            deckType: selectedTemplate || 'pitch',
            requirements: input,
            enforceComplete: true,
            requireRealData: true
          }
        })
      });

      if (!response.ok) throw new Error('Failed to get agent response');

      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let deck: GeneratedDeck | null = null;

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const data = JSON.parse(dataStr);
              
              switch (data.type) {
                case 'skill_chain':
                  // Show skill chain in the stream
                  setExecutionSteps(prev => [...prev, `📋 Decomposed into ${data.total_count} skills:`]);
                  data.skills?.forEach((skill: any, i: number) => {
                    setExecutionSteps(prev => [...prev, `  ${i+1}. ${skill.name}: ${skill.purpose}`]);
                  });
                  // Also log to console
                  console.log('📋 [Skill Chain] Decomposed into', data.total_count, 'skills:');
                  data.skills?.forEach((skill: any, i: number) => {
                    console.log(`  ${i+1}. ${skill.name}: ${skill.purpose} (Group ${skill.group})`);
                  });
                  break;
                  
                case 'skill_start':
                  // Show skill start in the stream
                  setExecutionSteps(prev => [...prev, `⏳ [${data.phase}] ${data.skill}`]);
                  console.log(`⏳ [${data.phase}] Starting: ${data.skill} - ${data.purpose}`);
                  break;
                  
                case 'skill_complete':
                  // Show skill completion in the stream
                  const timing = data.timing ? ` (${data.timing.toFixed(2)}s)` : '';
                  setExecutionSteps(prev => [...prev, `✅ ${data.skill}${timing}`]);
                  console.log(`✅ [Skill Complete] ${data.skill}${timing}`);
                  break;
                  
                case 'skill_error':
                  // Show skill error in the stream
                  setExecutionSteps(prev => [...prev, `❌ ${data.skill}: ${data.error}`]);
                  console.error(`❌ [Skill Error] ${data.skill}: ${data.error}`);
                  break;
                  
                case 'progress':
                  // Update progress message
                  setProgressMessage(data.message);
                  setExecutionSteps(prev => [...prev, data.message]);
                  setGenerationProgress(Math.min(90, generationProgress + 10));
                  break;
                  
                case 'status':
                  setProgressMessage(data.message);
                  break;
                  
                case 'complete':
                  // Deck is complete - backend returns data.result (singular) with slides at top level
                  console.log('🔍 [Deck Agent] Raw complete data:', data);
                  console.log('🔍 [Deck Agent] data.result structure:', data.result);
                  console.log('🔍 [Deck Agent] data.result.slides:', data.result?.slides);
                  console.log('🔍 [Deck Agent] Slides count:', data.result?.slides?.length || 0);
                  
                  // DEBUG: Log full result to see what we actually get
                  try {
                    console.log('🔴 FULL RESULT OBJECT:', JSON.stringify(data.result, null, 2));
                  } catch (e) {
                    console.log('🔴 RESULT OBJECT (non-stringifiable):', data.result);
                  }
                  
                  // The backend returns the deck data directly in result (singular, not results)
                  // The deck format has slides, theme, citations, charts at the top level of result
                  // Check if result has format: 'deck' structure
                  if (data.result && data.result.format === 'deck') {
                    console.log('✅ [Deck Agent] Found unified format deck structure');
                    deck = {
                      id: `deck-${Date.now()}`,
                      title: data.result.metadata?.title || 'Investment Analysis Deck',
                      type: selectedTemplate || 'pitch',
                      slides: data.result.slides || [],
                      theme: data.result.theme,
                      data_sources: data.result.metadata?.data_sources || [],
                      citations: data.result.citations || [],
                      charts: data.result.charts || []
                    };
                  } else if (data.result && Array.isArray(data.result.slides)) {
                    // Direct slides array in result
                    console.log('✅ [Deck Agent] Found direct slides in result');
                    deck = {
                      id: `deck-${Date.now()}`,
                      title: 'Investment Analysis Deck',
                      type: selectedTemplate || 'pitch',
                      slides: data.result.slides,
                      theme: data.result.theme,
                      data_sources: [],
                      citations: data.result.citations || [],
                      charts: data.result.charts || []
                    };
                  } else {
                    // Fallback - use result as deck
                    console.log('⚠️ [Deck Agent] Using result as deck directly');
                    deck = data.result;
                  }
                  
                  // Extract citations and charts if available
                  if (deck?.citations) {
                    setCitations(deck.citations);
                  }
                  if (deck?.charts) {
                    setCharts(deck.charts);
                  }
                  
                  setGenerationProgress(100);
                  console.log('✅ Deck generation complete with', deck?.slides?.length || 0, 'slides');
                  // Also log the skills that were used from metadata
                  if (data.metadata?.skills_used) {
                    console.log('📊 Skills used:', data.metadata.skills_used);
                  }
                  break;
                  
                case 'error':
                  console.error('❌ Streaming error:', data.message);
                  throw new Error(data.message);
                  
                case 'done':
                  console.log('✨ Stream complete:', data.message);
                  break;
              }
            } catch (e) {
              console.warn('Could not parse streaming data:', e);
            }
          }
        }
      }

      clearInterval(progressInterval);
      setGenerationProgress(100);
      
      if (deck) {
        console.log('✅ [Deck Agent] Using streamed deck data');
        console.log('📊 [Deck Agent] Full deck object:', deck);
        console.log('📊 [Deck Agent] Deck structure:', {
          format: (deck as any).format || 'deck',
          title: deck.title || 'Generated Deck',
          slideCount: deck.slides?.length,
          hasTheme: !!deck.theme,
          hasDataSources: !!(deck as any).data_sources,
          hasCitations: !!(deck as any).citations,
          hasCharts: !!(deck as any).charts
        });
        
        // The backend returns format: 'deck' with slides array
        // We need to wrap it in the expected deck structure
        if (!deck.id) deck.id = `deck-${Date.now()}`;
        if (!deck.type) deck.type = selectedTemplate || 'pitch';
        if (!deck.title) deck.title = 'Investment Analysis Deck';
        
        // Check if we actually have valid slides
        if (!deck.slides || deck.slides.length === 0) {
          console.error('❌ [Deck Agent] No slides in generated deck');
          console.error('📋 [Deck Agent] Deck keys:', Object.keys(deck));
          // Instead of using sample, show an error
          setMessages(prev => [...prev, {
            id: `msg-error-${Date.now()}`,
            role: 'assistant',
            content: `⚠️ The deck generation completed but no slides were created. This might be due to insufficient data. Please try again with more specific company names or prompts.`,
            timestamp: new Date()
          }]);
          setIsGenerating(false);
          return;
        } else {
          console.log(`✅ [Deck Agent] Generated real deck with ${deck.slides.length} slides`);
          // Log first slide for debugging
          if (deck.slides[0]) {
            console.log('🎯 [Deck Agent] First slide preview:', {
              template: deck.slides[0].template,
              title: deck.slides[0].content?.title,
              hasContent: !!deck.slides[0].content
            });
          }
        }
      } else {
        // No deck received - show error instead of template
        console.error('No deck received from streaming');
        setMessages(prev => [...prev, {
          id: `msg-error-${Date.now()}`,
          role: 'assistant',
          content: `❌ Failed to generate deck. Backend returned no data.`,
          timestamp: new Date()
        }]);
        setIsGenerating(false);
        return;
      }

      console.log('🎯 handleSubmit Setting deck:', deck.title, 'with', deck.slides?.length, 'slides');
      setCurrentDeck(deck);
      setCurrentSlideIndex(0);
      setLastPrompt(input);
      setShowFeedback(true); // Show feedback UI after generation
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I've created your ${deck.type} deck with ${deck.slides.length} slides. You can view, edit, and export the presentation using the controls above. Please provide feedback to help improve future generations!`,
        timestamp: new Date(),
        status: 'complete',
        deck: deck
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error calling API:', error);
      // Show error instead of template
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `❌ Error generating deck: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
        status: 'error'
      };
      setMessages(prev => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
    }
  };

  // Template generation function removed - only real data from backend

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
    inputRef.current?.focus();
  };

  const handleTemplateSelect = async (templateId: string) => {
    setSelectedTemplate(templateId);
    const template = templates.find(t => t.id === templateId);
    if (template) {
      const prompt = `Create a ${template.name} with ${template.slides} slides`;
      setInput(prompt);
      
      // Auto-submit the template request
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: prompt,
        timestamp: new Date(),
        status: 'complete'
      };

      setMessages(prev => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);
      setIsGenerating(true);
      setGenerationProgress(0);
      setProgressMessage('🎨 Generating template deck...');
      setExecutionSteps([]);

      // Simulate deck generation with progress
      const progressInterval = setInterval(() => {
        setGenerationProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      try {
        const response = await fetch('/api/agent/unified-brain', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt,
            outputFormat: 'deck'
          })
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        // Handle streaming response
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let templateDeck: GeneratedDeck | null = null;

        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              if (dataStr === '[DONE]') continue;
              
              try {
                const data = JSON.parse(dataStr);
                
                switch (data.type) {
                  case 'progress':
                    setProgressMessage(data.message);
                    setExecutionSteps(prev => [...prev, data.message]);
                    setGenerationProgress(Math.min(90, generationProgress + 10));
                    break;
                    
                  case 'status':
                    setProgressMessage(data.message);
                    break;
                  case 'complete':
                    templateDeck = data.result;
                    setGenerationProgress(100);
                    break;
                  case 'error':
                    throw new Error(data.message);
                }
              } catch (e) {
                console.warn('Could not parse streaming data:', e);
              }
            }
          }
        }

        clearInterval(progressInterval);
        setGenerationProgress(100);
        
        if (templateDeck) {
          console.log('handleTemplateSelect Setting deck from streamed result');
          setCurrentDeck(templateDeck);
          setCurrentSlideIndex(0);
          
          const assistantMessage: Message = {
            id: Date.now().toString(),
            role: 'assistant',
            content: `Created a ${template.name} with ${templateDeck.slides?.length || 0} slides`,
            timestamp: new Date(),
            status: 'complete',
            deck: templateDeck
          };

          setMessages(prev => [...prev, assistantMessage]);
        } else {
          console.error('handleTemplateSelect No valid deck in response');
        }
      } catch (error) {
        clearInterval(progressInterval);
        const errorMessage: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `Error creating deck: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: new Date(),
          status: 'error'
        };
        setMessages(prev => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
        setIsGenerating(false);
        setGenerationProgress(0);
      }
    }
  };

  const handleSlideEdit = () => {
    if (currentDeck && currentDeck.slides[currentSlideIndex]) {
      setEditedContent({ ...currentDeck.slides[currentSlideIndex].content });
      setIsEditingSlide(true);
    }
  };

  const handleSaveSlide = () => {
    if (currentDeck && editedContent) {
      const updatedDeck = { ...currentDeck };
      updatedDeck.slides[currentSlideIndex].content = editedContent;
      setCurrentDeck(updatedDeck);
      setIsEditingSlide(false);
      setEditedContent(null);
    }
  };

  const submitFeedback = async () => {
    if (userFeedback.rating === 0) return;
    
    try {
      // Send feedback to unified brain with RL integration
      await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: lastPrompt,
          outputFormat: 'deck',
          rlFeedback: {
            previousAction: lastPrompt,
            reward: userFeedback.rating / 5, // Normalize to 0-1
            state: {
              deckType: selectedTemplate,
              slidesGenerated: currentDeck?.slides.length,
              userComment: userFeedback.comment
            }
          }
        })
      });

      // Also send to MCP backend directly
      await fetch('http://localhost:8000/api/mcp/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_type: 'deck',
          prompt: lastPrompt,
          rating: userFeedback.rating,
          comment: userFeedback.comment,
          output_quality: userFeedback.rating / 5,
          timestamp: new Date().toISOString()
        })
      });

      setShowFeedback(false);
      setUserFeedback({ rating: 0, comment: '' });
      
      // Show confirmation
      const feedbackMessage: Message = {
        id: Date.now().toString(),
        role: 'system',
        content: 'Thank you for your feedback! This helps improve future deck generations.',
        timestamp: new Date(),
        status: 'complete'
      };
      setMessages(prev => [...prev, feedbackMessage]);
    } catch (error) {
      console.error('Error submitting feedback:', error);
    }
  };

  // Render visual devices (timelines, matrices, textboxes, etc.)
  const renderDevice = (device: any) => {
    switch (device.type) {
      case 'timeline':
        return (
          <div className="relative">
            <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gradient-to-b from-purple-500 to-blue-500"></div>
            <div className="space-y-8">
              {device.items?.map((item: any, idx: number) => (
                <div key={idx} className="relative flex items-center">
                  <div className={`absolute left-6 w-4 h-4 rounded-full border-2 ${
                    item.highlight ? 'bg-purple-500 border-purple-500' : 'bg-white border-gray-400'
                  }`}></div>
                  <div className="ml-16">
                    <div className="flex items-center gap-2">
                      <span className={`font-bold ${item.highlight ? 'text-purple-600' : 'text-gray-600'}`}>
                        {item.date}
                      </span>
                      {item.icon && (
                        <span className="text-lg">{getIcon(item.icon)}</span>
                      )}
                    </div>
                    <div className="text-gray-700">{item.event}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'matrix':
        return (
          <div className="bg-gray-50 p-6 rounded-lg">
            <h3 className="font-bold text-lg mb-4">{device.title}</h3>
            <div className="relative h-64 border-2 border-gray-300 bg-white">
              <div className="absolute bottom-0 left-0 right-0 text-center text-sm text-gray-600 -mb-6">
                {device.axes?.x}
              </div>
              <div className="absolute top-0 bottom-0 left-0 text-sm text-gray-600 -ml-12 flex items-center">
                <span className="transform -rotate-90">{device.axes?.y}</span>
              </div>
              {device.items?.map((item: any, idx: number) => (
                <div
                  key={idx}
                  className={`absolute w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transform -translate-x-1/2 -translate-y-1/2 ${
                    item.highlight ? 'bg-purple-500 text-white' : 'bg-gray-400 text-white'
                  }`}
                  style={{
                    left: `${item.x}%`,
                    bottom: `${item.y}%`
                  }}
                  title={item.name}
                >
                  {item.name?.substring(0, 2)}
                </div>
              ))}
            </div>
          </div>
        );

      case 'textbox':
        const bgColor = device.style === 'callout' ? 'bg-yellow-50 border-yellow-300' :
                       device.style === 'quote' ? 'bg-blue-50 border-blue-300' :
                       device.style === 'stat' ? 'bg-green-50 border-green-300' :
                       'bg-purple-50 border-purple-300';
        return (
          <div className={`p-6 rounded-lg border-2 ${bgColor}`}>
            <div className="flex items-center justify-between">
              <div className={`text-2xl font-bold`} style={{ color: device.color || '#1a73e8' }}>
                {device.content}
              </div>
              {device.icon && (
                <span className="text-3xl">{getIcon(device.icon)}</span>
              )}
            </div>
          </div>
        );

      case 'comparison-table':
        return (
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white rounded-lg overflow-hidden">
              <thead className="bg-gray-100">
                <tr>
                  {device.headers?.map((header: string, idx: number) => (
                    <th key={idx} className="px-4 py-3 text-left font-semibold text-gray-700">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {device.rows?.map((row: string[], ridx: number) => (
                  <tr key={ridx} className={ridx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                    {row.map((cell: string, cidx: number) => (
                      <td key={cidx} className="px-4 py-3 text-gray-700">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      case 'process-flow':
        return (
          <div className="flex justify-between items-center">
            {device.steps?.map((step: any, idx: number) => (
              <React.Fragment key={idx}>
                <div className="flex-1 text-center">
                  <div className="bg-gradient-to-r from-purple-500 to-blue-500 text-white rounded-lg p-4">
                    <div className="text-sm font-semibold">{step.label}</div>
                    <div className="text-xl font-bold mt-1">{step.value}</div>
                  </div>
                </div>
                {idx < device.steps.length - 1 && (
                  <div className="w-8 flex items-center justify-center">
                    <span className="text-gray-400">→</span>
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        );

      case 'logo-grid':
        return (
          <div>
            {device.title && (
              <h3 className="text-center font-semibold text-gray-700 mb-4">{device.title}</h3>
            )}
            <div className="grid grid-cols-3 gap-4">
              {device.logos?.map((logo: string, idx: number) => (
                <div key={idx} className="bg-gray-100 h-20 rounded flex items-center justify-center">
                  {logo.startsWith('http') ? (
                    <img src={logo} alt="Logo" className="max-h-12 max-w-full" />
                  ) : (
                    <span className="text-gray-500">{logo}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        );

      case 'metric-cards':
        return (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {device.cards?.map((card: any, idx: number) => (
              <div key={idx} className="bg-gradient-to-br from-purple-50 to-blue-50 p-6 rounded-lg border border-purple-200">
                <div className="text-3xl font-bold text-gray-900">{card.metric}</div>
                <div className="text-sm text-gray-600 mt-1">{card.label}</div>
                {card.change && (
                  <div className={`text-sm font-semibold mt-2 ${
                    card.change.startsWith('+') ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {card.change}
                  </div>
                )}
                {card.sparkline && (
                  <div className="mt-2 flex items-end h-8 gap-1">
                    {card.sparkline.map((val: number, sidx: number) => (
                      <div
                        key={sidx}
                        className="flex-1 bg-purple-400 rounded-t"
                        style={{ height: `${(val / Math.max(...card.sparkline)) * 100}%` }}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        );

      case 'quote':
        return (
          <div className="bg-gray-50 p-6 rounded-lg border-l-4 border-purple-500">
            <div className="text-xl italic text-gray-700 mb-4">"{device.text}"</div>
            <div className="flex items-center gap-3">
              {device.logo && (
                <img src={device.logo} alt="Company" className="h-8" />
              )}
              <div className="text-sm text-gray-600">— {device.author}</div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  // Helper function for icons
  const getIcon = (iconName: string) => {
    const icons: any = {
      'rocket': '🚀',
      'trending-up': '📈',
      'seedling': '🌱',
      'users': '👥',
      'target': '🎯',
      'check': '✅',
      'star': '⭐',
      'chart': '📊',
      'dollar': '💰',
      'calendar': '📅',
      'globe': '🌍',
      'lightning': '⚡'
    };
    return icons[iconName] || '•';
  };

  const renderSlideContent = (slide: Slide) => {
    // Safety check for slide content
    if (!slide || !slide.content) {
      return (
        <div className="h-full flex flex-col p-8 bg-white">
          <div className="text-gray-500">No content available for this slide</div>
        </div>
      );
    }

    // Get theme styles
    const bgStyle = slide.theme?.background || (slide.template === 'title' ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : '#ffffff');
    const titleColor = slide.theme?.titleColor || (slide.template === 'title' ? '#ffffff' : '#1a202c');
    const textColor = slide.theme?.textColor || (slide.template === 'title' ? '#f7fafc' : '#4a5568');

    return (
      <div 
        className="h-full flex flex-col p-8"
        style={{ 
          background: bgStyle,
          color: textColor 
        }}
      >
        {/* Slide Header */}
        <div className="mb-6">
          <h2 className="text-3xl font-bold" style={{ color: titleColor }}>
            {slide.content.title || 'Untitled Slide'}
          </h2>
          {slide.content.subtitle && (
            <p className="text-xl mt-2" style={{ color: textColor, opacity: 0.9 }}>
              {slide.content.subtitle}
            </p>
          )}
        </div>

        {/* Slide Body */}
        <div className="flex-1 overflow-auto">
          {slide.content.body && (
            <p className="text-lg text-gray-700 mb-4">{slide.content.body}</p>
          )}

          {slide.content.bullets && slide.content.bullets.length > 0 && (
            <ul className="space-y-3 mb-4">
              {slide.content.bullets.map((bullet, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-purple-600 mr-3 mt-1">•</span>
                  <span className="text-gray-700">{bullet}</span>
                </li>
              ))}
            </ul>
          )}

          {slide.content.metrics && Object.keys(slide.content.metrics).length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6">
              {Object.entries(slide.content.metrics).map(([key, value]) => {
                // Handle different types of metric values
                let displayValue = value;
                let sourceInfo = null;
                
                // If value is an object with label, value, source structure
                if (typeof value === 'object' && value !== null) {
                  if ('value' in value) {
                    displayValue = value.value;
                  }
                  if ('label' in value) {
                    displayValue = value.label;
                  }
                  if ('source' in value) {
                    sourceInfo = value.source;
                  }
                  // If it's still an object, stringify it
                  if (typeof displayValue === 'object') {
                    displayValue = JSON.stringify(displayValue);
                  }
                }
                
                return (
                  <div key={key} className="bg-gray-50 p-4 rounded-lg">
                    <div className="text-sm text-gray-600">{key}</div>
                    <div className="text-2xl font-bold text-gray-900">{String(displayValue)}</div>
                    {sourceInfo && (
                      <div className="text-xs text-gray-500 mt-1">Source: {sourceInfo}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Render Visual Devices */}
          {slide.content.devices && slide.content.devices.map((device, idx) => (
            <div key={idx} className="mt-6">
              {renderDevice(device)}
            </div>
          ))}

          {slide.content.chart_data && (
            <div className="mt-6 p-4 bg-white rounded-lg border border-gray-200">
              {/* Use TableauLevelCharts for advanced visualizations */}
              {slide.content.chart_data.type && ['sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'treemap', 'funnel', 'composed'].includes(slide.content.chart_data.type.toLowerCase()) ? (
                <TableauLevelCharts 
                  type={slide.content.chart_data.type as any}
                  data={slide.content.chart_data.data}
                  title={slide.content.chart_data.title}
                  height={300}
                />
              ) : (
              <ResponsiveContainer width="100%" height={300}>
                {(() => {
                  const chartType = slide.content.chart_data.type?.toLowerCase();
                  const chartData = slide.content.chart_data.data;
                  const labels = chartData?.labels || [];
                  
                  // Format data for Recharts - handle both single and multi-dataset
                  let formattedData = [];
                  
                  if (chartData?.datasets && Array.isArray(chartData.datasets)) {
                    // Multiple datasets - format for multi-series charts
                    formattedData = labels.map((label, index) => {
                      const dataPoint: any = { name: label };
                      chartData.datasets.forEach((dataset: any) => {
                        const key = dataset.label || 'value';
                        dataPoint[key] = dataset.data[index] || 0;
                      });
                      return dataPoint;
                    });
                  } else if (chartData?.values) {
                    // Legacy format with values array
                    formattedData = labels.map((label, index) => ({
                      name: label,
                      value: chartData.values[index] || 0
                    }));
                  } else if (Array.isArray(chartData)) {
                    // Direct array of values
                    formattedData = chartData.map((value, index) => ({
                      name: labels[index] || `Item ${index + 1}`,
                      value: typeof value === 'number' ? value : parseFloat(value) || 0
                    }));
                  }
                  
                  // Define colors for charts
                  const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#d084d0'];
                  
                  switch (chartType) {
                    case 'line':
                      // Get all data keys except 'name'
                      const lineKeys = formattedData.length > 0 ? 
                        Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                      
                      return (
                        <LineChart data={formattedData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          {lineKeys.map((key, idx) => (
                            <Line 
                              key={key}
                              type="monotone" 
                              dataKey={key} 
                              stroke={COLORS[idx % COLORS.length]} 
                              strokeWidth={2}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />
                          ))}
                        </LineChart>
                      );
                    
                    case 'bar':
                      // Get all data keys except 'name'
                      const barKeys = formattedData.length > 0 ? 
                        Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                      
                      return (
                        <BarChart data={formattedData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          {barKeys.map((key, idx) => (
                            <Bar 
                              key={key}
                              dataKey={key} 
                              fill={COLORS[idx % COLORS.length]}
                              radius={[4, 4, 0, 0]}
                            />
                          ))}
                        </BarChart>
                      );
                    
                    case 'pie':
                      return (
                        <PieChart>
                          <Pie
                            data={formattedData}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                          >
                            {formattedData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      );
                    
                    case 'area':
                      return (
                        <AreaChart data={formattedData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Area type="monotone" dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
                        </AreaChart>
                      );
                    
                    default:
                      // Fallback to bar chart if type is unknown
                      return (
                        <BarChart data={formattedData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="value" fill="#8884d8">
                            {formattedData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Bar>
                        </BarChart>
                      );
                  }
                })()}
              </ResponsiveContainer>
              )}
              {slide.content.chart_data.title && !['sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'treemap', 'funnel', 'composed'].includes(slide.content.chart_data.type?.toLowerCase()) && (
                <p className="text-center text-sm text-gray-600 mt-2">
                  {slide.content.chart_data.title}
                </p>
              )}
            </div>
          )}
          
          {/* Citations Section */}
          {slide.content.citations && slide.content.citations.length > 0 && (
            <div className="mt-6 pt-4 border-t border-gray-200">
              <p className="text-xs font-semibold text-gray-500 mb-2">Sources:</p>
              <div className="space-y-1">
                {slide.content.citations.map((citation, idx) => (
                  <div key={idx} className="text-xs text-gray-600">
                    <span className="text-blue-600">[{idx + 1}]</span>{' '}
                    {citation.url ? (
                      <a 
                        href={citation.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                        title={citation.text}
                      >
                        {citation.source}
                      </a>
                    ) : (
                      <span>{citation.source}</span>
                    )}
                    {citation.text && (
                      <span className="text-gray-500 ml-1">({citation.text})</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Slide Footer */}
        {slide.content.notes && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500">
              <strong>Notes:</strong> {slide.content.notes}
            </p>
          </div>
        )}
      </div>
    );
  };

  const renderEditableSlideContent = () => {
    if (!editedContent) return null;

    return (
      <div className="h-full flex flex-col p-8 bg-white">
        <div className="mb-4">
          <input
            type="text"
            value={editedContent.title}
            onChange={(e) => setEditedContent({ ...editedContent, title: e.target.value })}
            className="text-3xl font-bold text-gray-900 w-full border-b-2 border-gray-300 focus:border-purple-500 outline-none"
          />
          <input
            type="text"
            value={editedContent.subtitle || ''}
            onChange={(e) => setEditedContent({ ...editedContent, subtitle: e.target.value })}
            placeholder="Subtitle (optional)"
            className="text-xl text-gray-600 mt-2 w-full border-b border-gray-200 focus:border-purple-500 outline-none"
          />
        </div>

        <div className="flex-1 overflow-auto">
          <textarea
            value={editedContent.body || ''}
            onChange={(e) => setEditedContent({ ...editedContent, body: e.target.value })}
            placeholder="Body text (optional)"
            className="text-lg text-gray-700 mb-4 w-full h-32 p-2 border border-gray-200 rounded focus:border-purple-500 outline-none resize-none"
          />

          {editedContent.bullets && (
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700">Bullet Points:</label>
              {editedContent.bullets.map((bullet, idx) => (
                <div key={idx} className="flex items-center mt-2">
                  <span className="text-purple-600 mr-3">•</span>
                  <input
                    type="text"
                    value={bullet}
                    onChange={(e) => {
                      const newBullets = [...editedContent.bullets!];
                      newBullets[idx] = e.target.value;
                      setEditedContent({ ...editedContent, bullets: newBullets });
                    }}
                    className="flex-1 p-2 border border-gray-200 rounded focus:border-purple-500 outline-none"
                  />
                </div>
              ))}
            </div>
          )}

          <textarea
            value={editedContent.notes || ''}
            onChange={(e) => setEditedContent({ ...editedContent, notes: e.target.value })}
            placeholder="Speaker notes (optional)"
            className="text-sm text-gray-500 w-full h-20 p-2 border border-gray-200 rounded focus:border-purple-500 outline-none resize-none"
          />
        </div>

        <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => setIsEditingSlide(false)}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveSlide}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
          >
            Save Changes
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      {/* Progress Tracker */}
      {activeTaskId && (
        <AgentProgressTracker 
          taskId={activeTaskId} 
          onClose={() => setActiveTaskId(undefined)}
        />
      )}
      
      <div className="flex gap-6">
        {/* Main Content Area */}
        <div className="flex-1">
          {/* Feedback Panel */}
          {showFeedback && currentDeck && (
            <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg shadow-lg mb-6 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">How was this deck generation?</h3>
              
              {/* Star Rating */}
              <div className="flex items-center gap-2 mb-4">
                <span className="text-sm text-gray-600">Rate the quality:</span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      onClick={() => setUserFeedback({ ...userFeedback, rating: star })}
                      className="p-1 hover:scale-110 transition-transform"
                    >
                      <Star
                        className={`w-6 h-6 ${
                          star <= userFeedback.rating
                            ? 'fill-yellow-400 text-yellow-400'
                            : 'text-gray-300'
                        }`}
                      />
                    </button>
                  ))}
                </div>
                {userFeedback.rating > 0 && (
                  <span className="text-sm text-gray-600">
                    {userFeedback.rating === 5 ? 'Excellent!' :
                     userFeedback.rating === 4 ? 'Good' :
                     userFeedback.rating === 3 ? 'Okay' :
                     userFeedback.rating === 2 ? 'Poor' : 'Very Poor'}
                  </span>
                )}
              </div>
              
              {/* Comment Box */}
              <div className="mb-4">
                <textarea
                  value={userFeedback.comment}
                  onChange={(e) => setUserFeedback({ ...userFeedback, comment: e.target.value })}
                  placeholder="Any specific feedback? (optional)"
                  className="w-full p-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  rows={2}
                />
              </div>
              
              {/* Submit Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={submitFeedback}
                  disabled={userFeedback.rating === 0}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <ThumbsUp className="w-4 h-4" />
                  Submit Feedback
                </button>
                <button
                  onClick={() => {
                    setShowFeedback(false);
                    setUserFeedback({ rating: 0, comment: '' });
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50"
                >
                  Skip
                </button>
              </div>
            </div>
          )}

          {/* Deck Viewer/Editor */}
          {currentDeck && (
            <div className="bg-white rounded-lg shadow-lg mb-6">
              <div className="flex items-center justify-between p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">{currentDeck.title}</h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentSlideIndex(Math.max(0, currentSlideIndex - 1))}
                    disabled={currentSlideIndex === 0}
                    className="p-2 rounded hover:bg-gray-100 disabled:opacity-50"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="text-sm text-gray-600">
                    {currentSlideIndex + 1} / {currentDeck.slides.length}
                  </span>
                  <button
                    onClick={() => setCurrentSlideIndex(Math.min(currentDeck.slides.length - 1, currentSlideIndex + 1))}
                    disabled={currentSlideIndex === currentDeck.slides.length - 1}
                    className="p-2 rounded hover:bg-gray-100 disabled:opacity-50"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                  <div className="ml-4 flex gap-2">
                    <button
                      onClick={handleSlideEdit}
                      className="p-2 rounded hover:bg-gray-100"
                    >
                      <Edit2 className="w-5 h-5" />
                    </button>
                    <button className="p-2 rounded hover:bg-gray-100">
                      <Eye className="w-5 h-5" />
                    </button>
                    <button className="p-2 rounded hover:bg-gray-100">
                      <Download className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
              
              {/* Slide Content Area */}
              <div className="h-96 overflow-hidden">
                {isEditingSlide 
                  ? renderEditableSlideContent()
                  : renderSlideContent(currentDeck.slides[currentSlideIndex])
                }
              </div>

              {/* Slide Thumbnails */}
              <div className="p-4 border-t border-gray-200">
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {currentDeck.slides.map((slide, idx) => (
                    <button
                      key={slide.id}
                      onClick={() => setCurrentSlideIndex(idx)}
                      className={`flex-shrink-0 w-24 h-16 border-2 rounded ${
                        idx === currentSlideIndex 
                          ? 'border-purple-500 bg-purple-50' 
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="p-1 text-xs">
                        <div className="font-medium truncate">{idx + 1}. {slide?.content?.title || 'Untitled'}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Data Sources Section */}
              {currentDeck.data_sources && currentDeck.data_sources.length > 0 && (
                <div className="p-4 border-t border-gray-200 bg-gray-50">
                  <h3 className="text-xs font-semibold text-gray-600 mb-2">All Data Sources</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {currentDeck.data_sources.map((source, idx) => (
                      <div key={idx} className="text-xs">
                        {source.url ? (
                          <a 
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline flex items-center gap-1"
                          >
                            <span>📊</span>
                            <span>{source.name}</span>
                            {source.date && <span className="text-gray-500">({source.date})</span>}
                          </a>
                        ) : (
                          <span className="text-gray-600 flex items-center gap-1">
                            <span>📊</span>
                            <span>{source.name}</span>
                            {source.date && <span className="text-gray-500">({source.date})</span>}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Chat Interface */}
          <div className="bg-white rounded-lg shadow-lg">
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Presentation className="w-5 h-5 text-purple-600" />
                </div>
                <h1 className="text-lg font-semibold text-gray-900">Deck Agent</h1>
              </div>
            </div>

            {/* Messages */}
            <div className="h-64 overflow-y-auto p-4 space-y-4">
              {messages.map(message => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xl p-3 rounded-lg ${
                      message.role === 'user'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <div className="text-sm">{message.content}</div>
                  </div>
                </div>
              ))}
              
              {isGenerating && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-3 rounded-lg">
                    <div className="flex items-center gap-2">
                      <RefreshCw className="w-4 h-4 text-purple-600 animate-spin" />
                      <span className="text-sm text-gray-600">Generating deck...</span>
                    </div>
                    <div className="w-48 bg-gray-200 rounded-full h-2 mt-2">
                      <div 
                        className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${generationProgress}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompts */}
            <div className="px-4 py-2 border-t border-gray-200">
              <div className="flex gap-2 overflow-x-auto">
                {quickPrompts.slice(0, 3).map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => handleQuickPrompt(prompt)}
                    className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs whitespace-nowrap hover:bg-purple-200"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder="Describe the deck you want to create..."
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
            
            {/* RL Feedback Panel */}
            {currentDeck && useRL && (
              <div className="border-t border-gray-200 p-4 bg-green-50">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-semibold text-green-800">
                      Training Feedback - Help improve the model
                    </span>
                  </div>
                  {feedbackSent && (
                    <span className="text-xs text-green-600 animate-pulse">
                      ✓ Feedback sent!
                    </span>
                  )}
                </div>
                
                {/* Quick Feedback Buttons */}
                <div className="flex gap-2 mb-2">
                  <button 
                    onClick={() => submitRLFeedback('good', 'Deck is perfect')}
                    className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-xs text-white"
                  >
                    👍 Perfect
                  </button>
                  <button 
                    onClick={() => submitRLFeedback('edit', 'Needs minor changes')}
                    className="px-3 py-1 bg-yellow-600 hover:bg-yellow-700 rounded text-xs text-white"
                  >
                    ✏️ Minor Edit
                  </button>
                  <button 
                    onClick={() => submitRLFeedback('fix', 'Needs major changes')}
                    className="px-3 py-1 bg-orange-600 hover:bg-orange-700 rounded text-xs text-white"
                  >
                    🔧 Major Fix
                  </button>
                  <button 
                    onClick={() => submitRLFeedback('bad', 'Wrong content')}
                    className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-xs text-white"
                  >
                    👎 Wrong
                  </button>
                </div>
                
                {/* Semantic Feedback Input */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={semanticFeedback}
                    onChange={(e) => setSemanticFeedback(e.target.value)}
                    placeholder="e.g., Add more financial metrics, Change to Series B deck, Use 2024 data"
                    className="flex-1 px-3 py-1 border border-green-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-green-500"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && semanticFeedback.trim()) {
                        submitRLFeedback('semantic', semanticFeedback);
                      }
                    }}
                  />
                  <button 
                    onClick={() => semanticFeedback.trim() && submitRLFeedback('semantic', semanticFeedback)}
                    disabled={!semanticFeedback.trim()}
                    className="px-4 py-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 rounded text-sm text-white"
                  >
                    Send
                  </button>
                </div>
              </div>
            )}
            
            {/* RL Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-50 border-t border-gray-200">
              <span className="text-xs text-gray-600">AI Training Mode</span>
              <button
                onClick={() => setUseRL(!useRL)}
                className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
                  useRL ? "bg-green-600" : "bg-gray-400"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    useRL ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-64">
          {/* Templates */}
          <div className="bg-white rounded-lg shadow-lg p-4 mb-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Templates</h2>
            <div className="space-y-2">
              {templates.map(template => (
                <button
                  key={template.id}
                  onClick={() => handleTemplateSelect(template.id)}
                  className={`w-full p-2 rounded-lg border text-left text-sm ${
                    selectedTemplate === template.id
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`p-1 rounded ${template.color}`}>
                      {template.icon}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{template.name}</div>
                      <div className="text-xs text-gray-500">{template.slides} slides</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Export Options */}
          {currentDeck && (
            <div className="bg-white rounded-lg shadow-lg p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Export</h2>
              <div className="space-y-2">
                <button className="w-full px-3 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700">
                  <Download className="w-4 h-4 inline mr-2" />
                  PowerPoint
                </button>
                <button className="w-full px-3 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50">
                  <Download className="w-4 h-4 inline mr-2" />
                  PDF
                </button>
              </div>
            </div>
          )}

          {/* Citations Section */}
          {citations && citations.length > 0 && (
            <div className="bg-white rounded-lg shadow-lg p-4 mt-4">
              <CitationDisplay citations={citations} />
            </div>
          )}

          {/* Charts Section */}
          {charts && charts.length > 0 && (
            <div className="bg-white rounded-lg shadow-lg p-4 mt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700 flex items-center">
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Visual Analytics
                </h3>
                <button
                  onClick={() => setShowCharts(!showCharts)}
                  className="text-xs text-blue-600 hover:text-blue-700"
                >
                  {showCharts ? 'Hide' : 'Show'}
                </button>
              </div>
              
              {showCharts && (
                <div className="space-y-4">
                  {charts.map((chart, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-3">
                      <AgentChartGenerator
                        prompt={`Chart ${index + 1}: ${chart.title || chart.type}`}
                        data={chart.data || chart}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}