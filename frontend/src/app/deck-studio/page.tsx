'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  PlusIcon,
  ChartBarIcon,
  ChartPieIcon,
  ArrowTrendingUpIcon,
  TableCellsIcon,
  PhotoIcon,
  DocumentTextIcon,
  SparklesIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  PlayIcon,
  CloudArrowDownIcon,
  ShareIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  Bars3Icon,
  MagnifyingGlassIcon,
  UserGroupIcon,
  ClockIcon,
  CommandLineIcon,
  PencilIcon,
  CursorArrowRaysIcon,
  Square3Stack3DIcon,
  ViewColumnsIcon,
  ChatBubbleLeftRightIcon
} from '@heroicons/react/24/outline';
import { 
  BoldIcon,
  ItalicIcon,
  UnderlineIcon,
  LinkIcon,
  ListBulletIcon,
  NumberedListIcon 
} from '@heroicons/react/24/solid';
import dynamic from 'next/dynamic';

// Dynamic imports for chart libraries
const Chart = dynamic(() => import('react-chartjs-2').then(mod => mod.Chart), { ssr: false });
const Line = dynamic(() => import('react-chartjs-2').then(mod => mod.Line), { ssr: false });
const Bar = dynamic(() => import('react-chartjs-2').then(mod => mod.Bar), { ssr: false });
const Doughnut = dynamic(() => import('react-chartjs-2').then(mod => mod.Doughnut), { ssr: false });
const Scatter = dynamic(() => import('react-chartjs-2').then(mod => mod.Scatter), { ssr: false });

interface Slide {
  id: string;
  order: number;
  type: string;
  title: string;
  content: any;
  layout: string;
  elements: Element[];
  notes: string;
  animations: any[];
  background: string;
}

interface Element {
  id: string;
  type: 'text' | 'image' | 'chart' | 'table' | 'shape' | 'video';
  position: { x: number; y: number; width: number; height: number };
  content: any;
  style: any;
  locked: boolean;
}

interface Deck {
  id: string;
  title: string;
  slides: Slide[];
  theme: Theme;
  collaborators: string[];
  lastModified: Date;
  version: number;
}

interface Theme {
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
    text: string;
  };
  fonts: {
    heading: string;
    body: string;
  };
}

