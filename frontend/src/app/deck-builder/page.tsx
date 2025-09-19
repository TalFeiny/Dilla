'use client';

import React, { useState, useEffect } from 'react';
import { 
  PlusIcon, 
  PlayIcon,
  DocumentArrowDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PencilIcon,
  TrashIcon,
  SparklesIcon,
  ArrowPathIcon,
  ViewColumnsIcon,
  Squares2X2Icon
} from '@heroicons/react/24/outline';

interface Slide {
  id: string;
  order: number;
  template: string;
  content: {
    title: string;
    subtitle?: string;
    body?: string;
    bullets?: string[];
    metrics?: Record<string, any>;
    notes?: string;
  };
}

interface Deck {
  id: string;
  title: string;
  type: string;
  company_name: string;
  slides: Slide[];
  theme: {
    primary_color: string;
    secondary_color: string;
    accent_color: string;
    background_color: string;
    font_family: string;
  };
}

export default function DeckBuilder() {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [viewMode, setViewMode] = useState<'edit' | 'preview'>('edit');
  const [sidebarView, setSidebarView] = useState<'slides' | 'themes'>('slides');
  const [selectedTemplate, setSelectedTemplate] = useState('title');

  // Form state for deck creation
  const [deckForm, setDeckForm] = useState({
    title: '',
    type: 'pitch',
    companyName: '',
    industry: '',
    stage: 'seed',
    requirements: ''
  });

  const deckTypes = [
    { id: 'pitch', name: 'Pitch Deck', description: 'For investors' },
    { id: 'cim', name: 'Investment Memo', description: 'Detailed analysis' },
    { id: 'sales', name: 'Sales Deck', description: 'For customers' },
    { id: 'board', name: 'Board Deck', description: 'For board meetings' }
  ];

  const slideTemplates = [
    { id: 'title', name: 'Title Slide', icon: '📄' },
    { id: 'agenda', name: 'Agenda', icon: '📋' },
    { id: 'problem_solution', name: 'Problem/Solution', icon: '💡' },
    { id: 'market_opportunity', name: 'Market Opportunity', icon: '📈' },
    { id: 'financials', name: 'Financials', icon: '💰' },
    { id: 'team', name: 'Team', icon: '👥' },
    { id: 'competition', name: 'Competition', icon: '🏆' },
    { id: 'roadmap', name: 'Roadmap', icon: '🗺️' },
    { id: 'metrics', name: 'Metrics', icon: '📊' },
    { id: 'ask', name: 'The Ask', icon: '🎯' }
  ];

  const themes = [
    { id: 'professional', name: 'Professional', colors: ['#1E40AF', '#3B82F6'] },
    { id: 'modern', name: 'Modern', colors: ['#7C3AED', '#A78BFA'] },
    { id: 'minimal', name: 'Minimal', colors: ['#000000', '#6B7280'] },
    { id: 'vibrant', name: 'Vibrant', colors: ['#DC2626', '#F97316'] }
  ];

  const createDeck = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('/api/deck-builder/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: deckForm.title,
          type: deckForm.type,
          company_info: {
            name: deckForm.companyName,
            industry: deckForm.industry,
            stage: deckForm.stage,
            author: 'User'
          },
          requirements: deckForm.requirements,
          auto_generate: true
        })
      });

      const data = await response.json();
      
      // Fetch the complete deck
      const deckResponse = await fetch(`/api/deck-builder/${data.id}`);
      const deckData = await deckResponse.json();
      
      setDeck(deckData);
      setCurrentSlideIndex(0);
    } catch (error) {
      console.error('Error creating deck:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const addSlide = async (template: string) => {
    if (!deck) return;

    try {
      const response = await fetch('/api/deck-builder/slides/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slide_type: template,
          context: {
            company_info: {
              name: deck.company_name,
              industry: deckForm.industry
            },
            deck_type: deck.type
          }
        })
      });

      const slideContent = await response.json();
      
      const newSlide: Slide = {
        id: `slide-${Date.now()}`,
        order: deck.slides.length + 1,
        template,
        content: slideContent
      };

      setDeck({
        ...deck,
        slides: [...deck.slides, newSlide]
      });
      
      setCurrentSlideIndex(deck.slides.length);
    } catch (error) {
      console.error('Error adding slide:', error);
    }
  };

  const regenerateSlide = async () => {
    if (!deck || !deck.slidesArray.from(rentSlideIndex)) return;

    try {
      const response = await fetch('/api/deck-builder/slides/update', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deck_id: deck.id,
          slide_id: deck.slidesArray.from(rentSlideIndex).id,
          regenerate: true,
          instructions: 'Make it more compelling and data-driven'
        })
      });

      const data = await response.json();
      if (data.success && data.slide) {
        const updatedSlides = [...deck.slides];
        updatedSlides[currentSlideIndex] = data.slide;
        setDeck({ ...deck, slides: updatedSlides });
      }
    } catch (error) {
      console.error('Error regenerating slide:', error);
    }
  };

  const exportDeck = async (format: string) => {
    if (!deck) return;

    try {
      const response = await fetch('/api/deck-builder/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deck_id: deck.id,
          format
        })
      });

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${deck.title}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting deck:', error);
    }
  };

  const currentSlide = deck?.slidesArray.from(rentSlideIndex);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-gray-900">
              {deck ? deck.title : 'AI Deck Builder'}
            </h1>
            {deck && (
              <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                {deck.type.toUpperCase()} • {deck.slides.length} slides
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-3">
            {deck && (
              <>
                <button
                  onClick={() => setViewMode(viewMode === 'edit' ? 'preview' : 'edit')}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  {viewMode === 'edit' ? 'Preview' : 'Edit'}
                </button>
                
                <button
                  onClick={() => exportDeck('pptx')}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  <DocumentArrowDownIcon className="h-5 w-5 mr-2" />
                  Export
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-73px)]">
        {/* Sidebar */}
        <aside className="w-80 bg-white border-r border-gray-200 overflow-y-auto">
          {!deck ? (
            // Deck creation form
            <div className="p-6">
              <h2 className="text-lg font-semibold mb-4">Create New Deck</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Deck Title
                  </label>
                  <input
                    type="text"
                    value={deckForm.title}
                    onChange={(e) => setDeckForm({ ...deckForm, title: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    placeholder="My Awesome Pitch"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Deck Type
                  </label>
                  <select
                    value={deckForm.type}
                    onChange={(e) => setDeckForm({ ...deckForm, type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  >
                    {deckTypes.map(type => (
                      <option key={type.id} value={type.id}>
                        {type.name} - {type.description}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={deckForm.companyName}
                    onChange={(e) => setDeckForm({ ...deckForm, companyName: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Acme Inc."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Industry
                  </label>
                  <input
                    type="text"
                    value={deckForm.industry}
                    onChange={(e) => setDeckForm({ ...deckForm, industry: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Technology, Healthcare, etc."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Stage
                  </label>
                  <select
                    value={deckForm.stage}
                    onChange={(e) => setDeckForm({ ...deckForm, stage: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="idea">Idea</option>
                    <option value="seed">Seed</option>
                    <option value="series-a">Series A</option>
                    <option value="series-b">Series B</option>
                    <option value="growth">Growth</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Special Requirements
                  </label>
                  <textarea
                    value={deckForm.requirements}
                    onChange={(e) => setDeckForm({ ...deckForm, requirements: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    rows={3}
                    placeholder="Any specific requirements or focus areas..."
                  />
                </div>

                <button
                  onClick={createDeck}
                  disabled={isGenerating || !deckForm.title || !deckForm.companyName}
                  className="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isGenerating ? (
                    <>
                      <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="h-5 w-5 mr-2" />
                      Generate Deck with AI
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            // Slide management
            <div className="h-full flex flex-col">
              <div className="flex border-b border-gray-200">
                <button
                  onClick={() => setSidebarView('slides')}
                  className={`flex-1 px-4 py-3 text-sm font-medium ${
                    sidebarView === 'slides'
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Slides
                </button>
                <button
                  onClick={() => setSidebarView('themes')}
                  className={`flex-1 px-4 py-3 text-sm font-medium ${
                    sidebarView === 'themes'
                      ? 'text-blue-600 border-b-2 border-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Themes
                </button>
              </div>

              {sidebarView === 'slides' ? (
                <div className="flex-1 overflow-y-auto">
                  {/* Slide thumbnails */}
                  <div className="p-4 space-y-2">
                    {deck.slides.map((slide, index) => (
                      <div
                        key={slide.id}
                        onClick={() => setCurrentSlideIndex(index)}
                        className={`p-3 rounded-lg cursor-pointer transition-colors ${
                          index === currentSlideIndex
                            ? 'bg-blue-50 border-2 border-blue-500'
                            : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="text-xs text-gray-500 mb-1">
                              Slide {index + 1}
                            </div>
                            <div className="font-medium text-sm text-gray-900">
                              {slide.content.title}
                            </div>
                            <div className="text-xs text-gray-600 mt-1">
                              {slide.template.replace('_', ' ')}
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              // Delete slide logic
                            }}
                            className="p-1 hover:bg-gray-200 rounded"
                          >
                            <TrashIcon className="h-4 w-4 text-gray-400" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add slide section */}
                  <div className="p-4 border-t border-gray-200">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">
                      Add New Slide
                    </h3>
                    <div className="grid grid-cols-2 gap-2">
                      {slideTemplates.map(template => (
                        <button
                          key={template.id}
                          onClick={() => addSlide(template.id)}
                          className="p-2 text-left rounded-lg border border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-colors"
                        >
                          <div className="text-lg mb-1">{template.icon}</div>
                          <div className="text-xs text-gray-700">
                            {template.name}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                // Themes view
                <div className="p-4 space-y-3">
                  {themes.map(theme => (
                    <button
                      key={theme.id}
                      onClick={() => {
                        // Apply theme logic
                      }}
                      className="w-full p-4 rounded-lg border border-gray-200 hover:border-blue-500 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{theme.name}</span>
                      </div>
                      <div className="flex space-x-2">
                        {theme.colors.map((color, i) => (
                          <div
                            key={i}
                            className="h-6 w-6 rounded"
                            style={{ backgroundColor: color }}
                          />
                        ))}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>

        {/* Main content area */}
        <main className="flex-1 flex flex-col bg-gray-100">
          {deck && currentSlide ? (
            <>
              {/* Slide canvas */}
              <div className="flex-1 p-8 overflow-auto">
                <div className="max-w-5xl mx-auto">
                  <div className="bg-white rounded-lg shadow-lg aspect-[16/9] p-12">
                    {/* Slide content rendering */}
                    <div className="h-full flex flex-col">
                      {currentSlide.content.title && (
                        <h1 className="text-4xl font-bold mb-6" style={{ color: deck.theme.primary_color }}>
                          {currentSlide.content.title}
                        </h1>
                      )}
                      
                      {currentSlide.content.subtitle && (
                        <h2 className="text-2xl mb-6" style={{ color: deck.theme.secondary_color }}>
                          {currentSlide.content.subtitle}
                        </h2>
                      )}
                      
                      {currentSlide.content.body && (
                        <p className="text-lg mb-6 text-gray-700">
                          {currentSlide.content.body}
                        </p>
                      )}
                      
                      {currentSlide.content.bullets && (
                        <ul className="space-y-3">
                          {currentSlide.content.bullets.map((bullet, i) => (
                            <li key={i} className="flex items-start">
                              <span className="text-blue-600 mr-3">•</span>
                              <span className="text-gray-700">{bullet}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      
                      {currentSlide.content.metrics && (
                        <div className="grid grid-cols-3 gap-6 mt-6">
                          {Object.entries(currentSlide.content.metrics).map(([key, value]) => (
                            <div key={key} className="text-center p-4 bg-blue-50 rounded-lg">
                              <div className="text-3xl font-bold text-blue-600">
                                {value}
                              </div>
                              <div className="text-sm text-gray-600 mt-1">
                                {key}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Speaker notes */}
                  {viewMode === 'edit' && currentSlide.content.notes && (
                    <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">
                        Speaker Notes
                      </h3>
                      <p className="text-sm text-gray-600">
                        {currentSlide.content.notes}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Slide controls */}
              <div className="bg-white border-t border-gray-200 px-8 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setCurrentSlideIndex(Math.max(0, currentSlideIndex - 1))}
                      disabled={currentSlideIndex === 0}
                      className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronLeftIcon className="h-5 w-5" />
                    </button>
                    
                    <span className="px-3 py-1 bg-gray-100 rounded-lg text-sm">
                      {currentSlideIndex + 1} / {deck.slides.length}
                    </span>
                    
                    <button
                      onClick={() => setCurrentSlideIndex(Math.min(deck.slides.length - 1, currentSlideIndex + 1))}
                      disabled={currentSlideIndex === deck.slides.length - 1}
                      className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronRightIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={regenerateSlide}
                      className="flex items-center px-3 py-2 text-sm bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200"
                    >
                      <ArrowPathIcon className="h-4 w-4 mr-1" />
                      Regenerate
                    </button>
                    
                    <button className="flex items-center px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
                      <PencilIcon className="h-4 w-4 mr-1" />
                      Edit
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            // Empty state
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Squares2X2Icon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  No deck created yet
                </h3>
                <p className="text-gray-600">
                  Fill out the form on the left to generate your first AI-powered deck
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}