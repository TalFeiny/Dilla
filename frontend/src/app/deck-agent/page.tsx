'use client';

import React, { useState, useRef, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import AgentProgressTracker from '@/components/AgentProgressTracker';
import AgentChartGenerator from '@/components/AgentChartGenerator';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { DECK_DESIGN_TOKENS } from '@/styles/deck-design-tokens';
import { getTheme, setTheme, initTheme } from '@/lib/theme';
import { formatMetricValue } from '@/utils/formatters';
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
  ThumbsDown,
  Star,
  MessageSquare,
  Moon,
  Sun,
  Sparkles,
  Zap,
  ArrowRight,
  Check,
  Calendar,
  Globe
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
import { fixChartData, fixChartDataObject, fixHeatmapData, fixLineChartData, fixProbabilityCloudData, fixSankeyData } from '@/utils/chartDataFixer';

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
  future_chart_data?: any; // Future ownership scenarios (waterfall/bar chart)
  future_pie_charts?: any[]; // Future ownership pie charts array
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


function DeckAgentContent() {
  const [mounted, setMounted] = useState(false);
  
  // Initialize with default values for SSR compatibility
  const [isPdfMode, setIsPdfMode] = useState(false);
  const [deckId, setDeckId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(''); // Initialize empty for SSR
  const [isDarkMode, setIsDarkMode] = useState(false);
  
  // Use searchParams safely
  const searchParams = useSearchParams();
  
  // Handle hydration - only update after mount
  useEffect(() => {
    setMounted(true);
    // Generate session ID on client side only
    const newSessionId = `deck-${Date.now()}`;
    setSessionId(newSessionId);
    
    // Read searchParams after mount to avoid hydration mismatch
    if (searchParams) {
      setIsPdfMode(searchParams.get('pdfMode') === 'true');
      setDeckId(searchParams.get('deckId'));
    }
    
    // Initialize theme from localStorage after mount
    const savedTheme = localStorage.getItem('theme');
    setIsDarkMode(savedTheme === 'dark');
  }, [searchParams]);
  
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Create professional presentations and pitch decks. Describe what you need and I\'ll generate a complete deck with slides, charts, and data.',
      timestamp: new Date(0), // Use epoch time for SSR consistency
      status: 'complete'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
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
  const [lastPrompt, setLastPrompt] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('pitch');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const justGeneratedDeckRef = useRef<boolean>(false); // Track if we just generated a deck via API
  const currentDeckRef = useRef<GeneratedDeck | null>(null); // Track current deck to avoid stale closures
  const hasAttemptedRecoveryRef = useRef<boolean>(false); // Track if recovery has already been attempted


  const quickPrompts = [
    "Compare @Adarga to @firefliesai for my 126m fund in year 3 q4 with 49m more to deploy",
    "Compare @Cursor and @Perplexity for my 122m fund, in year 3 with 63m to deploy",
    "Compare @Phoebe and @Tabular: i run a 178m fund that invests in pre-seed-seriesB",
    "Compare @Fleetzero and @Quilt for my 145m fund in yr 2 with 101m to deploy",
    "Compare @BuiltAI and @Palindrome for my series A fund, 234m with 0.4 dpi and 3.1 tvpi",
    "Compare @Gauss and @BankBio for my 89m seed fund with 48m to deploy"
  ];

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize theme after mount
  useEffect(() => {
    if (!mounted) return;
    // Initialize theme from system preference or stored preference
    const theme = initTheme();
    setIsDarkMode(theme === 'night');
  }, [mounted]);
  
  // Theme management
  const toggleTheme = () => {
    const newTheme = isDarkMode ? 'day' : 'night';
    setTheme(newTheme);
    setIsDarkMode(!isDarkMode);
  };

  // Apply theme to document
  useEffect(() => {
    if (!mounted) return;
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'night' : 'day');
  }, [isDarkMode, mounted]);

  // Persist deck to localStorage when it changes
  useEffect(() => {
    if (!mounted) return;
    if (currentDeck && currentDeck.slides && currentDeck.slides.length > 0) {
      try {
        localStorage.setItem('lastGeneratedDeck', JSON.stringify(currentDeck));
        // Also persist current slide index
        localStorage.setItem('lastSlideIndex', currentSlideIndex.toString());
        console.log('[Deck Agent] Saved deck to localStorage with', currentDeck.slides.length, 'slides at index', currentSlideIndex);
      } catch (error) {
        console.error('[Deck Agent] Failed to save deck to localStorage:', error);
      }
    }
  }, [currentDeck, currentSlideIndex, mounted]);

  // Try to recover deck from localStorage or messages on mount if no deck is loaded
  // Only run once on mount to prevent overwriting freshly generated decks
  useEffect(() => {
    if (!mounted) return;
    
    // Check for clear parameter in URL to clear localStorage
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get('clear') === 'true') {
      try {
        localStorage.removeItem('lastGeneratedDeck');
        localStorage.removeItem('lastSlideIndex');
        console.log('[Deck Agent] Cleared localStorage due to clear=true parameter');
        // Remove the parameter from URL
        searchParams.delete('clear');
        const newUrl = window.location.pathname + (searchParams.toString() ? '?' + searchParams.toString() : '');
        window.history.replaceState({}, '', newUrl);
      } catch (error) {
        console.error('[Deck Agent] Failed to clear localStorage:', error);
      }
    }
    
    // Only attempt recovery once when component mounts
    if (hasAttemptedRecoveryRef.current) return;
    
    // Check if we already have a deck using both ref and state to avoid stale closures
    const hasValidDeck = (currentDeckRef.current && currentDeckRef.current.slides && currentDeckRef.current.slides.length > 0) ||
                         (currentDeck && currentDeck.slides && currentDeck.slides.length > 0);
    
    if (hasValidDeck) {
      // Already have a deck, don't load from storage
      console.log('[Deck Agent] Skipping recovery - already have deck');
      hasAttemptedRecoveryRef.current = true;
      return;
    }
    
    // Mark recovery as attempted before proceeding
    hasAttemptedRecoveryRef.current = true;
    
    // First try localStorage
    try {
      const savedDeck = localStorage.getItem('lastGeneratedDeck');
      if (savedDeck) {
        const parsedDeck = JSON.parse(savedDeck);
        if (parsedDeck && parsedDeck.slides && parsedDeck.slides.length > 0) {
          // Double-check we still don't have a deck (race condition protection)
          const stillNoDeck = !currentDeckRef.current || !currentDeckRef.current.slides || currentDeckRef.current.slides.length === 0;
          if (stillNoDeck) {
          console.log('[Deck Agent] Recovered deck from localStorage:', {
            id: parsedDeck.id,
            title: parsedDeck.title,
            slideCount: parsedDeck.slides.length,
            hasCharts: parsedDeck.charts?.length || 0,
            hasCitations: parsedDeck.citations?.length || 0
          });
          setCurrentDeck(parsedDeck);
          currentDeckRef.current = parsedDeck;
          setCitations(parsedDeck.citations || []);
          setCharts(parsedDeck.charts || []);
          // Restore slide index if saved
          const savedIndex = localStorage.getItem('lastSlideIndex');
          if (savedIndex) {
            const index = parseInt(savedIndex, 10);
            if (!isNaN(index) && index >= 0 && index < parsedDeck.slides.length) {
              setCurrentSlideIndex(index);
              console.log('[Deck Agent] Restored slide index to', index);
            }
          }
          return;
          } else {
            console.log('[Deck Agent] Skipped localStorage recovery - deck was set during recovery');
          }
        }
      }
    } catch (error) {
      console.error('[Deck Agent] Failed to recover deck from localStorage:', error);
    }
    
    // If localStorage doesn't have it, try to recover from messages (only on mount)
    // Double-check we still don't have a deck
    const stillNoDeck = !currentDeckRef.current || !currentDeckRef.current.slides || currentDeckRef.current.slides.length === 0;
    if (stillNoDeck) {
      const lastDeckMessage = messages
        .filter(msg => msg.deck && msg.deck.slides && msg.deck.slides.length > 0)
        .pop();
      
      if (lastDeckMessage && lastDeckMessage.deck) {
        console.log('[Deck Agent] Recovered deck from messages:', {
          id: lastDeckMessage.deck.id,
          title: lastDeckMessage.deck.title,
          slideCount: lastDeckMessage.deck.slides.length,
          hasCharts: lastDeckMessage.deck.charts?.length || 0,
          hasCitations: lastDeckMessage.deck.citations?.length || 0
        });
        setCurrentDeck(lastDeckMessage.deck);
        currentDeckRef.current = lastDeckMessage.deck;
        setCitations(lastDeckMessage.deck.citations || []);
        setCharts(lastDeckMessage.deck.charts || []);
        // Restore slide index if saved
        const savedIndex = localStorage.getItem('lastSlideIndex');
        if (savedIndex) {
          const index = parseInt(savedIndex, 10);
          if (!isNaN(index) && index >= 0 && index < lastDeckMessage.deck.slides.length) {
            setCurrentSlideIndex(index);
            console.log('[Deck Agent] Restored slide index to', index);
          }
        }
      }
    }
  }, [mounted]); // Only run on mount - use ref guard to prevent multiple runs

  // Load deck data if deckId provided (for PDF mode)
  // ONLY load if we don't already have a deck set via API generation
  useEffect(() => {
    // Don't run until component is mounted
    if (!mounted) return;
    
    // Don't load if no deckId
    if (!deckId) return;
    
    // CRITICAL: Don't overwrite a deck that was just generated via API
    // Only load from deckId if we don't have a current deck OR if we're in PDF mode
    // This prevents the "rapidly falling back" issue where generated decks get overwritten
    if (justGeneratedDeckRef.current && !isPdfMode) {
      console.log(`[PDF_MODE] Skipping deck load - deck was just generated via API`);
      justGeneratedDeckRef.current = false; // Reset flag
      return;
    }
    
    // Create AbortController outside async function so it's accessible in cleanup
    const controller = new AbortController();
    let timeoutId: NodeJS.Timeout | null = null;
    
    const loadDeckFromStorage = async () => {
      try {
        console.log(`[PDF_MODE] Loading deck with ID: ${deckId}`);
        
        // Add timeout to prevent hanging
        timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout
        
        const response = await fetch(`/api/deck-data/${deckId}`, {
          signal: controller.signal
        });
        
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
        
        if (!response.ok) {
          console.error(`[PDF_MODE] Failed to load deck ${deckId}:`, response.status);
          
          // Show error message instead of hanging
          const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
          console.error(`[PDF_MODE] Error details:`, errorData);
          
          // Only set error deck if we don't already have a deck
          // This prevents overwriting a valid deck with an error
          const hasValidDeck = currentDeckRef.current && currentDeckRef.current.slides && currentDeckRef.current.slides.length > 0;
          if (!hasValidDeck) {
            const errorDeck = {
              id: deckId,
              title: 'Deck Loading Error',
              type: 'error',
              slides: [{
                id: 'error-slide',
                order: 0,
                template: 'error',
                content: {
                  title: 'Deck Not Found',
                  subtitle: `Could not load deck with ID: ${deckId}`,
                  body: `Error: ${errorData.error || 'Unknown error'}. Please check if the deck ID is correct and try again.`,
                  bullets: [
                    'Verify the deck ID is correct',
                    'Check if the deck was recently generated',
                    'Try generating a new deck'
                  ]
                }
              }],
              theme: 'professional',
              data_sources: [],
              citations: [],
              charts: []
            };
            setCurrentDeck(errorDeck);
            currentDeckRef.current = errorDeck;
          }
          return;
        }
        
        const deckData = await response.json();
        console.log(`[PDF_MODE] Loaded deck with ${deckData.slides?.length || 0} slides`);
        
        // Use ref to check current deck to avoid stale closure issues
        const hasValidDeck = currentDeckRef.current && currentDeckRef.current.slides && currentDeckRef.current.slides.length > 0;
        
        // Only set deck if we got valid slides, and only if we don't have a valid deck already
        // CRITICAL: Don't overwrite a deck that was just generated via API unless we're in PDF mode
        if (deckData.slides && deckData.slides.length > 0) {
          // Only overwrite if:
          // 1. We don't have a current deck with slides, OR
          // 2. We're in PDF mode (explicitly loading from storage)
          if (!hasValidDeck || isPdfMode) {
            console.log(`[PDF_MODE] Setting deck from storage (isPdfMode: ${isPdfMode}, hasValidDeck: ${hasValidDeck})`);
            setCurrentDeck(deckData);
            currentDeckRef.current = deckData; // Update ref
            // Restore slide index if saved
            const savedIndex = localStorage.getItem('lastSlideIndex');
            if (savedIndex) {
              const index = parseInt(savedIndex, 10);
              if (!isNaN(index) && index >= 0 && index < deckData.slides.length) {
                setCurrentSlideIndex(index);
                console.log(`[PDF_MODE] Restored slide index to ${index}`);
              }
            }
          } else {
            console.log(`[PDF_MODE] Skipping deck load - already have valid deck with ${currentDeckRef.current.slides.length} slides`);
          }
        } else if (!hasValidDeck) {
          // Only set empty deck if we don't have a valid one
          console.warn(`[PDF_MODE] Loaded deck has no slides, keeping current deck if it exists`);
        }
        
        // If PDF mode, hide UI elements and show only the deck
        if (isPdfMode) {
          // Hide chat interface and show only deck presentation
          console.log('[PDF_MODE] PDF mode enabled - hiding UI elements');
        }
      } catch (error) {
        // Don't handle AbortError as it's expected when component unmounts or effect is cleaned up
        if (error instanceof Error && error.name === 'AbortError') {
          console.log('[PDF_MODE] Deck load aborted');
          return;
        }
        
        console.error('[PDF_MODE] Error loading deck:', error);
        
        // Only set error deck if we don't already have a valid deck
        // This prevents overwriting a generated deck with an error
        const hasValidDeck = currentDeckRef.current && currentDeckRef.current.slides && currentDeckRef.current.slides.length > 0;
        if (!hasValidDeck) {
          const errorDeck = {
            id: deckId || 'error',
            title: 'Deck Loading Error',
            type: 'error',
            slides: [{
              id: 'error-slide',
              order: 0,
              template: 'error',
              content: {
                title: 'Connection Error',
                subtitle: 'Could not connect to deck service',
                body: `Network error: ${error instanceof Error ? error.message : 'Unknown error'}. Please check your connection and try again.`,
                bullets: [
                  'Check your internet connection',
                  'Verify the backend service is running',
                  'Try refreshing the page'
                ]
              }
            }],
            theme: 'professional',
            data_sources: [],
            citations: [],
            charts: []
          };
          setCurrentDeck(errorDeck);
          currentDeckRef.current = errorDeck;
        }
      } finally {
        // Clean up timeout if it still exists
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
      }
    };
    
    loadDeckFromStorage();
    
    // Cleanup function to abort any pending requests
    return () => {
      // Abort any pending fetch request
      controller.abort();
      // Clear timeout if it exists
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [deckId, isPdfMode, mounted]); // Added mounted to dependencies to prevent running before mount

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Extract fund context from user prompt
  const extractFundContext = (prompt: string): Record<string, any> => {
    const context: any = {};
    
    // Portfolio contribution (millions)
    const portContrib = prompt.match(/portfolio contribution.*?(\d+(?:\.\d+)?)\s*m/i);
    if (portContrib) {
      context.portfolio_contribution = parseFloat(portContrib[1]) * 1_000_000;
      context.fund_size = context.portfolio_contribution; // Use as fund_size
    }
    
    // Fund size
    const fundSize = prompt.match(/(\$?\d+(?:\.\d+)?)\s*m(?:illion)?\s+fund/i);
    if (fundSize) {
      context.fund_size = parseFloat(fundSize[1].replace('$', '')) * 1_000_000;
    }
    
    // DPI
    const dpi = prompt.match(/(\d+(?:\.\d+)?)\s+dpi/i);
    if (dpi) context.dpi = parseFloat(dpi[1]);
    
    // TVPI
    const tvpi = prompt.match(/(\d+(?:\.\d+)?)\s+tvpi/i);
    if (tvpi) context.tvpi = parseFloat(tvpi[1]);
    
    return context;
  };

  const clearCurrentDeck = () => {
    try {
      localStorage.removeItem('lastGeneratedDeck');
      localStorage.removeItem('lastSlideIndex');
      setCurrentDeck(null);
      currentDeckRef.current = null;
      setCurrentSlideIndex(0);
      setCitations([]);
      setCharts([]);
      console.log('[Deck Agent] Cleared deck and localStorage');
    } catch (error) {
      console.error('[Deck Agent] Failed to clear deck:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    console.log('🎯 handleSubmit Called with input:', input);

    // Clear old deck from localStorage and state when starting new generation
    clearCurrentDeck();

    const userMessage: Message = {
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substr(2, 9),
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
      
      // Call the unified brain API (NON-STREAMING for reliability)
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: deckPrompt,
          output_format: 'deck',
          stream: false,  // DISABLED: Streaming causes format mismatch issues
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
            requireRealData: true,
            ...extractFundContext(input)  // Merge extracted fund context
          }
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Backend error:', errorText);
        throw new Error(`Failed to get agent response: ${errorText}`);
      }

      // Handle non-streaming JSON response
      setProgressMessage('⏳ Processing request...');
      const data = await response.json();

      console.log('📥 [Deck Agent] RAW Response:', JSON.stringify(data).substring(0, 500));
      console.log('🔍 [Deck Agent] Response structure:', {
        success: data.success,
        hasResult: !!data.result,
        hasResults: !!data.results,  // Check both
        hasDirectSlides: !!data.slides,  // Check top-level slides
        resultFormat: data.result?.format || data.format,
        resultsFormat: data.results?.format,
        resultKeys: data.result ? Object.keys(data.result) : [],
        resultsKeys: data.results ? Object.keys(data.results) : [],
        topLevelKeys: Object.keys(data),
        slidesCount: data.result?.slides?.length || data.slides?.length,
        resultsSlidesCount: data.results?.slides?.length,
        firstSlide: data.result?.slides?.[0] || data.slides?.[0],
        firstResultSlide: data.results?.slides?.[0]
      });
      
      // CRITICAL DEBUG: Log slide count received from Next.js API
      if (data.result?.slides) {
        console.log(`[Deck Agent] ✅ Received ${data.result.slides.length} slides from API via data.result.slides`);
      } else if (data.results?.slides) {
        console.log(`[Deck Agent] ✅ Received ${data.results.slides.length} slides from API via data.results.slides`);
      } else if (data.slides) {
        console.log(`[Deck Agent] ✅ Received ${data.slides.length} slides from API at top level`);
      } else {
        console.log('[Deck Agent] ❌ Received NO slides from API in data.result, data.results, or top level');
        console.log('[Deck Agent] Full response keys:', Object.keys(data));
        console.log('[Deck Agent] data.result keys:', data.result ? Object.keys(data.result) : 'no result');
        console.log('[Deck Agent] data.results keys:', data.results ? Object.keys(data.results) : 'no results');
      }
      
      clearInterval(progressInterval);
      setGenerationProgress(100);
      
      // Extract deck data from various possible locations
      let deckData = null;
      
      // Try different locations for deck data
      if (data.result && (data.result.format === 'deck' || data.result.slides)) {
        deckData = data.result;
        console.log('✅ [Deck Agent] Found deck data in data.result');
      } else if (data.results && (data.results.format === 'deck' || data.results.slides)) {
        deckData = data.results;
        console.log('✅ [Deck Agent] Found deck data in data.results');
      } else if (data.format === 'deck' || data.slides) {
        deckData = data;
        console.log('✅ [Deck Agent] Found deck data at top level');
      } else if (data.success && data['deck-storytelling']) {
        deckData = data['deck-storytelling'];
        console.log('✅ [Deck Agent] Found deck data in deck-storytelling key');
      }
      
      // Validate deck data
      if (!deckData) {
        console.error('❌ [Deck Agent] No deck data found in response:', data);
        throw new Error('No deck data in response');
      }
      
      // Normalize slides to ensure it's always an array
      const slides = Array.isArray(deckData.slides) ? deckData.slides : (deckData.slides ? [deckData.slides] : []);
      deckData.slides = slides;  // Update deckData with normalized slides
      
      // Ensure we have slides (now guaranteed to be an array)
      if (slides.length === 0) {
        console.warn('⚠️ [Deck Agent] Empty slides array - will create fallback deck');
      }
      
      if (deckData.slides.length === 0) {
        console.warn('⚠️ [Deck Agent] Empty slides array - creating fallback deck');
        // Create a fallback deck with a single slide explaining the issue
        const fallbackDeck: GeneratedDeck = {
          id: `deck-${Date.now()}`,
          title: 'Deck Generation Issue',
          type: selectedTemplate || 'pitch',
          slides: [{
            id: 'fallback-slide',
            order: 0,
            template: 'error',
            content: {
              title: 'Deck Generation In Progress',
              subtitle: 'The AI is still processing your request',
              body: 'Please wait while we generate your investment deck. This may take a few moments.',
              bullets: [
                'The backend is processing your request',
                'Deck generation can take 30-60 seconds',
                'Please try again in a moment'
              ]
            }
          }],
          theme: 'professional',
          data_sources: [],
          citations: [],
          charts: []
        };
        setCurrentDeck(fallbackDeck);
        currentDeckRef.current = fallbackDeck;
        return;
      }
      
      // Build deck object from response
      const deck: GeneratedDeck = {
        id: `deck-${Date.now()}`,
        title: deckData.title || deckData.metadata?.title || 'Investment Analysis Deck',
        type: selectedTemplate || 'pitch',
        slides: deckData.slides,
        theme: deckData.theme || 'professional',
        data_sources: deckData.data_sources || deckData.metadata?.data_sources || [],
        citations: deckData.citations || [],
        charts: deckData.charts || []
      };
      
      console.log('✅ [Deck Agent] Built deck successfully:', {
        id: deck.id,
        title: deck.title,
        slideCount: deck.slides.length,
        hasTheme: !!deck.theme,
        hasCitations: deck.citations.length,
        hasCharts: deck.charts.length
      });
      
      // CRITICAL DEBUG: Log final deck slide count
      console.log(`[Deck Agent] ✅ Final deck has ${deck.slides.length} slides`);
      if (deck.slides.length > 0) {
        console.log(`[Deck Agent] ✅ First slide title: ${deck.slides[0]?.content?.title || 'No title'}`);
        console.log(`[Deck Agent] ✅ Slide IDs: ${deck.slides.map(s => s.id).slice(0, 3).join(', ')}`);
      } else {
        console.log('[Deck Agent] ❌ Final deck has ZERO slides - this is the bug!');
      }
      
      // Set deck and related data
      setCurrentDeck(deck);
      currentDeckRef.current = deck; // Update ref to avoid stale closures
      setCitations(deck.citations);
      setCharts(deck.charts);
      setLastPrompt(input);
      setProgressMessage(`✅ Generated ${deck.slides.length} slides`);
      
      // CRITICAL: Mark that we just generated a deck via API to prevent useEffect from overwriting it
      // This prevents the "rapidly falling back" issue where the deck gets overwritten
      justGeneratedDeckRef.current = true;
      
      // Clear deckId from URL params to prevent useEffect from reloading and overwriting
      if (deckId) {
        console.log('[Deck Agent] Clearing deckId to prevent reload overwrite');
        setDeckId(null);
        // Also update URL to remove deckId param without page reload
        if (typeof window !== 'undefined' && window.history) {
          const url = new URL(window.location.href);
          url.searchParams.delete('deckId');
          window.history.replaceState({}, '', url.toString());
        }
      }
      
      const successMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Generated ${deck.slides.length}-slide ${selectedTemplate || 'pitch'} deck. Review and refine as needed.`,
        timestamp: new Date(),
        status: 'complete',
        deck
      };
      setMessages(prev => [...prev, successMessage]);
      
      // Deck already set - reset to first slide
      // Use setTimeout to ensure deck state is fully set before changing slide index
      setTimeout(() => {
        setCurrentSlideIndex(0);
        // Ensure deck is still set (prevent race conditions)
        if (currentDeckRef.current && currentDeckRef.current.slides && currentDeckRef.current.slides.length > 0) {
          console.log('[Deck Agent] Deck confirmed stable with', currentDeckRef.current.slides.length, 'slides');
        }
      }, 100);
      
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

  const handleExportPDF = async () => {
    if (!currentDeck) {
      console.error('No deck to export');
      return;
    }

    try {
      setProgressMessage('Exporting to PDF...');
      setIsGenerating(true);
      
      const response = await fetch('/api/export/deck', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          deck: currentDeck,
          format: 'pdf'
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `Export failed: ${response.status}`);
      }

      // Handle file download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentDeck.title || 'deck'}_${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      setProgressMessage('PDF exported successfully');
    } catch (error) {
      console.error('Error exporting PDF:', error);
      setProgressMessage(`Error: ${error instanceof Error ? error.message : 'Failed to export PDF'}`);
    } finally {
      setIsGenerating(false);
      setTimeout(() => setProgressMessage(''), 3000);
    }
  };

  const handleExportPPTX = async () => {
    if (!currentDeck) {
      console.error('No deck to export');
      return;
    }

    try {
      setProgressMessage('Exporting to PowerPoint...');
      setIsGenerating(true);
      
      const response = await fetch('/api/export/deck', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          deck: currentDeck,
          format: 'pptx'
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `Export failed: ${response.status}`);
      }

      // Handle file download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentDeck.title || 'deck'}_${Date.now()}.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      setProgressMessage('PowerPoint exported successfully');
    } catch (error) {
      console.error('Error exporting PPTX:', error);
      setProgressMessage(`Error: ${error instanceof Error ? error.message : 'Failed to export PowerPoint'}`);
    } finally {
      setIsGenerating(false);
      setTimeout(() => setProgressMessage(''), 3000);
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
      currentDeckRef.current = updatedDeck;
      setIsEditingSlide(false);
      setEditedContent(null);
    }
  };

  // Helper function to safely parse device content that might be a JSON string
  const parseDeviceContent = (content: any): string => {
    if (!content) return '';
    
    // If it's already a string, check if it's JSON
    if (typeof content === 'string') {
      // Check if it looks like JSON (starts with { or [)
      if ((content.trim().startsWith('{') || content.trim().startsWith('[')) && content.trim().length > 2) {
        try {
          const parsed = JSON.parse(content);
          // If parsed successfully, try to extract meaningful text
          if (typeof parsed === 'object' && parsed !== null) {
            // Try to find text fields in the object
            if (parsed.text) return String(parsed.text);
            if (parsed.content) return String(parsed.content);
            if (parsed.label) return String(parsed.label);
            if (parsed.value) return String(parsed.value);
            if (parsed.title) return String(parsed.title);
            // If no text field found, stringify with formatting
            return JSON.stringify(parsed, null, 2);
          }
          return String(parsed);
        } catch (e) {
          // Not valid JSON, return as-is
          return content;
        }
      }
      return content;
    }
    
    // If it's an object, try to extract text or stringify
    if (typeof content === 'object' && content !== null) {
      if (content.text) return String(content.text);
      if (content.content) return String(content.content);
      if (content.label) return String(content.label);
      if (content.value) return String(content.value);
      if (content.title) return String(content.title);
      // Last resort: stringify the object
      return JSON.stringify(content, null, 2);
    }
    
    return String(content);
  };

  // Render visual devices (timelines, matrices, textboxes, etc.)
  const renderDevice = (device: any) => {
    if (!device || !device.type) {
      console.warn('[renderDevice] Device missing type:', device);
      return (
        <div 
          className="p-4 rounded-lg border border-yellow-300 bg-yellow-50"
          style={{ color: '#92400E' }}
        >
          <p className="text-sm">⚠️ Device missing type information</p>
          {device && (
            <pre className="text-xs mt-2 overflow-auto">
              {JSON.stringify(device, null, 2)}
            </pre>
          )}
        </div>
      );
    }

    switch (device.type) {
      case 'timeline':
        // Parse items if they're JSON strings
        let timelineItems = device.items;
        if (typeof device.items === 'string') {
          try {
            timelineItems = JSON.parse(device.items);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse timeline items:', e);
            timelineItems = [];
          }
        }
        
        if (!timelineItems || !Array.isArray(timelineItems) || timelineItems.length === 0) {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Timeline device has no items</p>
            </div>
          );
        }

        return (
          <div className="relative">
            <div 
              className="absolute left-8 top-0 bottom-0 w-0.5"
              style={{
                background: `linear-gradient(to bottom, ${DECK_DESIGN_TOKENS.colors.foreground}, ${DECK_DESIGN_TOKENS.colors.muted.DEFAULT})`
              }}
            ></div>
            <div className="space-y-8">
              {timelineItems.map((item: any, idx: number) => {
                // Parse item properties if they're JSON strings
                const date = typeof item.date === 'string' && (item.date.startsWith('{') || item.date.startsWith('['))
                  ? parseDeviceContent(item.date) : (item.date || '');
                const event = typeof item.event === 'string' && (item.event.startsWith('{') || item.event.startsWith('['))
                  ? parseDeviceContent(item.event) : (item.event || '');
                
                return (
                  <div key={idx} className="relative flex items-center">
                    <div 
                      className="absolute left-6 w-4 h-4 rounded-full border-2"
                      style={{
                        backgroundColor: item.highlight ? DECK_DESIGN_TOKENS.colors.foreground : DECK_DESIGN_TOKENS.colors.background,
                        borderColor: item.highlight ? DECK_DESIGN_TOKENS.colors.foreground : DECK_DESIGN_TOKENS.colors.border
                      }}
                    ></div>
                    <div className="ml-16">
                      <div className="flex items-center gap-2">
                        <span 
                          className="font-heading"
                          style={{
                            color: item.highlight ? DECK_DESIGN_TOKENS.colors.foreground : DECK_DESIGN_TOKENS.colors.muted.foreground,
                            fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize,
                            fontWeight: DECK_DESIGN_TOKENS.typography.label.fontWeight
                          }}
                        >
                          {date}
                        </span>
                        {item.icon && (
                          <span className="text-lg">{getIcon(item.icon)}</span>
                        )}
                      </div>
                      <div 
                        style={{
                          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                          fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                        }}
                      >
                        {event}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );

      case 'matrix':
        // Parse items if they're JSON strings
        let matrixItems = device.items;
        if (typeof device.items === 'string') {
          try {
            matrixItems = JSON.parse(device.items);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse matrix items:', e);
            matrixItems = [];
          }
        }

        const matrixTitle = parseDeviceContent(device.title || '');
        const xAxis = typeof device.axes?.x === 'string' 
          ? parseDeviceContent(device.axes.x) 
          : (device.axes?.x || '');
        const yAxis = typeof device.axes?.y === 'string' 
          ? parseDeviceContent(device.axes.y) 
          : (device.axes?.y || '');

        return (
          <div 
            className="p-6 rounded-lg"
            style={{
              backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
              borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
            }}
          >
            {matrixTitle && (
              <h3 
                className="font-bold mb-4"
                style={{
                  color: DECK_DESIGN_TOKENS.colors.foreground,
                  fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize,
                  fontWeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontWeight
                }}
              >
                {matrixTitle}
              </h3>
            )}
            <div 
              className="relative h-64 border-2"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                borderColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium,
                borderRadius: DECK_DESIGN_TOKENS.borderRadius.small
              }}
            >
              {xAxis && (
                <div 
                  className="absolute bottom-0 left-0 right-0 text-center font-caption -mb-6"
                  style={{
                    color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                    fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize
                  }}
                >
                  {xAxis}
                </div>
              )}
              {yAxis && (
                <div 
                  className="absolute top-0 bottom-0 left-0 font-caption -ml-12 flex items-center"
                  style={{
                    color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                    fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize
                  }}
                >
                  <span className="transform -rotate-90">{yAxis}</span>
                </div>
              )}
              {matrixItems && Array.isArray(matrixItems) && matrixItems.length > 0 ? (
                matrixItems.map((item: any, idx: number) => {
                  const itemName = typeof item.name === 'string' 
                    ? parseDeviceContent(item.name) 
                    : (item.name || '');
                  
                  return (
                    <div
                      key={idx}
                      className="absolute w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transform -translate-x-1/2 -translate-y-1/2"
                      style={{
                        left: `${item.x || 0}%`,
                        bottom: `${item.y || 0}%`,
                        backgroundColor: item.highlight ? DECK_DESIGN_TOKENS.colors.foreground : DECK_DESIGN_TOKENS.colors.muted.DEFAULT,
                        color: DECK_DESIGN_TOKENS.colors.primary.foreground
                      }}
                      title={itemName}
                    >
                      {itemName?.substring(0, 2) || '?'}
                    </div>
                  );
                })
              ) : (
                <div 
                  className="flex items-center justify-center h-full"
                  style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}
                >
                  <p className="text-sm">Matrix has no items</p>
                </div>
              )}
            </div>
          </div>
        );

      case 'textbox':
        const textboxContent = parseDeviceContent(device.content);
        
        if (!textboxContent || textboxContent.trim() === '') {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Textbox device has no content</p>
            </div>
          );
        }

        return (
          <div 
            className="p-6 rounded-lg border-2"
            style={{
              backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
              borderColor: DECK_DESIGN_TOKENS.colors.border,
              borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
            }}
          >
            <div className="flex items-center justify-between">
              <div 
                className="font-bold"
                style={{ 
                  color: device.color || DECK_DESIGN_TOKENS.colors.foreground,
                  fontSize: DECK_DESIGN_TOKENS.typography.metric.fontSize,
                  fontWeight: DECK_DESIGN_TOKENS.typography.metric.fontWeight
                }}
              >
                {textboxContent}
              </div>
              {device.icon && (
                <span className="text-3xl">{getIcon(device.icon)}</span>
              )}
            </div>
          </div>
        );

      case 'comparison-table':
        // Parse headers and rows if they're JSON strings
        let tableHeaders = device.headers;
        if (typeof device.headers === 'string') {
          try {
            tableHeaders = JSON.parse(device.headers);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse table headers:', e);
            tableHeaders = [];
          }
        }

        let tableRows = device.rows;
        if (typeof device.rows === 'string') {
          try {
            tableRows = JSON.parse(device.rows);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse table rows:', e);
            tableRows = [];
          }
        }

        if (!tableHeaders || !Array.isArray(tableHeaders) || tableHeaders.length === 0) {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Comparison table has no headers</p>
            </div>
          );
        }

        return (
          <div className="overflow-x-auto">
            <table 
              className="min-w-full rounded-lg overflow-hidden"
              style={{
                backgroundColor: DECK_DESIGN_TOKENS.colors.background,
                borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
              }}
            >
              <thead 
                style={{
                  backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT
                }}
              >
                <tr>
                  {tableHeaders.map((header: any, idx: number) => {
                    const headerText = typeof header === 'string' 
                      ? parseDeviceContent(header) 
                      : String(header || '');
                    return (
                      <th 
                        key={idx} 
                        className="px-4 py-3 text-left font-heading"
                        style={{
                          color: DECK_DESIGN_TOKENS.colors.foreground,
                          fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize,
                          fontWeight: DECK_DESIGN_TOKENS.typography.label.fontWeight
                        }}
                      >
                        {headerText}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {tableRows && Array.isArray(tableRows) && tableRows.length > 0 ? (
                  tableRows.map((row: any, ridx: number) => {
                    const rowArray = Array.isArray(row) ? row : (row.cells || []);
                    return (
                      <tr 
                        key={ridx} 
                        style={{
                          backgroundColor: ridx % 2 === 0 ? DECK_DESIGN_TOKENS.colors.secondary.DEFAULT : DECK_DESIGN_TOKENS.colors.background
                        }}
                      >
                        {rowArray.map((cell: any, cidx: number) => {
                          const cellText = typeof cell === 'string' 
                            ? parseDeviceContent(cell) 
                            : String(cell || '');
                          return (
                            <td 
                              key={cidx} 
                              className="px-4 py-3"
                              style={{
                                color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                                fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                              }}
                            >
                              {cellText}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td 
                      colSpan={tableHeaders.length} 
                      className="px-4 py-3 text-center"
                      style={{
                        color: isDarkMode ? '#94A3B8' : '#737373'
                      }}
                    >
                      No rows available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        );

      case 'process-flow':
        // Parse steps if they're JSON strings
        let processSteps = device.steps;
        if (typeof device.steps === 'string') {
          try {
            processSteps = JSON.parse(device.steps);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse process steps:', e);
            processSteps = [];
          }
        }

        if (!processSteps || !Array.isArray(processSteps) || processSteps.length === 0) {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Process flow has no steps</p>
            </div>
          );
        }

        return (
          <div className="flex justify-between items-center">
            {processSteps.map((step: any, idx: number) => {
              const stepLabel = typeof step.label === 'string' 
                ? parseDeviceContent(step.label) 
                : (step.label || '');
              const stepValue = typeof step.value === 'string' 
                ? parseDeviceContent(step.value) 
                : (step.value || '');
              
              return (
                <React.Fragment key={idx}>
                  <div className="flex-1 text-center">
                    <div 
                      className="rounded-lg p-4"
                      style={{
                        backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
                        color: DECK_DESIGN_TOKENS.colors.foreground,
                        borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
                      }}
                    >
                      {stepLabel && (
                        <div 
                          className="font-semibold"
                          style={{
                            fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize,
                            fontWeight: DECK_DESIGN_TOKENS.typography.label.fontWeight,
                            color: DECK_DESIGN_TOKENS.colors.muted.foreground
                          }}
                        >
                          {stepLabel}
                        </div>
                      )}
                      {stepValue && (
                        <div 
                          className="font-bold mt-1"
                          style={{
                            fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize,
                            fontWeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontWeight,
                            color: DECK_DESIGN_TOKENS.colors.foreground
                          }}
                        >
                          {stepValue}
                        </div>
                      )}
                    </div>
                  </div>
                  {idx < processSteps.length - 1 && (
                    <div className="w-8 flex items-center justify-center">
                      <span 
                        style={{
                          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                          fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                        }}
                      >
                        →
                      </span>
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        );

      case 'logo-grid':
        // Parse logos if they're JSON strings
        let logoList = device.logos;
        if (typeof device.logos === 'string') {
          try {
            logoList = JSON.parse(device.logos);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse logo list:', e);
            logoList = [];
          }
        }

        const logoTitle = parseDeviceContent(device.title || '');

        if (!logoList || !Array.isArray(logoList) || logoList.length === 0) {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Logo grid has no logos</p>
            </div>
          );
        }

        return (
          <div>
            {logoTitle && (
              <h3 
                className="text-center font-semibold mb-4"
                style={{
                  color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                  fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize,
                  fontWeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontWeight
                }}
              >
                {logoTitle}
              </h3>
            )}
            <div className="grid grid-cols-3 gap-4">
              {logoList.map((logo: any, idx: number) => {
                const logoValue = typeof logo === 'string' 
                  ? parseDeviceContent(logo) 
                  : (logo.url || logo.src || logo.name || String(logo || ''));
                
                return (
                  <div 
                    key={idx} 
                    className="h-20 rounded flex items-center justify-center"
                    style={{
                      backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
                      borderRadius: DECK_DESIGN_TOKENS.borderRadius.small
                    }}
                  >
                    {logoValue && logoValue.startsWith('http') ? (
                      <img src={logoValue} alt="Logo" className="max-h-12 max-w-full" />
                    ) : (
                      <span 
                        style={{
                          color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                          fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                        }}
                      >
                        {logoValue}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );

      case 'metric-cards':
        // Parse cards if they're JSON strings
        let metricCards = device.cards;
        if (typeof device.cards === 'string') {
          try {
            metricCards = JSON.parse(device.cards);
          } catch (e) {
            console.warn('[renderDevice] Failed to parse metric cards:', e);
            metricCards = [];
          }
        }

        if (!metricCards || !Array.isArray(metricCards) || metricCards.length === 0) {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Metric cards device has no cards</p>
            </div>
          );
        }

        return (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {metricCards.map((card: any, idx: number) => {
              const cardMetric = typeof card.metric === 'string' 
                ? parseDeviceContent(card.metric) 
                : (card.metric || '');
              const cardLabel = typeof card.label === 'string' 
                ? parseDeviceContent(card.label) 
                : (card.label || '');
              const cardChange = typeof card.change === 'string' 
                ? parseDeviceContent(card.change) 
                : (card.change || '');
              
              return (
                <div 
                  key={idx} 
                  className="p-6 rounded-lg border"
                  style={{
                    backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
                    borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium,
                    borderColor: DECK_DESIGN_TOKENS.colors.border,
                    boxShadow: DECK_DESIGN_TOKENS.shadows.subtle
                  }}
                >
                  {cardMetric && (
                    <div 
                      className="font-bold"
                      style={{
                        color: DECK_DESIGN_TOKENS.colors.foreground,
                        fontSize: DECK_DESIGN_TOKENS.typography.metric.fontSize,
                        fontWeight: DECK_DESIGN_TOKENS.typography.metric.fontWeight
                      }}
                    >
                      {cardMetric}
                    </div>
                  )}
                  {cardLabel && (
                    <div 
                      className="mt-1"
                      style={{
                        color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                        fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize,
                        fontWeight: DECK_DESIGN_TOKENS.typography.label.fontWeight
                      }}
                    >
                      {cardLabel}
                    </div>
                  )}
                  {cardChange && (
                    <div 
                      className="font-semibold mt-2"
                      style={{
                        color: cardChange.startsWith('+') ? DECK_DESIGN_TOKENS.colors.success : DECK_DESIGN_TOKENS.colors.error,
                        fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                      }}
                    >
                      {cardChange}
                    </div>
                  )}
                  {card.sparkline && Array.isArray(card.sparkline) && card.sparkline.length > 0 && (
                    <div className="mt-2 flex items-end h-8 gap-1">
                      {card.sparkline.map((val: number, sidx: number) => (
                        <div
                          key={sidx}
                          className="rounded-t"
                          style={{
                            backgroundColor: DECK_DESIGN_TOKENS.colors.chart[sidx % DECK_DESIGN_TOKENS.colors.chart.length],
                            height: `${(val / Math.max(...card.sparkline)) * 100}%`
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );

      case 'quote':
        const quoteText = parseDeviceContent(device.text || device.content || '');
        const quoteAuthor = typeof device.author === 'string' 
          ? parseDeviceContent(device.author) 
          : (device.author || '');

        if (!quoteText || quoteText.trim() === '') {
          return (
            <div 
              className="p-4 rounded-lg border border-gray-300"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                color: isDarkMode ? '#94A3B8' : '#737373'
              }}
            >
              <p className="text-sm">Quote device has no text</p>
            </div>
          );
        }

        return (
          <div 
            className="p-6 rounded-lg border-l-4"
            style={{
              backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
              borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium,
              borderLeftColor: DECK_DESIGN_TOKENS.colors.foreground
            }}
          >
            <div 
              className="italic mb-4"
              style={{
                color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize,
                lineHeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.lineHeight
              }}
            >
              "{quoteText}"
            </div>
            {quoteAuthor && (
              <div className="flex items-center gap-3">
                {device.logo && (
                  <img src={device.logo} alt="Company" className="h-8" />
                )}
                <div 
                  style={{
                    color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                    fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                  }}
                >
                  — {quoteAuthor}
                </div>
              </div>
            )}
          </div>
        );

      default:
        // For unknown device types, try to render a generic device
        console.warn(`[renderDevice] Unknown device type: ${device.type}`, device);
        
        // Try to extract any meaningful content
        const genericContent = parseDeviceContent(
          device.content || device.text || device.label || device.value || ''
        );
        const genericTitle = parseDeviceContent(device.title || device.name || '');

        return (
          <div 
            className="p-6 rounded-lg border-2 border-dashed"
            style={{
              backgroundColor: isDarkMode 
                ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                : DECK_DESIGN_TOKENS.colors.light.surface.card,
              borderColor: isDarkMode 
                ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                : DECK_DESIGN_TOKENS.colors.light.border.medium,
              borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
            }}
          >
            {genericTitle && (
              <h3 
                className="font-bold mb-2"
                style={{
                  color: isDarkMode 
                    ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                    : DECK_DESIGN_TOKENS.colors.light.text.primary,
                  fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize
                }}
              >
                {genericTitle}
              </h3>
            )}
            {genericContent && genericContent.trim() !== '' ? (
              <div 
                style={{
                  color: isDarkMode 
                    ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                    : DECK_DESIGN_TOKENS.colors.light.text.secondary,
                  fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize
                }}
              >
                {genericContent}
              </div>
            ) : (
              <div 
                className="text-sm"
                style={{
                  color: isDarkMode ? '#94A3B8' : '#737373'
                }}
              >
                <p className="mb-2">⚠️ Unknown device type: <code>{device.type}</code></p>
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs">View device data</summary>
                  <pre className="text-xs mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded overflow-auto max-h-48">
                    {JSON.stringify(device, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </div>
        );
    }
  };

  // Helper function for icons
  const getIcon = (iconName: string) => {
    const icons: any = {
      'rocket': <Zap className="w-5 h-5" />,
      'trending-up': <TrendingUp className="w-5 h-5" />,
      'seedling': <Target className="w-5 h-5" />,
      'users': <Users className="w-5 h-5" />,
      'target': <Target className="w-5 h-5" />,
      'check': <Check className="w-5 h-5" />,
      'star': <Star className="w-5 h-5" />,
      'chart': <BarChart3 className="w-5 h-5" />,
      'dollar': <DollarSign className="w-5 h-5" />,
      'calendar': <Calendar className="w-5 h-5" />,
      'globe': <Globe className="w-5 h-5" />,
      'lightning': <Zap className="w-5 h-5" />
    };
    return icons[iconName] || <div className="w-5 h-5 bg-gray-300 rounded-full" />;
  };

  // Helper function to extract chart data consistently
  const extractChartData = (slide: Slide): { type: string; data: any; title?: string } | null => {
    if (!slide?.content) return null;
    
    // Priority 1: content.chart_data
    if (slide.content.chart_data && slide.content.chart_data.type) {
      return {
        type: slide.content.chart_data.type,
        data: slide.content.chart_data.data || slide.content.chart_data,
        title: slide.content.chart_data.title || slide.content.title
      };
    }
    
    // Priority 2: content.charts array (first chart)
    if (slide.content.charts && Array.isArray(slide.content.charts) && slide.content.charts.length > 0) {
      const firstChart = slide.content.charts[0];
      return {
        type: firstChart.type || 'bar',
        data: firstChart.data || firstChart,
        title: firstChart.title || slide.content.title
      };
    }
    
    // Priority 3: content.sankey_data (legacy)
    if (slide.content.sankey_data) {
      return {
        type: 'sankey',
        data: slide.content.sankey_data,
        title: slide.content.title
      };
    }
    
    return null;
  };

  const renderSlideContent = (slide: Slide) => {
    // Safety check for slide content
    if (!slide || !slide.content) {
      const fallbackBg = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.background.primary 
        : DECK_DESIGN_TOKENS.colors.light.background.primary;
      const fallbackText = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
        : DECK_DESIGN_TOKENS.colors.light.text.secondary;
      return (
        <div 
          className="h-full flex flex-col p-8"
          style={{ 
            background: fallbackBg,
            color: fallbackText
          }}
        >
          <div>No content available for this slide</div>
        </div>
      );
    }

    // Get theme styles using design tokens - make theme-aware
    let bgStyle: string;
    if (slide.theme?.background) {
      bgStyle = slide.theme.background;
    } else if (slide.template === 'title') {
      bgStyle = isDarkMode 
        ? `linear-gradient(135deg, ${DECK_DESIGN_TOKENS.colors.dark.background.secondary} 0%, ${DECK_DESIGN_TOKENS.colors.dark.background.tertiary} 100%)`
        : `linear-gradient(135deg, ${DECK_DESIGN_TOKENS.colors.foreground} 0%, ${DECK_DESIGN_TOKENS.colors.muted.DEFAULT} 100%)`;
    } else {
      bgStyle = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.background.primary 
        : DECK_DESIGN_TOKENS.colors.light.background.primary;
    }
    
    let titleColor: string;
    if (slide.theme?.titleColor) {
      titleColor = slide.theme.titleColor;
    } else if (slide.template === 'title') {
      titleColor = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
        : DECK_DESIGN_TOKENS.colors.primary.foreground;
    } else {
      titleColor = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
        : DECK_DESIGN_TOKENS.colors.foreground;
    }
    
    let textColor: string;
    if (slide.theme?.textColor) {
      textColor = slide.theme.textColor;
    } else if (slide.template === 'title') {
      textColor = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
        : DECK_DESIGN_TOKENS.colors.muted.foreground;
    } else {
      textColor = isDarkMode 
        ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
        : DECK_DESIGN_TOKENS.colors.light.text.secondary;
    }

    return (
      <div 
        className="h-full flex flex-col"
        style={{ 
          background: bgStyle,
          color: textColor || (isDarkMode ? '#E2E8F0' : '#0A0A0A'),
          padding: '40px 56px',
          boxSizing: 'border-box',
          overflow: 'auto',
          maxHeight: '100%'
        }}
      >
        {/* Slide Header */}
        <div className="mb-6 flex-shrink-0">
          <h2 
            className="font-bold mb-2" 
            style={{ 
              color: titleColor || (isDarkMode ? '#E2E8F0' : '#0A0A0A'),
              fontSize: DECK_DESIGN_TOKENS.typography.slideTitle.fontSize || '2rem',
              fontWeight: DECK_DESIGN_TOKENS.typography.slideTitle.fontWeight || 700,
              lineHeight: DECK_DESIGN_TOKENS.typography.slideTitle.lineHeight || 1.2,
              letterSpacing: DECK_DESIGN_TOKENS.typography.slideTitle.letterSpacing || 'normal'
            }}
          >
            {slide.content.title || 'Untitled Slide'}
          </h2>
          {slide.content.subtitle && (
            <p 
              className="mt-3 mb-4" 
              style={{ 
                color: textColor || (isDarkMode ? '#E2E8F0' : '#0A0A0A'), 
                opacity: 0.9,
                fontSize: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontSize,
                fontWeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.fontWeight,
                lineHeight: DECK_DESIGN_TOKENS.typography.slideSubtitle.lineHeight
              }}
            >
              {slide.content.subtitle}
            </p>
          )}
        </div>

        {/* Slide Body */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden" style={{ minHeight: 0 }}>
          {slide.content.body && (
            <p 
              className="mb-6 leading-relaxed" 
              style={{
                fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize || '1rem',
                fontWeight: DECK_DESIGN_TOKENS.typography.body.fontWeight || 400,
                lineHeight: DECK_DESIGN_TOKENS.typography.body.lineHeight || 1.6,
                color: textColor || (isDarkMode ? '#E2E8F0' : '#0A0A0A')
              }}
            >
              {slide.content.body}
            </p>
          )}

          {slide.content.bullets && slide.content.bullets.length > 0 && (
            <ul className="space-y-4 mb-6">
              {slide.content.bullets.map((bullet, idx) => (
                <li key={idx} className="flex items-start">
                  <span 
                    className="mr-4 mt-1.5 flex-shrink-0" 
                    style={{ 
                      color: isDarkMode 
                        ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                        : DECK_DESIGN_TOKENS.colors.foreground,
                      fontSize: '1.25rem',
                      lineHeight: 1
                    }}
                  >
                    •
                  </span>
                  <span 
                    className="leading-relaxed"
                    style={{ 
                      color: textColor || (isDarkMode ? '#E2E8F0' : '#0A0A0A'),
                      fontSize: DECK_DESIGN_TOKENS.typography.body.fontSize || '1rem',
                      lineHeight: DECK_DESIGN_TOKENS.typography.body.lineHeight || 1.6
                    }}
                  >
                    {bullet}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {slide.content.metrics && Object.keys(slide.content.metrics).length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6">
              {Object.entries(slide.content.metrics).map(([key, value]) => {
                // Handle different types of metric values - use formatMetricValue utility
                let displayValue: string;
                let sourceInfo = null;
                
                // If value is an object, extract meaningful fields before formatting
                if (typeof value === 'object' && value !== null) {
                  // Extract source info if present
                  if ('source' in value) {
                    sourceInfo = value.source;
                  }
                  
                  // Try to extract display value in priority order: value, amount, label, text, name
                  let extractedValue = value;
                  if ('value' in value) {
                    extractedValue = value.value;
                  } else if ('amount' in value) {
                    extractedValue = value.amount;
                  } else if ('label' in value) {
                    extractedValue = value.label;
                  } else if ('text' in value) {
                    extractedValue = value.text;
                  } else if ('name' in value) {
                    extractedValue = value.name;
                  } else {
                    // Try to find first numeric or string value
                    const firstValue = Object.values(value).find(v => 
                      typeof v === 'number' || typeof v === 'string'
                    );
                    if (firstValue !== undefined) {
                      extractedValue = firstValue;
                    }
                  }
                  
                  // If still an object after extraction, use formatMetricValue which handles it
                  // Otherwise format the extracted value
                  if (typeof extractedValue === 'object' && extractedValue !== null) {
                    displayValue = formatMetricValue(key, extractedValue);
                  } else {
                    displayValue = formatMetricValue(key, extractedValue);
                  }
                } else {
                  // Use formatMetricValue for proper formatting (currency, percentage, etc.)
                  displayValue = formatMetricValue(key, value);
                }
                
                return (
                  <div 
                    key={key} 
                    className="p-4 rounded-lg"
                    style={{
                      backgroundColor: isDarkMode 
                        ? DECK_DESIGN_TOKENS.colors.dark.surface.elevated 
                        : DECK_DESIGN_TOKENS.colors.light.surface.elevated,
                      borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium,
                      boxShadow: isDarkMode 
                        ? DECK_DESIGN_TOKENS.shadows.dark.subtle 
                        : DECK_DESIGN_TOKENS.shadows.light.subtle
                    }}
                  >
                    <div 
                      className="text-sm"
                      style={{
                        color: isDarkMode ? '#94A3B8' : '#525252',
                        fontSize: DECK_DESIGN_TOKENS.typography.label.fontSize,
                        fontWeight: DECK_DESIGN_TOKENS.typography.label.fontWeight,
                        textTransform: DECK_DESIGN_TOKENS.typography.label.textTransform,
                        letterSpacing: DECK_DESIGN_TOKENS.typography.label.letterSpacing
                      }}
                    >
                      {key}
                    </div>
                    <div 
                      className="font-bold"
                      style={{
                        color: isDarkMode ? '#E2E8F0' : '#0A0A0A',
                        fontSize: DECK_DESIGN_TOKENS.typography.metric.fontSize,
                        fontWeight: DECK_DESIGN_TOKENS.typography.metric.fontWeight,
                        lineHeight: DECK_DESIGN_TOKENS.typography.metric.lineHeight,
                        letterSpacing: DECK_DESIGN_TOKENS.typography.metric.letterSpacing
                      }}
                    >
                      {String(displayValue)}
                    </div>
                    {sourceInfo && (
                      <div 
                        className="mt-1"
                        style={{
                          color: isDarkMode ? '#94A3B8' : '#737373',
                          fontSize: '0.75rem'
                        }}
                      >
                        Source: {sourceInfo}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Render Visual Devices */}
          {(() => {
            // Debug: Log device information
            const devices = slide.content?.devices || slide.content?.visual_devices || slide.devices || [];
            
            // Also check if devices are nested in content directly (not in content.devices)
            if (!devices || devices.length === 0) {
              // Check for devices in various possible locations
              const possibleDevices = 
                slide.content?.devices ||
                slide.content?.visual_devices ||
                slide.devices ||
                (slide.content?.type === 'textbox' || slide.content?.type === 'matrix' || slide.content?.type === 'timeline' ? [slide.content] : []) ||
                [];
              
              if (possibleDevices.length > 0) {
                console.log('[renderSlideContent] Found devices in alternative location:', {
                  slideId: slide.id,
                  template: slide.template,
                  devices: possibleDevices,
                  contentKeys: Object.keys(slide.content || {})
                });
                return possibleDevices.map((device: any, idx: number) => (
                  <div key={idx} className="mt-6">
                    {renderDevice(device)}
                  </div>
                ));
              }
              
              // Debug log when no devices found
              if (slide.content && (slide.content.chart_data || slide.template === 'chart' || slide.template === 'visual')) {
                console.log('[renderSlideContent] Slide has chart/visual template but no devices:', {
                  slideId: slide.id,
                  template: slide.template,
                  hasChartData: !!slide.content.chart_data,
                  contentKeys: Object.keys(slide.content),
                  content: JSON.stringify(slide.content).substring(0, 200)
                });
              }
              
              return null;
            }
            
            return devices.map((device: any, idx: number) => {
              // Debug log for each device
              if (idx === 0) {
                console.log('[renderSlideContent] Rendering devices:', {
                  slideId: slide.id,
                  deviceCount: devices.length,
                  firstDevice: device
                });
              }
              
              return (
                <div key={idx} className="mt-6">
                  {renderDevice(device)}
                </div>
              );
            });
          })()}

          {/* Cap Table Handling */}
          {(slide.template === 'cap_table' || slide.content.sankey_data || slide.content.cap_table_data) && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-chart-type="sankey"
              data-testid="cap-table-container"
            >
              {slide.content.sankey_data ? (
                <div data-testid="cap-table-sankey">
                  <TableauLevelCharts 
                    type="sankey"
                    data={slide.content.sankey_data}
                    title={slide.content.title || "Cap Table"}
                    height={400}
                  />
                </div>
              ) : slide.content.chart_data ? (
                <div data-testid="cap-table-chart">
                  {slide.content.chart_data.type && ['sankey', 'side_by_side_sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'funnel', 'probability_cloud', 'timeline_valuation', 'pie'].includes(slide.content.chart_data.type.toLowerCase()) ? (
                    <TableauLevelCharts 
                      type={slide.content.chart_data.type as any}
                      data={slide.content.chart_data.data}
                      title={slide.content.chart_data.title}
                      height={400}
                    />
                  ) : slide.content.chart_data.type === 'image' && slide.content.chart_data.original_data ? (
                    // Handle prerendered image with original data
                    (() => {
                      const originalData = slide.content.chart_data.original_data;
                      if (originalData.type && ['sankey', 'side_by_side_sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'funnel', 'probability_cloud', 'timeline_valuation', 'pie'].includes(originalData.type.toLowerCase())) {
                        return (
                          <TableauLevelCharts 
                            type={originalData.type as any}
                            data={originalData.data}
                            title={originalData.title || slide.content.title}
                            height={400}
                          />
                        );
                      }
                      return (
                        <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                          Cap table chart data format not supported
                        </div>
                      );
                    })()
                  ) : (
                    <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                      Cap table chart data format not supported: {slide.content.chart_data?.type || 'unknown'}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Cap table data is missing
                </div>
              )}

              {/* Future Ownership Scenarios */}
              {slide.content.future_chart_data && (
                <div className="mt-8 pt-8" style={{ borderTop: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                  <h3 className="text-lg font-semibold mb-4" style={{ color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary }}>
                    Future Ownership Scenarios
                  </h3>
                  <div data-testid="recharts-container" data-chart-type={slide.content.future_chart_data?.type || 'bar'}>
                    {(() => {
                      try {
                        const chartType = slide.content.future_chart_data?.type?.toLowerCase() || 'bar';
                        const chartData = slide.content.future_chart_data?.data;
                        
                        if (!chartData) {
                          return (
                            <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>No chart data available</p>
                              </div>
                            </div>
                          );
                        }
                        
                        const labels = chartData?.labels || [];
                        let formattedData: any[] = [];
                    
                        if (chartData?.datasets && Array.isArray(chartData.datasets)) {
                          formattedData = labels.map((label: string, index: number) => {
                            const dataPoint: any = { name: label || `Item ${index + 1}` };
                            chartData.datasets.forEach((dataset: any) => {
                              const key = dataset.label || 'value';
                              dataPoint[key] = dataset.data?.[index] ?? 0;
                            });
                            return dataPoint;
                          });
                        }
                        
                        if (!formattedData || formattedData.length === 0) {
                          return (
                            <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>Unable to format chart data</p>
                              </div>
                            </div>
                          );
                        }
                    
                        const COLORS = isDarkMode 
                          ? [
                              '#10B981', // Green - Our Fund
                              '#3B82F6', // Blue - Founders
                              '#F59E0B', // Amber - Employees
                              '#8B5CF6', // Purple - Other Investors
                            ]
                          : [
                              '#059669', // Green - Our Fund
                              '#3B82F6', // Blue - Founders
                              '#D97706', // Amber - Employees
                              '#7C3AED', // Purple - Other Investors
                            ];
                    
                        const textColor = isDarkMode 
                          ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                          : DECK_DESIGN_TOKENS.colors.light.text.secondary;
                        const gridColor = isDarkMode 
                          ? DECK_DESIGN_TOKENS.colors.dark.border.subtle 
                          : DECK_DESIGN_TOKENS.colors.light.border.subtle;
                        
                        const barKeys = (formattedData.length > 0 && formattedData[0]) ? 
                          Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                        
                        return (
                          <ResponsiveContainer width="100%" height={400}>
                            <BarChart data={formattedData}>
                              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                              <XAxis 
                                dataKey="name" 
                                tick={{ fill: textColor }}
                                stroke={gridColor}
                                angle={-45}
                                textAnchor="end"
                                height={100}
                              />
                              <YAxis 
                                tick={{ fill: textColor }}
                                stroke={gridColor}
                                domain={[0, 100]}
                              />
                              <Tooltip 
                                contentStyle={{
                                  backgroundColor: isDarkMode 
                                    ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                    : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                  border: `1px solid ${gridColor}`,
                                  color: textColor
                                }}
                              />
                              <Legend wrapperStyle={{ color: textColor }} />
                              {barKeys.map((key, idx) => (
                              <Bar 
                                key={key}
                                dataKey={key} 
                                fill={COLORS[idx % COLORS.length]}
                                radius={[4, 4, 0, 0]}
                                stackId="ownership"
                              />
                            ))}
                            </BarChart>
                          </ResponsiveContainer>
                        );
                      } catch (error) {
                        console.error('Error rendering future chart:', error);
                        return (
                          <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                            <div className="text-center">
                              <p>Error rendering chart</p>
                              <p className="text-sm mt-2">{String(error)}</p>
                            </div>
                          </div>
                        );
                      }
                    })()}
                  </div>
                </div>
              )}

              {/* Future Pie Charts Array */}
              {slide.content.future_pie_charts && slide.content.future_pie_charts.length > 0 && (
                <div className="mt-8 pt-8" style={{ borderTop: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                  <h3 className="text-lg font-semibold mb-4" style={{ color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary }}>
                    Future Ownership Scenarios
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {slide.content.future_pie_charts.map((futurePie: any, idx: number) => {
                      // Format pie chart data - handle Chart.js format {labels, datasets} or direct array
                      const pieData = futurePie.data || futurePie;
                      let formattedData: any[] = [];
                      
                      if (pieData.labels && pieData.datasets && Array.isArray(pieData.datasets) && pieData.datasets.length > 0) {
                        // Chart.js format: {labels: [], datasets: [{data: []}]}
                        const labels = pieData.labels || [];
                        const dataset = pieData.datasets[0];
                        const values = dataset.data || [];
                        formattedData = labels.map((label: string, i: number) => ({
                          name: label,
                          value: typeof values[i] === 'number' ? values[i] : parseFloat(values[i]) || 0
                        }));
                      } else if (Array.isArray(pieData)) {
                        formattedData = pieData.map((item: any) => ({
                          name: item.name || item.label || String(item),
                          value: typeof item.value === 'number' ? item.value : parseFloat(item.value) || 0
                        }));
                      }
                      
                      const COLORS = isDarkMode 
                        ? [
                            DECK_DESIGN_TOKENS.colors.dark.accent.cyan,
                            DECK_DESIGN_TOKENS.colors.dark.accent.blue,
                            '#10B981', // Green
                            '#F59E0B', // Amber
                            '#EF4444', // Red
                            '#8B5CF6', // Purple
                          ]
                        : [
                            '#0A0A0A', // Obsidian black
                            '#3B82F6', // Blue
                            '#059669', // Green
                            '#D97706', // Amber
                            '#DC2626', // Red
                            '#7C3AED', // Purple
                          ];
                      
                      return (
                        <div 
                          key={idx} 
                          className="p-4 rounded-lg border"
                          style={{
                            backgroundColor: isDarkMode 
                              ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                              : DECK_DESIGN_TOKENS.colors.light.surface.card,
                            border: `1px solid ${isDarkMode 
                              ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                              : DECK_DESIGN_TOKENS.colors.light.border.medium}`
                          }}
                        >
                          {futurePie.title && (
                            <h4 className="text-md font-semibold mb-3" style={{ color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary }}>
                              {futurePie.title}
                            </h4>
                          )}
                          <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                              <Pie
                                data={formattedData}
                                cx="50%"
                                cy="50%"
                                labelLine={false}
                                label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                outerRadius={80}
                                fill={COLORS[0]}
                                dataKey="value"
                              >
                                {formattedData.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                              </Pie>
                              <Tooltip 
                                contentStyle={{
                                  backgroundColor: isDarkMode 
                                    ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                    : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                  border: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}`,
                                  color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary
                                }}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Template-specific handlers for advanced charts */}
          {slide.template === 'scoring_matrix' && slide.content.chart_data && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="scoring-matrix-container"
            >
              {slide.content.chart_data ? (
                (() => {
                  try {
                    // Handle prerendered image
                    if (slide.content.chart_data.type === 'image' && slide.content.chart_data.original_data) {
                      const originalData = slide.content.chart_data.original_data;
                      if (originalData.type === 'heatmap') {
                        // Fix the data before rendering
                        const fixed = fixHeatmapData(originalData.data);
                        if (fixed.fixed) {
                          console.log('Scoring matrix: Fixed prerendered heatmap data:', fixed.fixes);
                        }
                        if (fixed.data && (fixed.data.dimensions || fixed.data.length > 0)) {
                          return (
                            <>
                              <TableauLevelCharts 
                                type="heatmap"
                                data={fixed.data}
                                title={originalData.title || slide.content.title}
                                height={400}
                              />
                              {slide.content.metrics && (
                                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                                  {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                    <div key={key}>
                                      <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {slide.content.body && (
                                <div className="mt-4 p-3 rounded-lg text-sm" style={{ 
                                  backgroundColor: isDarkMode ? 'rgba(59, 130, 246, 0.1)' : 'rgba(59, 130, 246, 0.05)',
                                  color: isDarkMode ? '#94A3B8' : '#4B5563'
                                }}>
                                  {slide.content.body}
                                </div>
                              )}
                            </>
                          );
                        }
                      }
                      console.warn('Scoring matrix: prerendered image has invalid original_data:', {
                        originalType: originalData.type,
                        hasData: !!originalData.data
                      });
                    }
                    // Handle raw chart_data
                    if (slide.content.chart_data.type === 'heatmap') {
                      // Fix the data before rendering
                      const fixed = fixHeatmapData(slide.content.chart_data.data);
                      if (fixed.fixed) {
                        console.log('Scoring matrix: Fixed heatmap data:', fixed.fixes);
                      }
                      if (fixed.data && (fixed.data.dimensions || fixed.data.length > 0)) {
                        return (
                          <>
                            <TableauLevelCharts 
                              type="heatmap"
                              data={fixed.data}
                              title={slide.content.chart_data.title || slide.content.title}
                              height={400}
                            />
                            {slide.content.metrics && (
                              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                                {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                  <div key={key}>
                                    <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                  </div>
                                ))}
                              </div>
                            )}
                            {slide.content.body && (
                              <div className="mt-4 p-3 rounded-lg text-sm" style={{ 
                                backgroundColor: isDarkMode ? 'rgba(59, 130, 246, 0.1)' : 'rgba(59, 130, 246, 0.05)',
                                color: isDarkMode ? '#94A3B8' : '#4B5563'
                              }}>
                                {slide.content.body}
                              </div>
                            )}
                          </>
                        );
                      }
                    }
                    // Try to fix the entire chart_data object
                    const fixedChart = fixChartDataObject(slide.content.chart_data);
                    if (fixedChart && fixedChart.fixed && fixedChart.type === 'heatmap') {
                      console.log('Scoring matrix: Fixed chart_data object:', fixedChart.fixes);
                      const fixed = fixHeatmapData(fixedChart.data);
                      if (fixed.data && (fixed.data.dimensions || fixed.data.length > 0)) {
                        return (
                          <>
                            <TableauLevelCharts 
                              type="heatmap"
                              data={fixed.data}
                              title={fixedChart.title || slide.content.title}
                              height={400}
                            />
                            {slide.content.metrics && (
                              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                                {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                  <div key={key}>
                                    <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                  </div>
                                ))}
                              </div>
                            )}
                            {slide.content.body && (
                              <div className="mt-4 p-3 rounded-lg text-sm" style={{ 
                                backgroundColor: isDarkMode ? 'rgba(59, 130, 246, 0.1)' : 'rgba(59, 130, 246, 0.05)',
                                color: isDarkMode ? '#94A3B8' : '#4B5563'
                              }}>
                                {slide.content.body}
                              </div>
                            )}
                          </>
                        );
                      }
                    }
                    console.warn('Scoring matrix: chart data structure is invalid:', {
                      type: slide.content.chart_data?.type,
                      hasData: !!slide.content.chart_data?.data,
                      hasOriginalData: !!slide.content.chart_data?.original_data
                    });
                    return (
                      <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                        Scoring matrix chart data is missing or invalid
                      </div>
                    );
                  } catch (error) {
                    console.error('Error rendering scoring matrix chart:', error);
                    return (
                      <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                        Error rendering scoring matrix chart
                      </div>
                    );
                  }
                })()
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Scoring matrix chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'cap_table_forward_looking' && slide.content.chart_data && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="cap-table-forward-looking-container"
            >
              {slide.content.chart_data.type === 'side_by_side_sankey' && slide.content.chart_data.data ? (
                <>
                  <TableauLevelCharts 
                    type="side_by_side_sankey"
                    data={slide.content.chart_data.data}
                    title={slide.content.chart_data.title || slide.content.title}
                    height={400}
                  />
                  {slide.content.insights && (
                    <div className="mt-4 text-sm" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                      {slide.content.insights}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Cap table forward looking chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'path_to_100m_comparison' && slide.content.chart_data && (
            <div 
              className="mt-8 p-6 rounded-xl shadow-sm"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-chart-type={slide.content.chart_data.type}
              data-testid="path-to-100m-chart-container"
            >
              {slide.content.chart_data.type === 'image' ? (
                (() => {
                  // Check if we have original_data for line chart rendering
                  if (slide.content.chart_data.original_data) {
                    const originalData = slide.content.chart_data.original_data;
                    if (originalData.type === 'line') {
                      // Fix the data before rendering
                      const fixed = fixLineChartData(originalData.data);
                      if (fixed.fixed) {
                        console.log('Path to $100M: Fixed prerendered line chart data:', fixed.fixes);
                      }
                      if (fixed.data && fixed.data.labels && fixed.data.datasets) {
                        // Render line chart from fixed original_data
                        return (
                          <div data-testid="line-chart-container" data-chart-type="line">
                            {(() => {
                              try {
                                const chartData = fixed.data;
                                const labels = chartData.labels || [];
                                let formattedData: any[] = [];
                          
                                if (chartData.datasets && Array.isArray(chartData.datasets)) {
                                  formattedData = labels.map((label: string, index: number) => {
                                    const dataPoint: any = { name: label || `Period ${index + 1}` };
                                    chartData.datasets.forEach((dataset: any) => {
                                      const key = dataset.label || 'value';
                                      dataPoint[key] = dataset.data?.[index] ?? 0;
                                    });
                                    return dataPoint;
                                  });
                                }
                              
                                if (!formattedData || formattedData.length === 0) {
                                  return (
                                    <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                      <div className="text-center">
                                        <p>Unable to format chart data</p>
                                      </div>
                                    </div>
                                  );
                                }
                          
                                const COLORS = isDarkMode 
                                  ? ['#0EA5E9', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
                                  : ['#0A0A0A', '#3B82F6', '#059669', '#D97706', '#DC2626', '#7C3AED'];
                          
                                const textColor = isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                                  : DECK_DESIGN_TOKENS.colors.light.text.secondary;
                                const gridColor = isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.border.subtle 
                                  : DECK_DESIGN_TOKENS.colors.light.border.subtle;
                              
                                const lineKeys = (formattedData.length > 0 && formattedData[0]) ? 
                                  Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                              
                                return (
                                  <ResponsiveContainer width="100%" height={400}>
                                    <LineChart data={formattedData}>
                                      <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                                      <XAxis 
                                        dataKey="name" 
                                        tick={{ fill: textColor }}
                                        stroke={gridColor}
                                      />
                                      <YAxis 
                                        tick={{ fill: textColor }}
                                        stroke={gridColor}
                                      />
                                      <Tooltip 
                                        contentStyle={{
                                          backgroundColor: isDarkMode 
                                            ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                            : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                          border: `1px solid ${gridColor}`,
                                          color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary
                                        }}
                                      />
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
                                  </ResponsiveContainer>
                                );
                              } catch (error) {
                                console.error('Error rendering path to 100M chart from original_data:', error);
                                return (
                                  <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <div className="text-center">
                                      <p>Error rendering chart</p>
                                    </div>
                                  </div>
                                );
                              }
                            })()}
                          </div>
                        );
                      }
                    }
                  }
                  // Fallback to image if src exists
                  if (!slide.content.chart_data.src) {
                    console.warn('Path to $100M: image type but no src or valid original_data:', {
                      hasSrc: !!slide.content.chart_data.src,
                      hasOriginalData: !!slide.content.chart_data.original_data,
                      originalDataType: slide.content.chart_data.original_data?.type
                    });
                  }
                  return (
                    <div data-testid="prerendered-chart">
                      {slide.content.chart_data.src ? (
                        <img 
                          src={slide.content.chart_data.src} 
                          alt={slide.content.chart_data.alt || 'Path to 100M Chart'} 
                          className="w-full h-auto"
                          style={{ maxHeight: '400px', objectFit: 'contain' }}
                        />
                      ) : (
                        <div className="text-center py-8 text-gray-500">
                          Chart image source missing
                        </div>
                      )}
                    </div>
                  );
                })()
              ) : slide.content.chart_data.data ? (
                <>
                  {slide.content.chart_data.type === 'line' ? (
                    <div data-testid="line-chart-container" data-chart-type="line">
                      {(() => {
                        try {
                          // Fix the data before processing
                          const fixed = fixLineChartData(slide.content.chart_data.data);
                          if (fixed.fixed) {
                            console.log('Path to $100M: Fixed line chart data:', fixed.fixes);
                          }
                          const chartData = fixed.data;
                          const labels = chartData?.labels || [];
                          let formattedData: any[] = [];
                      
                          if (chartData?.datasets && Array.isArray(chartData.datasets)) {
                            formattedData = labels.map((label: string, index: number) => {
                              const dataPoint: any = { name: label || `Period ${index + 1}` };
                              chartData.datasets.forEach((dataset: any) => {
                                const key = dataset.label || 'value';
                                dataPoint[key] = dataset.data?.[index] ?? 0;
                              });
                              return dataPoint;
                            });
                          }
                          
                          if (!formattedData || formattedData.length === 0) {
                            return (
                              <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                <div className="text-center">
                                  <p>Unable to format chart data</p>
                                </div>
                              </div>
                            );
                          }
                      
                          const COLORS = isDarkMode 
                            ? ['#0EA5E9', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
                            : ['#0A0A0A', '#3B82F6', '#059669', '#D97706', '#DC2626', '#7C3AED'];
                      
                          const textColor = isDarkMode 
                            ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                            : DECK_DESIGN_TOKENS.colors.light.text.secondary;
                          const gridColor = isDarkMode 
                            ? DECK_DESIGN_TOKENS.colors.dark.border.subtle 
                            : DECK_DESIGN_TOKENS.colors.light.border.subtle;
                          
                          const lineKeys = (formattedData.length > 0 && formattedData[0]) ? 
                            Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                          
                          return (
                            <ResponsiveContainer width="100%" height={400}>
                              <LineChart data={formattedData}>
                                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                                <XAxis 
                                  dataKey="name" 
                                  tick={{ fill: textColor }}
                                  stroke={gridColor}
                                />
                                <YAxis 
                                  tick={{ fill: textColor }}
                                  stroke={gridColor}
                                />
                                <Tooltip 
                                  contentStyle={{
                                    backgroundColor: isDarkMode 
                                      ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                      : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                    border: `1px solid ${gridColor}`,
                                    color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary
                                  }}
                                />
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
                            </ResponsiveContainer>
                          );
                        } catch (error) {
                          console.error('Error rendering path to 100M chart:', error);
                          return (
                            <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>Error rendering chart</p>
                              </div>
                            </div>
                          );
                        }
                      })()}
                    </div>
                  ) : (
                    <TableauLevelCharts 
                      type={slide.content.chart_data.type as any}
                      data={slide.content.chart_data.data}
                      title={slide.content.chart_data.title || slide.content.title}
                      height={400}
                    />
                  )}
                  {slide.content.insights && Array.isArray(slide.content.insights) && slide.content.insights.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <h4 className="font-semibold text-sm mb-2">Key Insights</h4>
                      <ul className="list-disc list-inside space-y-1 text-sm" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                        {slide.content.insights.map((insight: string, idx: number) => (
                          <li key={idx}>{insight}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Path to 100M chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'fund_dpi_impact_sankey' && slide.content.chart_data && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="fund-dpi-impact-sankey-container"
            >
              {slide.content.chart_data ? (
                (() => {
                  try {
                    // Handle prerendered image
                    if (slide.content.chart_data.type === 'image' && slide.content.chart_data.original_data) {
                      const originalData = slide.content.chart_data.original_data;
                      if (originalData.type === 'sankey') {
                        // Fix the data before rendering
                        const fixed = fixSankeyData(originalData.data);
                        if (fixed.fixed) {
                          console.log('DPI Sankey: Fixed prerendered data:', fixed.fixes);
                        }
                        if (fixed.data && fixed.data.nodes && fixed.data.links) {
                          return (
                            <>
                              <TableauLevelCharts 
                                type="sankey"
                                data={fixed.data}
                                title={originalData.title || slide.content.title}
                                height={400}
                              />
                              {slide.content.metrics && (
                                <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                                  {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                    <div key={key}>
                                      <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </>
                          );
                        }
                      }
                      console.warn('DPI Sankey: prerendered image has invalid original_data:', {
                        originalType: originalData.type,
                        hasData: !!originalData.data
                      });
                    }
                    // Handle raw chart_data
                    if (slide.content.chart_data.type === 'sankey') {
                      // Fix the data before rendering
                      const fixed = fixSankeyData(slide.content.chart_data.data);
                      if (fixed.fixed) {
                        console.log('DPI Sankey: Fixed data:', fixed.fixes);
                      }
                      if (fixed.data && fixed.data.nodes && fixed.data.links) {
                        return (
                          <>
                            <TableauLevelCharts 
                              type="sankey"
                              data={fixed.data}
                              title={slide.content.chart_data.title || slide.content.title}
                              height={400}
                            />
                            {slide.content.metrics && (
                              <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                                {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                  <div key={key}>
                                    <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        );
                      }
                    }
                    // Try to fix the entire chart_data object
                    const fixedChart = fixChartDataObject(slide.content.chart_data);
                    if (fixedChart && fixedChart.fixed && fixedChart.type === 'sankey') {
                      console.log('DPI Sankey: Fixed chart_data object:', fixedChart.fixes);
                      const fixed = fixSankeyData(fixedChart.data);
                      if (fixed.data && fixed.data.nodes && fixed.data.links) {
                        return (
                          <>
                            <TableauLevelCharts 
                              type="sankey"
                              data={fixed.data}
                              title={fixedChart.title || slide.content.title}
                              height={400}
                            />
                            {slide.content.metrics && (
                              <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                                {Object.entries(slide.content.metrics).map(([key, value]: [string, any]) => (
                                  <div key={key}>
                                    <span className="font-semibold">{key}:</span> {typeof value === 'number' ? value.toFixed(2) : value}
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        );
                      }
                    }
                    console.warn('DPI Sankey: chart data structure is invalid:', {
                      type: slide.content.chart_data?.type,
                      hasData: !!slide.content.chart_data?.data,
                      hasOriginalData: !!slide.content.chart_data?.original_data
                    });
                    return (
                      <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                        Fund DPI impact Sankey chart data is missing or invalid
                      </div>
                    );
                  } catch (error) {
                    console.error('Error rendering DPI Sankey chart:', error);
                    return (
                      <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                        Error rendering Fund DPI impact Sankey chart
                      </div>
                    );
                  }
                })()
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Fund DPI impact Sankey chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'probability_cloud' && slide.content.chart_data && (
            <div 
              className="mt-8 p-6 rounded-xl shadow-sm"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="probability-cloud-container"
              data-chart-type="probability_cloud"
            >
              {slide.content.chart_data ? (
                (() => {
                  // Handle prerendered image
                  if (slide.content.chart_data.type === 'image' && slide.content.chart_data.original_data) {
                    const originalData = slide.content.chart_data.original_data;
                    if (originalData.type === 'probability_cloud') {
                      // Fix the data before rendering
                      const fixed = fixProbabilityCloudData(originalData.data);
                      if (fixed.fixed) {
                        console.log('Probability cloud: Fixed prerendered data:', fixed.fixes);
                      }
                      if (fixed.data && fixed.data.scenario_curves) {
                        return (
                          <TableauLevelCharts 
                            type="probability_cloud"
                            data={fixed.data}
                            title={originalData.title || slide.content.title}
                            height={500}
                          />
                        );
                      }
                    }
                  }
                  // Handle raw chart_data
                  if (slide.content.chart_data.type === 'probability_cloud') {
                    // Fix the data before rendering
                    const fixed = fixProbabilityCloudData(slide.content.chart_data.data);
                    if (fixed.fixed) {
                      console.log('Probability cloud: Fixed data:', fixed.fixes);
                    }
                    if (fixed.data && fixed.data.scenario_curves) {
                      return (
                        <TableauLevelCharts 
                          type="probability_cloud"
                          data={fixed.data}
                          title={slide.content.chart_data.title || slide.content.title}
                          height={500}
                        />
                      );
                    }
                  }
                  // Try to fix the entire chart_data object
                  const fixedChart = fixChartDataObject(slide.content.chart_data);
                  if (fixedChart && fixedChart.fixed && fixedChart.type === 'probability_cloud') {
                    console.log('Probability cloud: Fixed chart_data object:', fixedChart.fixes);
                    const fixed = fixProbabilityCloudData(fixedChart.data);
                    if (fixed.data && fixed.data.scenario_curves) {
                      return (
                        <TableauLevelCharts 
                          type="probability_cloud"
                          data={fixed.data}
                          title={fixedChart.title || slide.content.title}
                          height={500}
                        />
                      );
                    }
                  }
                  console.warn('Probability cloud: chart data structure is invalid:', {
                    type: slide.content.chart_data?.type,
                    hasData: !!slide.content.chart_data?.data,
                    hasOriginalData: !!slide.content.chart_data?.original_data
                  });
                  return (
                    <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                      Probability cloud chart data is missing or invalid
                    </div>
                  );
                })()
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Probability cloud chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'breakpoint_analysis' && slide.content.chart_data && (
            <div 
              className="mt-8 p-6 rounded-xl shadow-sm"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="breakpoint-analysis-container"
            >
              {slide.content.chart_data.data ? (
                slide.content.chart_data.type === 'waterfall' ? (
                  <TableauLevelCharts 
                    type="waterfall"
                    data={slide.content.chart_data.data}
                    title={slide.content.chart_data.title || slide.content.title}
                    height={400}
                  />
                ) : slide.content.chart_data.type === 'bar' || slide.content.chart_data.type === 'line' ? (
                  <div data-testid="recharts-container" data-chart-type="line">
                    {(() => {
                        try {
                        // Fix the data before processing
                        const fixed = fixLineChartData(slide.content.chart_data.data);
                        if (fixed.fixed) {
                          console.log('Breakpoint analysis: Fixed line chart data:', fixed.fixes);
                        }
                        const chartData = fixed.data;
                        const labels = chartData?.labels || [];
                        let formattedData: any[] = [];
                    
                        if (chartData?.datasets && Array.isArray(chartData.datasets)) {
                          formattedData = labels.map((label: string, index: number) => {
                            const dataPoint: any = { name: label || `Item ${index + 1}` };
                            chartData.datasets.forEach((dataset: any) => {
                              const key = dataset.label || 'value';
                              dataPoint[key] = dataset.data?.[index] ?? 0;
                            });
                            return dataPoint;
                          });
                        }
                        
                        if (!formattedData || formattedData.length === 0) {
                          return (
                            <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>Unable to format chart data</p>
                              </div>
                            </div>
                          );
                        }
                    
                        // Determine colors based on dataset labels - ensure "with pro rata" is blue
                        const getLineColor = (label: string, idx: number): string => {
                          const labelLower = label.toLowerCase();
                          if (labelLower.includes('pro rata') || labelLower.includes('with pro')) {
                            return '#3B82F6'; // Blue for pro rata
                          }
                          if (labelLower.includes('without') || labelLower.includes('no pro')) {
                            return isDarkMode ? '#94A3B8' : '#0A0A0A'; // Gray/black for without
                          }
                          // Default colors
                          const COLORS = isDarkMode 
                            ? [
                                DECK_DESIGN_TOKENS.colors.dark.accent.cyan,
                                DECK_DESIGN_TOKENS.colors.dark.accent.blue,
                                '#10B981',
                                '#F59E0B',
                                '#EF4444',
                                '#8B5CF6',
                              ]
                            : [
                                '#0A0A0A',
                                '#3B82F6',
                                '#059669',
                                '#D97706',
                                '#DC2626',
                                '#7C3AED',
                              ];
                          return COLORS[idx % COLORS.length];
                        };
                    
                        const textColor = isDarkMode 
                          ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                          : DECK_DESIGN_TOKENS.colors.light.text.secondary;
                        const gridColor = isDarkMode 
                          ? DECK_DESIGN_TOKENS.colors.dark.border.subtle 
                          : DECK_DESIGN_TOKENS.colors.light.border.subtle;
                        
                        const lineKeys = (formattedData.length > 0 && formattedData[0]) ? 
                          Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                        
                        // Get dataset labels from chartData for proper color assignment
                        const datasetLabels = chartData?.datasets?.map((ds: any) => ds.label || '') || [];
                        
                        return (
                          <ResponsiveContainer width="100%" height={400}>
                            <LineChart data={formattedData}>
                              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                              <XAxis 
                                dataKey="name" 
                                tick={{ fill: textColor }}
                                stroke={gridColor}
                              />
                              <YAxis 
                                tick={{ fill: textColor }}
                                stroke={gridColor}
                              />
                              <Tooltip 
                                contentStyle={{
                                  backgroundColor: isDarkMode 
                                    ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                    : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                  border: `1px solid ${gridColor}`,
                                  color: textColor
                                }}
                              />
                              <Legend wrapperStyle={{ color: textColor }} />
                              {lineKeys.map((key, idx) => {
                                const datasetLabel = datasetLabels[idx] || key;
                                const lineColor = getLineColor(datasetLabel, idx);
                                return (
                                  <Line 
                                    key={key}
                                    type="monotone"
                                    dataKey={key} 
                                    stroke={lineColor}
                                    strokeWidth={datasetLabel.toLowerCase().includes('pro rata') ? 3 : 2}
                                    dot={{ r: 4 }}
                                    activeDot={{ r: 6 }}
                                    name={datasetLabel}
                                  />
                                );
                              })}
                            </LineChart>
                          </ResponsiveContainer>
                        );
                      } catch (error) {
                        console.error('Error rendering breakpoint chart:', error);
                        return (
                          <div className="flex items-center justify-center h-[400px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                            <div className="text-center">
                              <p>Error rendering chart</p>
                              <p className="text-sm mt-2">{String(error)}</p>
                            </div>
                          </div>
                        );
                      }
                    })()}
                  </div>
                ) : (
                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                    Breakpoint analysis chart type not supported: {slide.content.chart_data.type}
                  </div>
                )
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Breakpoint analysis chart data is missing or invalid
                </div>
              )}
            </div>
          )}

          {slide.template === 'exit_scenarios_pwerm' && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="exit-scenarios-pwerm-container"
              data-chart-type={slide.content.chart_data?.type || 'exit_scenarios'}
            >
              <div className="space-y-6">
                {slide.content.scenarios && Array.isArray(slide.content.scenarios) && slide.content.scenarios.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-lg mb-3">Exit Scenarios</h3>
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ borderBottom: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                          <th className="text-left py-2">Company</th>
                          <th className="text-left py-2">Scenario</th>
                          <th className="text-right py-2">Probability</th>
                          <th className="text-right py-2">Exit Value</th>
                          <th className="text-right py-2">Multiple</th>
                        </tr>
                      </thead>
                      <tbody>
                        {slide.content.scenarios.map((scenario: any, idx: number) => (
                          <tr key={idx} style={{ borderBottom: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                            <td className="py-2">{scenario.company || 'N/A'}</td>
                            <td className="py-2">{scenario.name || scenario.scenario || `Scenario ${idx + 1}`}</td>
                            <td className="text-right py-2">{scenario.probability !== undefined ? `${(scenario.probability * 100).toFixed(1)}%` : 'N/A'}</td>
                            <td className="text-right py-2">{scenario.exit_value !== undefined ? `$${(scenario.exit_value / 1e6).toFixed(1)}M` : 'N/A'}</td>
                            <td className="text-right py-2">{scenario.multiple !== undefined ? `${scenario.multiple.toFixed(2)}x` : 'N/A'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {slide.content.chart_data && slide.content.chart_data.data ? (
                  <div className="mt-6">
                    {slide.content.scenarios && slide.content.scenarios.length > 0 && (
                      <h3 className="font-semibold text-lg mb-3">Visualization</h3>
                    )}
                    {(() => {
                      try {
                        // Handle prerendered image
                        if (slide.content.chart_data.type === 'image' && slide.content.chart_data.original_data) {
                          const originalData = slide.content.chart_data.original_data;
                          if (originalData.type && originalData.data) {
                            // Fix the data based on type
                            const fixed = fixChartData(originalData.type, originalData.data);
                            if (fixed.fixed) {
                              console.log('Exit scenarios: Fixed prerendered data:', fixed.fixes);
                            }
                            if (fixed.data) {
                              return (
                                <TableauLevelCharts 
                                  type={originalData.type as any}
                                  data={fixed.data}
                                  title={originalData.title || slide.content.chart_data.title || slide.content.title}
                                  height={400}
                                />
                              );
                            }
                          }
                          console.warn('Exit scenarios: prerendered image has invalid original_data:', {
                            originalType: originalData.type,
                            hasData: !!originalData.data
                          });
                        }
                        // Handle raw chart_data - try to fix it
                        const fixedChart = fixChartDataObject(slide.content.chart_data);
                        if (fixedChart && fixedChart.data) {
                          if (fixedChart.fixed) {
                            console.log('Exit scenarios: Fixed chart_data:', fixedChart.fixes);
                          }
                          return (
                            <TableauLevelCharts 
                              type={fixedChart.type as any}
                              data={fixedChart.data}
                              title={fixedChart.title || slide.content.chart_data.title || slide.content.title}
                              height={400}
                            />
                          );
                        }
                        // Fallback to original if fixer couldn't help
                        if (slide.content.chart_data.type && slide.content.chart_data.data) {
                          return (
                            <TableauLevelCharts 
                              type={slide.content.chart_data.type as any}
                              data={slide.content.chart_data.data}
                              title={slide.content.chart_data.title || slide.content.title}
                              height={400}
                            />
                          );
                        }
                        console.warn('Exit scenarios: chart_data structure is invalid:', {
                          type: slide.content.chart_data?.type,
                          hasData: !!slide.content.chart_data?.data
                        });
                        return (
                          <div className="text-center py-4" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                            Chart data is invalid
                          </div>
                        );
                      } catch (error) {
                        console.error('Error rendering exit scenarios chart:', error);
                        return (
                          <div className="text-center py-4" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                            Error rendering chart
                          </div>
                        );
                      }
                    })()}
                  </div>
                ) : !slide.content.scenarios && (
                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                    Exit scenarios data is missing
                  </div>
                )}
              </div>
            </div>
          )}

          {slide.template === 'followon_strategy_table' && slide.content && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="followon-strategy-table-container"
            >
              {slide.content.strategy_table ? (
                <div className="space-y-4">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                        <th className="text-left py-2">Round</th>
                        <th className="text-right py-2">Pro-Rata</th>
                        <th className="text-right py-2">Investment</th>
                        <th className="text-right py-2">Ownership</th>
                        <th className="text-left py-2">Strategy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {slide.content.strategy_table.map((row: any, idx: number) => (
                        <tr key={idx} style={{ borderBottom: `1px solid ${isDarkMode ? '#374151' : '#E5E7EB'}` }}>
                          <td className="py-2">{row.round || `Round ${idx + 1}`}</td>
                          <td className="text-right py-2">{row.pro_rata ? `${(row.pro_rata * 100).toFixed(1)}%` : 'N/A'}</td>
                          <td className="text-right py-2">{row.investment ? `$${(row.investment / 1e6).toFixed(2)}M` : 'N/A'}</td>
                          <td className="text-right py-2">{row.ownership ? `${(row.ownership * 100).toFixed(1)}%` : 'N/A'}</td>
                          <td className="py-2">{row.strategy || 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Follow-on strategy table data is missing
                </div>
              )}
            </div>
          )}

          {slide.template === 'next_round_intelligence' && slide.content && (
            <div 
              className="mt-6 p-4 rounded-lg"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-testid="next-round-intelligence-container"
            >
              {slide.content.companies && Array.isArray(slide.content.companies) && slide.content.companies.length > 0 ? (
                <div className="space-y-4">
                  {slide.content.companies.map((company: any, idx: number) => (
                    <div key={idx} className="p-4 rounded" style={{ backgroundColor: isDarkMode ? '#1F2937' : '#F9FAFB' }}>
                      <h4 className="font-semibold mb-2">{company.company || `Company ${idx + 1}`}</h4>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-semibold">Timing:</span> {company.timing || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Urgency:</span> {company.urgency || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Stage:</span> {company.stage || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Size:</span> {company.size || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Valuation (Pre):</span> {company.valuation_pre || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Valuation Step-up:</span> {company.valuation_step_up || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Down Round Risk:</span> {company.down_round_risk || 'N/A'} ({company.down_round_probability || 'N/A'})
                        </div>
                        <div>
                          <span className="font-semibold">Revenue Milestone:</span> {company.revenue_milestone || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Our Pro-Rata:</span> {company.our_prorata || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Expected Dilution:</span> {company.dilution_expected || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Market Sentiment:</span> {company.market_sentiment || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Milestone Confidence:</span> {company.milestone_confidence || 'N/A'}
                        </div>
                      </div>
                    </div>
                  ))}
                  {slide.content.insights && Array.isArray(slide.content.insights) && slide.content.insights.length > 0 && (
                    <div className="mt-4 p-4 rounded" style={{ backgroundColor: isDarkMode ? '#111827' : '#F3F4F6' }}>
                      <h5 className="font-semibold mb-2">Key Insights</h5>
                      <ul className="list-disc list-inside space-y-1 text-sm">
                        {slide.content.insights.map((insight: string, idx: number) => (
                          <li key={idx}>{insight}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : slide.content.predictions ? (
                <div className="space-y-4">
                  {slide.content.predictions.map((prediction: any, idx: number) => (
                    <div key={idx} className="p-4 rounded" style={{ backgroundColor: isDarkMode ? '#1F2937' : '#F9FAFB' }}>
                      <h4 className="font-semibold mb-2">{prediction.round || `Round ${idx + 1}`}</h4>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-semibold">Timing:</span> {prediction.timing || 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Valuation:</span> {prediction.valuation ? `$${(prediction.valuation / 1e6).toFixed(1)}M` : 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Amount:</span> {prediction.amount ? `$${(prediction.amount / 1e6).toFixed(1)}M` : 'N/A'}
                        </div>
                        <div>
                          <span className="font-semibold">Probability:</span> {prediction.probability ? `${(prediction.probability * 100).toFixed(1)}%` : 'N/A'}
                        </div>
                      </div>
                      {prediction.recommendation && (
                        <div className="mt-2 text-sm" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                          {prediction.recommendation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  Next round intelligence data is missing
                </div>
              )}
            </div>
          )}

          {slide.content.chart_data && (
            <div 
              className="mt-8 p-6 rounded-xl shadow-sm"
              style={{
                backgroundColor: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                border: `1px solid ${isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.border.medium 
                  : DECK_DESIGN_TOKENS.colors.light.border.medium}`,
                color: isDarkMode 
                  ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
                  : DECK_DESIGN_TOKENS.colors.light.text.primary
              }}
              data-chart-type={slide.content.chart_data.type}
              data-testid="chart-container"
            >
              {/* Check if chart is pre-rendered image */}
              {slide.content.chart_data.type === 'image' ? (
                <div data-testid="prerendered-chart">
                  {slide.content.chart_data.src ? (
                    <img 
                      src={slide.content.chart_data.src} 
                      alt={slide.content.chart_data.alt || 'Chart'} 
                      className="w-full h-auto"
                      style={{ maxHeight: '400px', objectFit: 'contain' }}
                      onError={(e) => {
                        console.error('Chart image failed to load:', slide.content.chart_data.src);
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      Chart image source missing
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {/* Use TableauLevelCharts for advanced visualizations */}
                  {slide.content.chart_data.type && ['sankey', 'side_by_side_sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'funnel', 'probability_cloud', 'timeline_valuation'].includes(slide.content.chart_data.type.toLowerCase()) ? (
                    <div data-testid="advanced-chart" data-chart-type={slide.content.chart_data.type}>
                      {slide.content.chart_data.data ? (
                        (() => {
                          // Validate chart data structure before rendering
                          try {
                            const chartType = slide.content.chart_data.type.toLowerCase();
                            const chartData = slide.content.chart_data.data;
                            
                            // Basic validation
                            if (!chartData || (typeof chartData === 'object' && Object.keys(chartData).length === 0)) {
                              return (
                                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                  <p>Chart data is empty</p>
                                  <p className="text-sm mt-2">Type: {chartType}</p>
                                </div>
                              );
                            }
                            
                            // Validate sankey data structure
                            if (chartType === 'sankey') {
                              if (!chartData.nodes || !Array.isArray(chartData.nodes) || chartData.nodes.length === 0) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid Sankey data: missing nodes</p>
                                  </div>
                                );
                              }
                              if (!chartData.links || !Array.isArray(chartData.links)) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid Sankey data: missing links</p>
                                  </div>
                                );
                              }
                            }
                            
                            // Validate side_by_side_sankey data structure
                            if (chartType === 'side_by_side_sankey') {
                              if (!chartData.company1_data || !chartData.company2_data) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid side-by-side Sankey data: missing company data</p>
                                  </div>
                                );
                              }
                            }
                            
                            // Validate probability_cloud data structure
                            if (chartType === 'probability_cloud') {
                              if (!chartData.scenario_curves || !Array.isArray(chartData.scenario_curves)) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid probability cloud data: missing scenario curves</p>
                                  </div>
                                );
                              }
                            }
                            
                            // Validate heatmap data structure
                            if (chartType === 'heatmap') {
                              // Heatmap can be backend format {dimensions, companies, scores} or frontend format [{x, y, value}]
                              if (!chartData.dimensions && (!Array.isArray(chartData) && !chartData.length)) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid heatmap data: missing dimensions/companies/scores or data array</p>
                                  </div>
                                );
                              }
                            }
                            
                            // Validate waterfall data structure
                            if (chartType === 'waterfall') {
                              const waterfallData = Array.isArray(chartData) ? chartData : (chartData.items || chartData.data);
                              if (!Array.isArray(waterfallData) || waterfallData.length === 0) {
                                return (
                                  <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                    <p>Invalid waterfall data: must be an array of items</p>
                                  </div>
                                );
                              }
                            }
                            
                            return (
                              <TableauLevelCharts 
                                type={slide.content.chart_data.type as any}
                                data={chartData}
                                title={slide.content.chart_data.title}
                                height={300}
                              />
                            );
                          } catch (error) {
                            console.error('[Chart Validation] Error validating chart data:', error);
                            return (
                              <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                <p>Error validating chart data</p>
                                <p className="text-sm mt-2">{String(error)}</p>
                              </div>
                            );
                          }
                        })()
                      ) : (
                        <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                          Chart data is missing
                        </div>
                      )}
                    </div>
                  ) : (
                  <div data-testid="recharts-container" data-chart-type={slide.content.chart_data?.type || 'bar'}>
                    {(() => {
                      try {
                        const chartType = slide.content.chart_data?.type?.toLowerCase() || 'bar';
                        const chartData = slide.content.chart_data?.data;
                        
                        // Comprehensive validation before rendering
                        if (!chartData) {
                          console.warn('[Chart Rendering] No chart data for type:', chartType);
                          return (
                            <div className="flex items-center justify-center h-[300px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>No chart data available</p>
                                <p className="text-sm mt-2">Chart type: {chartType}</p>
                              </div>
                            </div>
                          );
                        }
                        
                        // Validate data structure based on chart type
                        if (typeof chartData === 'object' && chartData !== null) {
                          // For Chart.js format, check for labels and datasets
                          if (chartData.labels && !Array.isArray(chartData.labels)) {
                            console.warn('[Chart Rendering] Invalid labels format:', chartData.labels);
                            return (
                              <div className="flex items-center justify-center h-[300px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                <div className="text-center">
                                  <p>Invalid chart data structure</p>
                                  <p className="text-sm mt-2">Labels must be an array</p>
                                </div>
                              </div>
                            );
                          }
                          
                          if (chartData.datasets && !Array.isArray(chartData.datasets)) {
                            console.warn('[Chart Rendering] Invalid datasets format:', chartData.datasets);
                            return (
                              <div className="flex items-center justify-center h-[300px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                                <div className="text-center">
                                  <p>Invalid chart data structure</p>
                                  <p className="text-sm mt-2">Datasets must be an array</p>
                                </div>
                              </div>
                            );
                          }
                        }
                        
                        const labels = chartData?.labels || [];
                        
                        // Format data for Recharts - handle both single and multi-dataset
                        let formattedData: any[] = [];
                    
                        if (chartData?.datasets && Array.isArray(chartData.datasets)) {
                          // Multiple datasets - format for multi-series charts
                          formattedData = labels.map((label: string, index: number) => {
                            const dataPoint: any = { name: label || `Item ${index + 1}` };
                            chartData.datasets.forEach((dataset: any) => {
                              const key = dataset.label || 'value';
                              dataPoint[key] = dataset.data?.[index] ?? 0;
                            });
                            return dataPoint;
                          });
                        } else if (chartData?.values && Array.isArray(chartData.values)) {
                          // Legacy format with values array
                          formattedData = labels.map((label: string, index: number) => ({
                            name: label || `Item ${index + 1}`,
                            value: chartData.values[index] ?? 0
                          }));
                        } else if (Array.isArray(chartData)) {
                          // Direct array of values
                          formattedData = chartData.map((value: any, index: number) => ({
                            name: labels[index] || (typeof value === 'object' && value?.name) || `Item ${index + 1}`,
                            value: typeof value === 'number' ? value : (typeof value === 'object' && value?.value) ? value.value : parseFloat(value) || 0
                          }));
                        } else if (typeof chartData === 'object' && chartData !== null) {
                          // Try to extract data from object structure
                          if (chartData.data && Array.isArray(chartData.data)) {
                            formattedData = chartData.data.map((item: any, index: number) => ({
                              name: item.name || item.label || labels[index] || `Item ${index + 1}`,
                              value: item.value ?? 0
                            }));
                          } else {
                            // Try to convert object to array
                            formattedData = Object.entries(chartData).map(([key, value]) => ({
                              name: key,
                              value: typeof value === 'number' ? value : parseFloat(String(value)) || 0
                            }));
                          }
                        }
                        
                        // If still no data, show error
                        if (!formattedData || formattedData.length === 0) {
                          return (
                            <div className="flex items-center justify-center h-[300px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                              <div className="text-center">
                                <p>Unable to format chart data</p>
                                <p className="text-sm mt-2">Type: {chartType}</p>
                                <p className="text-xs mt-1 opacity-75">Check console for details</p>
                              </div>
                            </div>
                          );
                        }
                    
                    // Define colors for charts using design tokens - theme-aware
                    const COLORS = isDarkMode 
                      ? [
                          DECK_DESIGN_TOKENS.colors.dark.accent.cyan,
                          DECK_DESIGN_TOKENS.colors.dark.accent.blue,
                          '#10B981', // Green
                          '#F59E0B', // Amber
                          '#EF4444', // Red
                          '#8B5CF6', // Purple
                        ]
                      : [
                          '#0A0A0A', // Obsidian black
                          '#3B82F6', // Blue
                          '#059669', // Green
                          '#D97706', // Amber
                          '#DC2626', // Red
                          '#7C3AED', // Purple
                        ];
                    
                    // Theme-aware text and grid colors
                    const textColor = isDarkMode 
                      ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                      : DECK_DESIGN_TOKENS.colors.light.text.secondary;
                    const gridColor = isDarkMode 
                      ? DECK_DESIGN_TOKENS.colors.dark.border.subtle 
                      : DECK_DESIGN_TOKENS.colors.light.border.subtle;
                    
                    switch (chartType) {
                      case 'line':
                        // Get all data keys except 'name'
                        const lineKeys = (formattedData.length > 0 && formattedData[0]) ? 
                          Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                        
                        return (
                          <LineChart data={formattedData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                            <XAxis 
                              dataKey="name" 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <YAxis 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <Tooltip 
                              contentStyle={{
                                backgroundColor: isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                border: `1px solid ${gridColor}`,
                                color: textColor
                              }}
                            />
                            <Legend wrapperStyle={{ color: textColor }} />
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
                        const barKeys = (formattedData.length > 0 && formattedData[0]) ? 
                          Object.keys(formattedData[0]).filter(k => k !== 'name') : ['value'];
                        
                        return (
                          <BarChart data={formattedData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                            <XAxis 
                              dataKey="name" 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <YAxis 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <Tooltip 
                              contentStyle={{
                                backgroundColor: isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                border: `1px solid ${gridColor}`,
                                color: textColor
                              }}
                            />
                            <Legend wrapperStyle={{ color: textColor }} />
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
                              labelLine={true}
                              label={({name, percent, value}) => {
                                // Show investor name and percentage on chart
                                const pct = (percent * 100).toFixed(1);
                                return `${name}\n${pct}%`;
                              }}
                              outerRadius={100}
                              fill={COLORS[0]}
                              dataKey="value"
                              fontSize={12}
                            >
                              {formattedData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip 
                              contentStyle={{
                                backgroundColor: isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                border: `1px solid ${gridColor}`,
                                color: textColor
                              }}
                              formatter={(value: any, name: any) => [`${value}%`, name]}
                            />
                            <Legend 
                              wrapperStyle={{ color: textColor }}
                              formatter={(value: any) => {
                                const entry = formattedData.find(d => d.name === value);
                                const pct = entry ? ((entry.value / formattedData.reduce((sum, d) => sum + d.value, 0)) * 100).toFixed(1) : '';
                                return `${value} (${pct}%)`;
                              }}
                            />
                          </PieChart>
                        );
                      
                      case 'area':
                        return (
                          <AreaChart data={formattedData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                            <XAxis 
                              dataKey="name" 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <YAxis 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <Tooltip 
                              contentStyle={{
                                backgroundColor: isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                border: `1px solid ${gridColor}`,
                                color: textColor
                              }}
                            />
                            <Area 
                              type="monotone" 
                              dataKey="value" 
                              stroke={COLORS[0]} 
                              fill={COLORS[0]} 
                              fillOpacity={0.6} 
                            />
                          </AreaChart>
                        );
                      
                      default:
                        // Fallback to bar chart if type is unknown
                        return (
                          <BarChart data={formattedData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                            <XAxis 
                              dataKey="name" 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <YAxis 
                              tick={{ fill: textColor }}
                              stroke={gridColor}
                            />
                            <Tooltip 
                              contentStyle={{
                                backgroundColor: isDarkMode 
                                  ? DECK_DESIGN_TOKENS.colors.dark.surface.card 
                                  : DECK_DESIGN_TOKENS.colors.light.surface.card,
                                border: `1px solid ${gridColor}`,
                                color: textColor
                              }}
                            />
                            <Bar dataKey="value" fill={COLORS[0]}>
                              {formattedData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
                            </Bar>
                          </BarChart>
                        );
                    }
                  } catch (error) {
                      console.error('Error rendering chart:', error, { chartType, chartData });
                        return (
                          <div className="flex items-center justify-center h-[300px]" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                            <div className="text-center">
                              <p>Error rendering chart</p>
                              <p className="text-sm mt-2">{String(error)}</p>
                            </div>
                          </div>
                        );
                      }
                    })()}
                </div>
                  )}
                  {slide.content.chart_data.title && !['sankey', 'side_by_side_sankey', 'sunburst', 'waterfall', 'heatmap', 'bubble', 'radialBar', 'funnel', 'probability_cloud', 'timeline_valuation'].includes(slide.content.chart_data.type?.toLowerCase()) && (
                    <p 
                      className="text-center text-sm mt-2"
                      style={{
                        color: isDarkMode 
                          ? DECK_DESIGN_TOKENS.colors.dark.text.secondary 
                          : DECK_DESIGN_TOKENS.colors.light.text.secondary
                      }}
                    >
                      {slide.content.chart_data.title}
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {slide.template === 'investment_recommendations' && slide.content.recommendations && (
            <div 
              className="mt-6 space-y-4"
              data-testid="investment-recommendations-container"
            >
              {Array.isArray(slide.content.recommendations) && slide.content.recommendations.length > 0 ? (
                slide.content.recommendations.map((rec: any, idx: number) => {
                  const decision = rec.decision || rec.recommendation || '';
                  const color = rec.color || 'gray';
                  
                  // Determine color scheme based on decision
                  let bgColor: string;
                  let textColor: string;
                  let borderColor: string;
                  
                  if (decision.includes('BUY') || decision.includes('INVEST')) {
                    bgColor = isDarkMode ? 'rgba(16, 185, 129, 0.1)' : 'rgba(16, 185, 129, 0.05)';
                    textColor = isDarkMode ? '#10B981' : '#059669';
                    borderColor = isDarkMode ? '#10B981' : '#059669';
                  } else if (decision.includes('WATCH') || decision.includes('CONSIDER')) {
                    bgColor = isDarkMode ? 'rgba(251, 191, 36, 0.1)' : 'rgba(251, 191, 36, 0.05)';
                    textColor = isDarkMode ? '#FBBF24' : '#D97706';
                    borderColor = isDarkMode ? '#FBBF24' : '#D97706';
                  } else {
                    bgColor = isDarkMode ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.05)';
                    textColor = isDarkMode ? '#EF4444' : '#DC2626';
                    borderColor = isDarkMode ? '#EF4444' : '#DC2626';
                  }
                  
                  return (
                    <div
                      key={idx}
                      className="rounded-lg p-6 border-2"
                      style={{
                        backgroundColor: bgColor,
                        borderColor: borderColor,
                        color: isDarkMode ? DECK_DESIGN_TOKENS.colors.dark.text.primary : DECK_DESIGN_TOKENS.colors.light.text.primary
                      }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-xl font-bold">{rec.company || `Company ${idx + 1}`}</h3>
                        <div 
                          className="px-4 py-2 rounded font-semibold text-lg"
                          style={{
                            color: textColor,
                            backgroundColor: isDarkMode ? 'rgba(0, 0, 0, 0.2)' : 'rgba(255, 255, 255, 0.8)'
                          }}
                        >
                          {decision}
                        </div>
                      </div>
                      
                      {rec.action && (
                        <div className="mb-3">
                          <span className="font-semibold">Action: </span>
                          <span>{rec.action}</span>
                        </div>
                      )}
                      
                      {rec.reasoning && (
                        <div className="mb-4">
                          <span className="font-semibold">Reasoning: </span>
                          <span>{rec.reasoning}</span>
                        </div>
                      )}
                      
                      <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t" style={{ borderColor: isDarkMode ? '#374151' : '#E5E7EB' }}>
                        {rec.ownership_details && (
                          <div>
                            <span className="text-sm opacity-75">Ownership</span>
                            <div className="font-semibold">{rec.ownership_details}</div>
                          </div>
                        )}
                        {rec.expected_proceeds && (
                          <div>
                            <span className="text-sm opacity-75">Expected Proceeds</span>
                            <div className="font-semibold">{rec.expected_proceeds}</div>
                          </div>
                        )}
                        {rec.expected_irr && (
                          <div>
                            <span className="text-sm opacity-75">Expected IRR</span>
                            <div className="font-semibold">{rec.expected_irr}</div>
                          </div>
                        )}
                        {rec.score && (
                          <div>
                            <span className="text-sm opacity-75">Score</span>
                            <div className="font-semibold">{rec.score}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8" style={{ color: isDarkMode ? '#94A3B8' : '#737373' }}>
                  No investment recommendations available
                </div>
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

    const editBg = isDarkMode 
      ? DECK_DESIGN_TOKENS.colors.dark.background.primary 
      : DECK_DESIGN_TOKENS.colors.light.background.primary;
    const editText = isDarkMode 
      ? DECK_DESIGN_TOKENS.colors.dark.text.primary 
      : DECK_DESIGN_TOKENS.colors.light.text.primary;

    return (
      <div 
        className="h-full flex flex-col p-8"
        style={{ 
          background: editBg,
          color: editText
        }}
      >
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
    <div className={`w-full h-full ${isPdfMode ? 'pdf-mode' : ''}`} style={{ padding: 0, margin: 0 }}>
      {/* Progress Tracker */}
      {!isPdfMode && activeTaskId && (
        <AgentProgressTracker 
          taskId={activeTaskId} 
          onClose={() => setActiveTaskId(undefined)}
        />
      )}
      
      <div className="h-full flex flex-col" style={{ padding: 0, margin: 0 }}>
          {/* Export Options Bar */}
          {currentDeck && !isPdfMode && (
            <div className="bg-white rounded-lg shadow-lg p-4 mb-4" style={{ marginLeft: '0.5rem', marginRight: '0.5rem', marginTop: '0.5rem' }}>
              <div className="flex items-center gap-3">
                <h2 
                  className="font-semibold text-sm"
                  style={{
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    color: DECK_DESIGN_TOKENS.colors.muted.foreground,
                    fontFamily: DECK_DESIGN_TOKENS.fonts.display
                  }}
                >
                  Export:
                </h2>
                <button 
                  onClick={handleExportPPTX}
                  disabled={isGenerating}
                  className="px-4 py-2 text-white rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  style={{
                    backgroundColor: DECK_DESIGN_TOKENS.colors.foreground,
                    borderRadius: DECK_DESIGN_TOKENS.borderRadius.medium
                  }}
                  onMouseEnter={(e) => {
                    if (!isGenerating) {
                      e.currentTarget.style.backgroundColor = DECK_DESIGN_TOKENS.colors.muted.DEFAULT;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isGenerating) {
                      e.currentTarget.style.backgroundColor = DECK_DESIGN_TOKENS.colors.foreground;
                    }
                  }}
                >
                  <Download className="w-4 h-4" />
                  {isGenerating && progressMessage.includes('PowerPoint') ? 'Exporting...' : 'PowerPoint'}
                </button>
                <button 
                  onClick={handleExportPDF}
                  disabled={isGenerating}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  {isGenerating && progressMessage.includes('PDF') ? 'Exporting...' : 'PDF'}
                </button>
              </div>
            </div>
          )}

          {/* Deck Viewer/Editor */}
          {currentDeck && (
            <div className={`flex-1 flex flex-col bg-white rounded-lg shadow-lg ${isPdfMode ? 'pdf-mode-deck' : ''}`} style={{ minHeight: 0, marginLeft: '0.5rem', marginRight: '0.5rem', marginBottom: '0.5rem' }}>
              {!isPdfMode && (
                <div className="flex items-center justify-between p-4 border-b border-gray-200 flex-shrink-0">
                  <div className="flex items-center gap-4 flex-1">
                    <div className="flex flex-col">
                      <h2 className="text-lg font-semibold text-gray-900">{currentDeck.title}</h2>
                    {/* Deck Statistics */}
                    <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <Presentation className="w-3 h-3" />
                        {currentDeck.slides.length} slides
                      </span>
                      {currentDeck.charts && currentDeck.charts.length > 0 && (
                        <span className="flex items-center gap-1">
                          <BarChart3 className="w-3 h-3" />
                          {currentDeck.charts.length} chart{currentDeck.charts.length !== 1 ? 's' : ''}
                        </span>
                      )}
                      {currentDeck.citations && currentDeck.citations.length > 0 && (
                        <span className="flex items-center gap-1">
                          <MessageSquare className="w-3 h-3" />
                          {currentDeck.citations.length} citation{currentDeck.citations.length !== 1 ? 's' : ''}
                        </span>
                      )}
                      {currentDeck.data_sources && currentDeck.data_sources.length > 0 && (
                        <span className="flex items-center gap-1">
                          <Globe className="w-3 h-3" />
                          {currentDeck.data_sources.length} source{currentDeck.data_sources.length !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                    </div>
                    <button
                      onClick={clearCurrentDeck}
                      className="px-3 py-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded border border-red-200"
                      title="Clear current deck"
                    >
                      Clear Deck
                    </button>
                  </div>
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
              )}
              
              {/* Slide Content Area - Fits screen, no scrolling */}
              <div 
                className={`${isPdfMode ? '' : 'flex items-center justify-center'} ${isPdfMode ? 'overflow-y-auto' : 'overflow-hidden'}`} 
                data-testid="deck-presentation"
                style={isPdfMode ? {
                  flex: 1,
                  minHeight: 0,
                  pointerEvents: 'auto'
                } : {
                  flex: 1,
                  minHeight: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'auto'
                }}
              >
                {isPdfMode && currentDeck && currentDeck.slides && currentDeck.slides.length > 0 ? (
                  // In PDF mode, render all slides with proper page breaks
                  <div className="space-y-0">
                    {currentDeck.slides.map((slide, idx) => (
                      <div 
                        key={slide.id || `slide-${idx}`} 
                        className="page-break-after"
                        style={{
                          width: '1024px',
                          height: '768px',
                          margin: '0 auto',
                          pageBreakAfter: 'always',
                          pageBreakInside: 'avoid'
                        }}
                      >
                        {renderSlideContent(slide)}
                      </div>
                    ))}
                  </div>
                ) : isEditingSlide 
                  ? renderEditableSlideContent()
                  : currentDeck && currentDeck.slides && currentDeck.slides.length > 0 && currentDeck.slides[currentSlideIndex]
                    ? (
                        <div 
                          key={`slide-${currentSlideIndex}-${currentDeck.slides[currentSlideIndex]?.id}`}
                          className="w-full h-full flex items-center justify-center"
                          style={{
                            aspectRatio: '4/3',
                            maxWidth: '100%',
                            maxHeight: '100%',
                            pointerEvents: 'auto',
                            position: 'relative',
                            zIndex: 1
                          }}
                        >
                          <div 
                            style={{
                              width: '100%',
                              height: '100%',
                              maxWidth: '100vw',
                              maxHeight: 'calc(100vh - 200px)',
                              aspectRatio: '4/3',
                              pointerEvents: 'auto'
                            }}
                          >
                            {renderSlideContent(currentDeck.slides[currentSlideIndex])}
                          </div>
                        </div>
                      )
                    : <div className="h-full flex items-center justify-center text-gray-500">
                        {currentDeck && currentDeck.slides && currentDeck.slides.length > 0
                          ? `Slide ${currentSlideIndex + 1} not found (${currentDeck.slides.length} slides available)`
                          : 'No slide content available'}
                      </div>
                }
              </div>

              {/* Slide Thumbnails */}
              {!isPdfMode && (
                <>
                  <div className="p-4 border-t border-gray-200 flex-shrink-0">
                    <div className="flex gap-2 overflow-x-auto pb-2">
                      {currentDeck.slides && currentDeck.slides.length > 0 ? (
                        currentDeck.slides.map((slide, idx) => (
                          <button
                            key={slide.id || `slide-${idx}`}
                            onClick={() => setCurrentSlideIndex(idx)}
                            className={`flex-shrink-0 w-24 h-16 border-2 rounded transition-colors ${
                              idx === currentSlideIndex 
                                ? 'border-blue-600 bg-blue-50' 
                                : 'border-gray-300 hover:border-gray-400 bg-white'
                            }`}
                            style={idx === currentSlideIndex ? {
                              borderColor: DECK_DESIGN_TOKENS.colors.foreground,
                              backgroundColor: DECK_DESIGN_TOKENS.colors.secondary?.DEFAULT || '#f0f9ff'
                            } : {
                              borderColor: DECK_DESIGN_TOKENS.colors.border || '#d1d5db'
                            }}
                          >
                            <div className="p-1 text-xs">
                              <div className="font-medium truncate text-gray-900">{idx + 1}. {slide?.content?.title || 'Untitled'}</div>
                            </div>
                          </button>
                        ))
                      ) : (
                        <div className="text-sm text-gray-500 p-2">No slides available</div>
                      )}
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
                </>
              )}
            </div>
          )}

          {!isPdfMode && !currentDeck && (
          <div className="flex gap-6">
          {/* Chat Interface */}
          <div className="flex-1 bg-white border border-gray-200 rounded">
            {/* Header */}
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-green-600 rounded-lg">
                    <Presentation className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h1 className="text-2xl font-semibold text-gray-900">Deck Generator</h1>
                    <p className="text-sm text-gray-600">Create professional presentations</p>
                  </div>
                </div>
                
                <button
                  onClick={toggleTheme}
                  className="p-2 text-gray-600 hover:text-gray-900"
                  aria-label="Toggle theme"
                >
                  {isDarkMode ? (
                    <Sun className="w-5 h-5" />
                  ) : (
                    <Moon className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Neo-Noir Messages */}
            <div className="h-64 overflow-y-auto p-6 space-y-4" style={{
              background: isDarkMode 
                ? 'linear-gradient(180deg, #0A0A0F 0%, #111118 100%)'
                : 'linear-gradient(180deg, #FFFFFF 0%, #FAFAFA 100%)'
            }}>
              {messages.map(message => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={message.role === 'user' 
                      ? (isDarkMode ? 'card-neo-dark' : 'card-neo-light')
                      : (isDarkMode ? 'card-neo-dark' : 'card-neo-light')
                    }
                    style={{
                      maxWidth: '75%',
                      padding: '1rem 1.25rem',
                      borderRadius: '16px',
                      background: message.role === 'user'
                        ? (isDarkMode ? '#242433' : '#F5F5F5')
                        : (isDarkMode ? '#1A1A24' : '#FFFFFF')
                    }}
                  >
                    <div 
                      className={isDarkMode && message.role === 'assistant' ? 'text-glow-dark' : ''}
                      style={{
                        color: isDarkMode ? '#E2E8F0' : '#0A0A0A',
                        fontSize: '0.9375rem',
                        lineHeight: 1.6,
                        fontWeight: 400
                      }}
                    >
                      {message.content}
                    </div>
                  </div>
                </div>
              ))}
              
              {isGenerating && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-3 rounded-lg">
                    <div className="flex items-center gap-2">
                      <RefreshCw 
                        className="w-4 h-4 animate-spin" 
                        style={{ color: DECK_DESIGN_TOKENS.colors.foreground }}
                      />
                      <span 
                        className="text-sm"
                        style={{ color: DECK_DESIGN_TOKENS.colors.muted.foreground }}
                      >
                        Generating presentation...
                      </span>
                    </div>
                    <div 
                      className="w-48 rounded-full h-2 mt-2"
                      style={{
                        backgroundColor: DECK_DESIGN_TOKENS.colors.secondary.DEFAULT,
                        borderRadius: DECK_DESIGN_TOKENS.borderRadius.small
                      }}
                    >
                      <div 
                        className="h-2 rounded-full transition-all duration-300"
                        style={{ 
                          width: `${generationProgress}%`,
                          backgroundColor: DECK_DESIGN_TOKENS.colors.foreground,
                          borderRadius: DECK_DESIGN_TOKENS.borderRadius.small
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Neo-Noir Quick Prompts */}
            <div className="px-6 py-4" style={{
              borderTop: `1.5px solid ${isDarkMode ? 'rgba(255,255,255,0.08)' : '#E5E5E5'}`
            }}>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {quickPrompts.slice(0, 3).map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => handleQuickPrompt(prompt)}
                    className={isDarkMode ? 'card-neo-dark' : 'card-neo-light'}
                    style={{
                      padding: '0.75rem 1.25rem',
                      borderRadius: '12px',
                      fontSize: '0.875rem',
                      fontWeight: 500,
                      color: isDarkMode ? '#E2E8F0' : '#525252',
                      whiteSpace: 'nowrap',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem'
                    }}
                  >
                    <Sparkles className="w-4 h-4" style={{ color: isDarkMode ? '#22D3EE' : '#0A0A0A' }} />
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Input Form */}
            <form onSubmit={handleSubmit} className="p-6 bg-white border-t border-gray-200">
              <div className="flex gap-3 w-full">
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
                  placeholder="Describe the presentation you want to create..."
                  className="flex-1 min-w-0 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500 text-gray-900 bg-white"
                  style={{ minHeight: '56px', color: '#0A0A0A' }}
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className={isDarkMode ? 'btn-neo-primary-dark' : 'btn-neo-primary-light'}
                  style={{
                    minWidth: '56px',
                    height: '56px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: (!input.trim() || isLoading) ? 0.5 : 1,
                    cursor: (!input.trim() || isLoading) ? 'not-allowed' : 'pointer'
                  }}
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </form>
            
          </div>

          {/* Sidebar */}
          <div className="w-64">
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
          )}
      </div>
    </div>
  );
}

export default function DeckAgentPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<div className="w-full max-w-3xl mx-auto p-4">Loading...</div>}>
        <DeckAgentContent />
      </Suspense>
    </ErrorBoundary>
  );
}