export default function DeckStudio() {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [selectedElement, setSelectedElement] = useState<Element | null>(null);
  const [isPresenting, setIsPresenting] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [showGrid, setShowGrid] = useState(true);
  const [showRulers, setShowRulers] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<'slides' | 'elements' | 'data' | 'ai'>('slides');
  const [aiPrompt, setAiPrompt] = useState('');
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Chart templates
  const chartTemplates = [
    { id: 'line', name: 'Line Chart', icon: ArrowTrendingUpIcon, type: 'line' },
    { id: 'bar', name: 'Bar Chart', icon: ChartBarIcon, type: 'bar' },
    { id: 'pie', name: 'Pie Chart', icon: ChartPieIcon, type: 'pie' },
    { id: 'scatter', name: 'Scatter Plot', icon: Square3Stack3DIcon, type: 'scatter' },
    { id: 'area', name: 'Area Chart', icon: ArrowTrendingUpIcon, type: 'area' },
    { id: 'combo', name: 'Combo Chart', icon: ViewColumnsIcon, type: 'combo' }
  ];

  // Element templates
  const elementTemplates = [
    { id: 'text', name: 'Text', icon: DocumentTextIcon },
    { id: 'chart', name: 'Chart', icon: ChartBarIcon },
    { id: 'table', name: 'Table', icon: TableCellsIcon },
    { id: 'image', name: 'Image', icon: PhotoIcon },
    { id: 'shape', name: 'Shape', icon: Square3Stack3DIcon }
  ];

  // Initialize with empty deck
  useEffect(() => {
    const newDeck: Deck = {
      id: 'deck-' + Date.now(),
      title: 'Untitled Presentation',
      slides: [createEmptySlide(0)],
      theme: {
        colors: {
          primary: '#6366f1',
          secondary: '#8b5cf6',
          accent: '#ec4899',
          background: '#ffffff',
          text: '#1f2937'
        },
        fonts: {
          heading: 'Inter',
          body: 'Inter'
        }
      },
      collaborators: [],
      lastModified: new Date(),
      version: 1
    };
    setDeck(newDeck);
  }, []);

  function createEmptySlide(order: number): Slide {
    return {
      id: 'slide-' + Date.now() + '-' + order,
      order,
      type: 'blank',
      title: '',
      content: {},
      layout: 'blank',
      elements: [],
      notes: '',
      animations: [],
      background: '#ffffff'
    };
  }

  // Add new slide
  const addSlide = (type: string = 'blank') => {
    if (!deck) return;
    
    const newSlide = createEmptySlide(deck.slides.length);
    newSlide.type = type;
    
    setDeck({
      ...deck,
      slides: [...deck.slides, newSlide]
    });
    setCurrentSlideIndex(deck.slides.length);
  };

  // Delete slide
  const deleteSlide = (index: number) => {
    if (!deck || deck.slides.length <= 1) return;
    
    const newSlides = deck.slides.filter((_, i) => i !== index);
    setDeck({ ...deck, slides: newSlides });
    
    if (currentSlideIndex >= newSlides.length) {
      setCurrentSlideIndex(newSlides.length - 1);
    }
  };

  // Duplicate slide
  const duplicateSlide = (index: number) => {
    if (!deck) return;
    
    const slideToDuplicate = deck.slides[index];
    const newSlide = {
      ...slideToDuplicate,
      id: 'slide-' + Date.now(),
      order: index + 1
    };
    
    const newSlides = [
      ...deck.slides.slice(0, index + 1),
      newSlide,
      ...deck.slides.slice(index + 1)
    ];
    
    setDeck({ ...deck, slides: newSlides });
  };

  // Add element to current slide
  const addElement = (type: string, chartType?: string) => {
    if (!deck) return;
    
    const currentSlide = deck.slides[currentSlideIndex];
    const newElement: Element = {
      id: 'element-' + Date.now(),
      type: type as any,
      position: { 
        x: 20 + (currentSlide.elements.length * 5), 
        y: 20 + (currentSlide.elements.length * 5), 
        width: type === 'chart' ? 400 : 300, 
        height: type === 'chart' ? 300 : 200 
      },
      content: getDefaultContent(type, chartType),
      style: getDefaultStyle(type),
      locked: false
    };
    
    const newSlides = [...deck.slides];
    newSlides[currentSlideIndex] = {
      ...currentSlide,
      elements: [...currentSlide.elements, newElement]
    };
    
    setDeck({ ...deck, slides: newSlides });
    setSelectedElement(newElement);
  };

  // Get default content for element type
  function getDefaultContent(type: string, chartType?: string) {
    switch (type) {
      case 'text':
        return { text: 'Click to edit text', html: '<p>Click to edit text</p>' };
      case 'chart':
        return {
          type: chartType || 'bar',
          data: {
            labels: ['Q1', 'Q2', 'Q3', 'Q4'],
            datasets: [{
              label: 'Revenue',
              data: [30, 50, 70, 90],
              backgroundColor: '#6366f1',
              borderColor: '#4f46e5',
              borderWidth: 2
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'top' },
              title: { display: true, text: 'Quarterly Revenue' }
            }
          }
        };
      case 'table':
        return {
          headers: ['Metric', 'Q1', 'Q2', 'Q3', 'Q4'],
          rows: [
            ['Revenue', '$1M', '$1.5M', '$2M', '$2.5M'],
            ['Growth', '25%', '50%', '33%', '25%'],
            ['Customers', '100', '150', '200', '250']
          ]
        };
      default:
        return {};
    }
  }

  // Get default style for element type
  function getDefaultStyle(type: string) {
    return {
      padding: '16px',
      backgroundColor: type === 'text' ? 'transparent' : '#ffffff',
      border: type === 'chart' || type === 'table' ? '1px solid #e5e7eb' : 'none',
      borderRadius: '8px',
      fontSize: '16px',
      fontFamily: 'Inter',
      color: '#1f2937'
    };
  }

  // AI Agent Integration
  const handleAiGeneration = async () => {
    if (!aiPrompt.trim() || !deck) return;
    
    setIsAiGenerating(true);
    try {
      const response = await fetch('/api/deck-studio/ai-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: aiPrompt,
          context: {
            currentSlide: deck.slides[currentSlideIndex],
            deckType: deck.slides[0]?.type,
            theme: deck.theme
          }
        })
      });
      
      const result = await response.json();
      
      if (result.action === 'add_slide') {
        addSlide(result.slideType);
        // Update slide content
        const newSlides = [...deck.slides];
        newSlides[newSlides.length - 1] = {
          ...newSlides[newSlides.length - 1],
          ...result.content
        };
        setDeck({ ...deck, slides: newSlides });
      } else if (result.action === 'add_element') {
        addElement(result.elementType, result.chartType);
      } else if (result.action === 'update_content') {
        // Update current slide or element
        if (selectedElement) {
          updateElementContent(selectedElement.id, result.content);
        } else {
          updateSlideContent(currentSlideIndex, result.content);
        }
      }
      
      setAiPrompt('');
    } catch (error) {
      console.error('AI generation error:', error);
    } finally {
      setIsAiGenerating(false);
    }
  };

  // Update element content
  const updateElementContent = (elementId: string, content: any) => {
    if (!deck) return;
    
    const newSlides = [...deck.slides];
    const currentSlide = newSlides[currentSlideIndex];
    const elementIndex = currentSlide.elements.findIndex(e => e.id === elementId);
    
    if (elementIndex !== -1) {
      currentSlide.elements[elementIndex].content = content;
      setDeck({ ...deck, slides: newSlides });
    }
  };

  // Update slide content
  const updateSlideContent = (slideIndex: number, content: any) => {
    if (!deck) return;
    
    const newSlides = [...deck.slides];
    newSlides[slideIndex] = {
      ...newSlides[slideIndex],
      ...content
    };
    setDeck({ ...deck, slides: newSlides });
  };

  // Export deck
  const exportDeck = async (format: 'pptx' | 'pdf' | 'json') => {
    if (!deck) return;
    
    const response = await fetch('/api/deck-studio/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deck, format })
    });
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${deck.title}.${format}`;
    a.click();
  };

  if (!deck) return <div>Loading...</div>;

  const currentSlide = deck.slides[currentSlideIndex];

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top Toolbar */}
      <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4">
        <div className="flex items-center space-x-4">
          <button className="p-2 hover:bg-gray-100 rounded-lg">
            <Bars3Icon className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={deck.title}
            onChange={(e) => setDeck({ ...deck, title: e.target.value })}
            className="text-lg font-semibold bg-transparent border-none outline-none"
          />
          <div className="flex items-center space-x-1 text-sm text-gray-500">
            <ClockIcon className="w-4 h-4" />
            <span>Saved</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Zoom controls */}
          <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setZoom(Math.max(25, zoom - 25))}
              className="p-1 hover:bg-gray-200 rounded"
            >
              <ArrowsPointingInIcon className="w-4 h-4" />
            </button>
            <span className="px-2 text-sm">{zoom}%</span>
            <button
              onClick={() => setZoom(Math.min(200, zoom + 25))}
              className="p-1 hover:bg-gray-200 rounded"
            >
              <ArrowsPointingOutIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Present button */}
          <button
            onClick={() => setIsPresenting(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800"
          >
            <PlayIcon className="w-4 h-4" />
            <span>Present</span>
          </button>

          {/* Export button */}
          <button
            onClick={() => exportDeck('pptx')}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <CloudArrowDownIcon className="w-4 h-4" />
            <span>Export</span>
          </button>

          {/* Share button */}
          <button className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
            <ShareIcon className="w-4 h-4" />
            <span>Share</span>
          </button>

          {/* Collaborators */}
          <div className="flex -space-x-2">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs">
              JD
            </div>
            <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-xs">
              +2
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex">
        {/* Left Sidebar - Slides */}
        <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <button
              onClick={() => addSlide()}
              className="w-full flex items-center justify-center space-x-2 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              <PlusIcon className="w-4 h-4" />
              <span>New Slide</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {deck.slides.map((slide, index) => (
              <div
                key={slide.id}
                className={`relative group cursor-pointer ${
                  index === currentSlideIndex ? 'ring-2 ring-indigo-600' : ''
                }`}
                onClick={() => setCurrentSlideIndex(index)}
              >
                <div className="aspect-[16/9] bg-white border border-gray-200 rounded-lg p-2 hover:border-gray-300">
                  <div className="text-xs text-gray-500 mb-1">Slide {index + 1}</div>
                  <div className="text-sm font-medium truncate">{slide.title || 'Untitled'}</div>
                </div>
                
                {/* Slide actions */}
                <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 flex space-x-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      duplicateSlide(index);
                    }}
                    className="p-1 bg-white rounded shadow-sm hover:bg-gray-50"
                  >
                    <DocumentDuplicateIcon className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSlide(index);
                    }}
                    className="p-1 bg-white rounded shadow-sm hover:bg-red-50 text-red-600"
                  >
                    <TrashIcon className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main Canvas */}
        <div className="flex-1 flex flex-col bg-gray-100">
          {/* Canvas Toolbar */}
          <div className="h-12 bg-white border-b border-gray-200 flex items-center px-4 space-x-4">
            {/* Text formatting */}
            <div className="flex items-center space-x-1 border-r border-gray-200 pr-4">
              <button className="p-1.5 hover:bg-gray-100 rounded">
                <BoldIcon className="w-4 h-4" />
              </button>
              <button className="p-1.5 hover:bg-gray-100 rounded">
                <ItalicIcon className="w-4 h-4" />
              </button>
              <button className="p-1.5 hover:bg-gray-100 rounded">
                <UnderlineIcon className="w-4 h-4" />
              </button>
            </div>

            {/* Insert elements */}
            <div className="flex items-center space-x-2">
              {elementTemplates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => addElement(template.id)}
                  className="p-1.5 hover:bg-gray-100 rounded flex items-center space-x-1"
                  title={template.name}
                >
                  <template.icon className="w-4 h-4" />
                </button>
              ))}
            </div>

            {/* Chart types */}
            <div className="flex items-center space-x-1 border-l border-gray-200 pl-4">
              {chartTemplates.slice(0, 4).map((chart) => (
                <button
                  key={chart.id}
                  onClick={() => addElement('chart', chart.type)}
                  className="p-1.5 hover:bg-gray-100 rounded"
                  title={chart.name}
                >
                  <chart.icon className="w-4 h-4" />
                </button>
              ))}
            </div>
          </div>

          {/* Canvas */}
          <div className="flex-1 overflow-auto p-8">
            <div
              ref={canvasRef}
              className="mx-auto bg-white shadow-xl rounded-lg relative"
              style={{
                width: `${960 * (zoom / 100)}px`,
                height: `${540 * (zoom / 100)}px`,
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'top left'
              }}
            >
              {/* Grid overlay */}
              {showGrid && (
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    backgroundImage: `
                      repeating-linear-gradient(0deg, #f3f4f6 0px, transparent 1px, transparent 20px, #f3f4f6 21px),
                      repeating-linear-gradient(90deg, #f3f4f6 0px, transparent 1px, transparent 20px, #f3f4f6 21px)
                    `
                  }}
                />
              )}

              {/* Slide content */}
              <div className="absolute inset-0 p-8">
                {currentSlide.elements.map((element) => (
                  <div
                    key={element.id}
                    className={`absolute border-2 ${
                      selectedElement?.id === element.id ? 'border-indigo-600' : 'border-transparent'
                    } hover:border-gray-300 cursor-move`}
                    style={{
                      left: `${element.position.x}px`,
                      top: `${element.position.y}px`,
                      width: `${element.position.width}px`,
                      height: `${element.position.height}px`,
                      ...element.style
                    }}
                    onClick={() => setSelectedElement(element)}
                  >
                    {/* Render element based on type */}
                    {element.type === 'text' && (
                      <div
                        contentEditable
                        suppressContentEditableWarning
                        dangerouslySetInnerHTML={{ __html: element.content.html || element.content.text }}
                        className="w-full h-full outline-none"
                        onBlur={(e) => {
                          updateElementContent(element.id, {
                            ...element.content,
                            html: e.currentTarget.innerHTML,
                            text: e.currentTarget.innerText
                          });
                        }}
                      />
                    )}

                    {element.type === 'chart' && (
                      <div className="w-full h-full">
                        {element.content.type === 'line' && <Line data={element.content.data} options={element.content.options} />}
                        {element.content.type === 'bar' && <Bar data={element.content.data} options={element.content.options} />}
                        {element.content.type === 'pie' && <Doughnut data={element.content.data} options={element.content.options} />}
                        {element.content.type === 'scatter' && <Scatter data={element.content.data} options={element.content.options} />}
                      </div>
                    )}

                    {element.type === 'table' && (
                      <table className="w-full h-full">
                        <thead>
                          <tr>
                            {element.content.headers?.map((header: string, i: number) => (
                              <th key={i} className="border border-gray-300 p-2 bg-gray-50">{header}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {element.content.rows?.map((row: string[], i: number) => (
                            <tr key={i}>
                              {row.map((cell, j) => (
                                <td key={j} className="border border-gray-300 p-2">{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {/* Resize handles */}
                    {selectedElement?.id === element.id && (
                      <>
                        <div className="absolute -top-1 -left-1 w-3 h-3 bg-indigo-600 rounded-full cursor-nw-resize" />
                        <div className="absolute -top-1 -right-1 w-3 h-3 bg-indigo-600 rounded-full cursor-ne-resize" />
                        <div className="absolute -bottom-1 -left-1 w-3 h-3 bg-indigo-600 rounded-full cursor-sw-resize" />
                        <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-indigo-600 rounded-full cursor-se-resize" />
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Slide navigation */}
          <div className="h-16 bg-white border-t border-gray-200 flex items-center justify-between px-4">
            <button
              onClick={() => setCurrentSlideIndex(Math.max(0, currentSlideIndex - 1))}
              disabled={currentSlideIndex === 0}
              className="p-2 hover:bg-gray-100 rounded-lg disabled:opacity-50"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
            
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
                Slide {currentSlideIndex + 1} of {deck.slides.length}
              </span>
            </div>
            
            <button
              onClick={() => setCurrentSlideIndex(Math.min(deck.slides.length - 1, currentSlideIndex + 1))}
              disabled={currentSlideIndex === deck.slides.length - 1}
              className="p-2 hover:bg-gray-100 rounded-lg disabled:opacity-50"
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-80 bg-white border-l border-gray-200 flex flex-col">
          {/* Sidebar tabs */}
          <div className="flex border-b border-gray-200">
            <button
              onClick={() => setSidebarTab('slides')}
              className={`flex-1 py-3 text-sm font-medium ${
                sidebarTab === 'slides' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-600'
              }`}
            >
              Slides
            </button>
            <button
              onClick={() => setSidebarTab('elements')}
              className={`flex-1 py-3 text-sm font-medium ${
                sidebarTab === 'elements' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-600'
              }`}
            >
              Elements
            </button>
            <button
              onClick={() => setSidebarTab('data')}
              className={`flex-1 py-3 text-sm font-medium ${
                sidebarTab === 'data' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-600'
              }`}
            >
              Data
            </button>
            <button
              onClick={() => setSidebarTab('ai')}
              className={`flex-1 py-3 text-sm font-medium ${
                sidebarTab === 'ai' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-600'
              }`}
            >
              AI
            </button>
          </div>

          {/* Sidebar content */}
          <div className="flex-1 overflow-y-auto p-4">
            {/* AI Assistant Tab */}
            {sidebarTab === 'ai' && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-2">AI Assistant</h3>
                  <div className="space-y-2">
                    <textarea
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="Describe what you want to create..."
                      className="w-full p-3 border border-gray-300 rounded-lg resize-none"
                      rows={4}
                    />
                    <button
                      onClick={handleAiGeneration}
                      disabled={isAiGenerating || !aiPrompt.trim()}
                      className="w-full flex items-center justify-center space-x-2 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {isAiGenerating ? (
                        <span>Generating...</span>
                      ) : (
                        <>
                          <SparklesIcon className="w-4 h-4" />
                          <span>Generate</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Quick Actions</h4>
                  <div className="space-y-1">
                    <button
                      onClick={() => setAiPrompt('Add a revenue growth chart for the last 4 quarters')}
                      className="w-full text-left p-2 hover:bg-gray-50 rounded-lg text-sm"
                    >
                      📊 Add revenue chart
                    </button>
                    <button
                      onClick={() => setAiPrompt('Create a competitive analysis slide')}
                      className="w-full text-left p-2 hover:bg-gray-50 rounded-lg text-sm"
                    >
                      🎯 Competitive analysis
                    </button>
                    <button
                      onClick={() => setAiPrompt('Generate market sizing TAM/SAM/SOM')}
                      className="w-full text-left p-2 hover:bg-gray-50 rounded-lg text-sm"
                    >
                      📈 Market sizing
                    </button>
                    <button
                      onClick={() => setAiPrompt('Add financial projections for next 5 years')}
                      className="w-full text-left p-2 hover:bg-gray-50 rounded-lg text-sm"
                    >
                      💰 Financial projections
                    </button>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Agent Commands</h4>
                  <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono space-y-1">
                    <div className="text-gray-600"># Create slide</div>
                    <div>@create slide</div>
                    <div className="text-gray-600"># Add element</div>
                    <div>@add [chart|table|text]</div>
                    <div className="text-gray-600"># Update data</div>
                    <div>@update with data</div>
                    <div className="text-gray-600"># Style</div>
                    <div>@style [modern|minimal]</div>
                  </div>
                </div>
              </div>
            )}

            {/* Data Tab */}
            {sidebarTab === 'data' && selectedElement?.type === 'chart' && (
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-900">Chart Data</h3>
                <div className="space-y-2">
                  <div>
                    <label className="text-xs text-gray-600">Labels</label>
                    <input
                      type="text"
                      value={selectedElement.content.data.labels.join(', ')}
                      onChange={(e) => {
                        const labels = e.target.value.split(',').map(l => l.trim());
                        updateElementContent(selectedElement.id, {
                          ...selectedElement.content,
                          data: {
                            ...selectedElement.content.data,
                            labels
                          }
                        });
                      }}
                      className="w-full p-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs text-gray-600">Values</label>
                    <input
                      type="text"
                      value={selectedElement.content.data.datasets[0].data.join(', ')}
                      onChange={(e) => {
                        const data = e.target.value.split(',').map(v => parseFloat(v.trim()) || 0);
                        updateElementContent(selectedElement.id, {
                          ...selectedElement.content,
                          data: {
                            ...selectedElement.content.data,
                            datasets: [{
                              ...selectedElement.content.data.datasets[0],
                              data
                            }]
                          }
                        });
                      }}
                      className="w-full p-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>

                  <div>
                    <label className="text-xs text-gray-600">Chart Type</label>
                    <select
                      value={selectedElement.content.type}
                      onChange={(e) => {
                        updateElementContent(selectedElement.id, {
                          ...selectedElement.content,
                          type: e.target.value
                        });
                      }}
                      className="w-full p-2 border border-gray-300 rounded-lg text-sm"
                    >
                      <option value="line">Line</option>
                      <option value="bar">Bar</option>
                      <option value="pie">Pie</option>
                      <option value="scatter">Scatter</option>
                      <option value="area">Area</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Elements Tab */}
            {sidebarTab === 'elements' && (
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-900">Add Elements</h3>
                <div className="grid grid-cols-2 gap-2">
                  {elementTemplates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => addElement(template.id)}
                      className="p-4 border border-gray-200 rounded-lg hover:border-indigo-600 hover:bg-indigo-50 flex flex-col items-center space-y-2"
                    >
                      <template.icon className="w-6 h-6 text-gray-600" />
                      <span className="text-sm">{template.name}</span>
                    </button>
                  ))}
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Chart Types</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {chartTemplates.map((chart) => (
                      <button
                        key={chart.id}
                        onClick={() => addElement('chart', chart.type)}
                        className="p-3 border border-gray-200 rounded-lg hover:border-indigo-600 hover:bg-indigo-50 flex items-center space-x-2"
                      >
                        <chart.icon className="w-5 h-5 text-gray-600" />
                        <span className="text-sm">{chart.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}