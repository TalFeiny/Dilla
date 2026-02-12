'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import dynamic from 'next/dynamic';
import { 
  Bold, 
  Italic, 
  Underline, 
  List, 
  Heading1,
  Heading2,
  Quote,
  Code,
  Link,
  Image,
  BarChart3,
  Save,
  Download,
  Sparkles,
  FileText,
  Loader2
} from 'lucide-react';

// Model router: AI calls go via /api/agent/unified-brain → backend → model_router
const TableauLevelCharts = dynamic(
  () => import('@/components/charts/TableauLevelCharts'),
  { ssr: false }
);

interface DocumentSection {
  type: 'heading1' | 'heading2' | 'heading3' | 'paragraph' | 'chart' | 'list' | 'quote' | 'code' | 'image';
  content?: string;
  chart?: any;
  items?: string[];
  imageUrl?: string;
  imageCaption?: string;
}

export default function DocsPage() {
  const [sections, setSections] = useState<DocumentSection[]>([
    { type: 'heading1', content: 'New Document' },
    { type: 'paragraph', content: 'Start typing or use AI to generate content...' }
  ]);
  const [selectedSection, setSelectedSection] = useState<number>(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [documentTitle, setDocumentTitle] = useState('Untitled Document');
  const contentEditableRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const sectionsRef = useRef(sections);
  const selectedSectionRef = useRef(selectedSection);
  sectionsRef.current = sections;
  selectedSectionRef.current = selectedSection;

  const handleImageFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const imageUrl = (e.target?.result ?? '') as string;
      const imageSection: DocumentSection = {
        type: 'image',
        imageUrl,
        imageCaption: 'Click to add caption...'
      };
      const newSections = [...sectionsRef.current];
      newSections.splice(selectedSectionRef.current + 1, 0, imageSection);
      setSections(newSections);
      setSelectedSection(selectedSectionRef.current + 1);
    };
    reader.readAsDataURL(file);
  }, []);

  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of Array.from(items)) {
        if (item.type.indexOf('image') !== -1) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) handleImageFile(file);
          break;
        }
      }
    };

    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = e.dataTransfer?.files;
      if (!files) return;
      for (const file of Array.from(files)) {
        if (file.type.startsWith('image/')) {
          handleImageFile(file);
          break;
        }
      }
    };

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(true);
    };

    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
    };

    document.addEventListener('paste', handlePaste);
    document.addEventListener('drop', handleDrop);
    document.addEventListener('dragover', handleDragOver);
    document.addEventListener('dragleave', handleDragLeave);
    return () => {
      document.removeEventListener('paste', handlePaste);
      document.removeEventListener('drop', handleDrop);
      document.removeEventListener('dragover', handleDragOver);
      document.removeEventListener('dragleave', handleDragLeave);
    };
  }, [handleImageFile]);

  // Upload and process document via model router
  const handleDocumentUpload = async (file: File) => {
    setIsGenerating(true);
    try {
      // First upload to Supabase storage
      const formData = new FormData();
      formData.append('file', file);
      
      const uploadResponse = await fetch('/api/documents', {
        method: 'POST',
        body: formData,
      });
      
      if (!uploadResponse.ok) {
        throw new Error('Failed to upload document');
      }
      
      const uploadResult = await uploadResponse.json();
      
      // Then process via model router (unified-brain)
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: `Analyze the uploaded document (ID: ${uploadResult.document?.id || 'unknown'}) and generate a summary with key insights, metrics, and recommendations. Format as a document with sections.`,
          outputFormat: 'docs',
          documentId: uploadResult.document?.id,
          includeFormulas: false,
          includeCitations: true
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.result) {
          // Process the document sections (same as generateWithAI)
          const newSections: DocumentSection[] = [];
          
          if (data.result.format === 'docs') {
            if (data.result.content) {
              const lines = data.result.content.split('\n');
              let currentParagraph = '';
              
              for (const line of lines) {
                if (line.startsWith('# ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading1', content: line.slice(2) });
                } else if (line.startsWith('## ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading2', content: line.slice(3) });
                } else if (line.startsWith('### ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading3', content: line.slice(4) });
                } else if (line.trim() === '') {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                } else {
                  currentParagraph += (currentParagraph ? ' ' : '') + line;
                }
              }
              
              if (currentParagraph) {
                newSections.push({ type: 'paragraph', content: currentParagraph });
              }
            }
            
            if (data.result.sections && Array.isArray(data.result.sections)) {
              data.result.sections.forEach((section: any) => {
                if (section.type === 'chart' && section.chart) {
                  newSections.push({
                    type: 'chart',
                    chart: section.chart
                  });
                } else {
                  newSections.push({
                    type: section.type as any,
                    content: section.content
                  });
                }
              });
            }
            
            if (data.result.charts && Array.isArray(data.result.charts)) {
              data.result.charts.forEach((chart: any) => {
                newSections.push({
                  type: 'chart',
                  chart: chart
                });
              });
            }
          }
          
          if (newSections.length > 0) {
            setSections(newSections);
            const firstHeading = newSections.find(s => s.type === 'heading1');
            if (firstHeading?.content) {
              setDocumentTitle(firstHeading.content);
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to process document:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Generate document with AI — model router path: unified-brain → backend → model_router
  const generateWithAI = async () => {
    if (!aiPrompt.trim()) return;
    
    setIsGenerating(true);
    try {
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: aiPrompt,
          outputFormat: 'docs',
          includeFormulas: false,
          includeCitations: true
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.result) {
          // Process the document sections
          const newSections: DocumentSection[] = [];
          
          // Handle unified format where format: 'docs' is present
          if (data.result.format === 'docs') {
            console.log('[DocsPage] Processing unified docs format');

            // Prefer structured sections over raw markdown content
            if (data.result.sections && Array.isArray(data.result.sections) && data.result.sections.length > 0) {
              data.result.sections.forEach((section: any) => {
                if (section.type === 'chart' && section.chart) {
                  newSections.push({
                    type: 'chart',
                    chart: section.chart
                  });
                } else if (section.type === 'list' && section.items) {
                  newSections.push({
                    type: 'list' as any,
                    items: section.items
                  });
                } else {
                  newSections.push({
                    type: section.type as any,
                    content: section.content || section.section
                  });
                }
              });
            } else if (data.result.content) {
              // Fallback: Parse content as markdown only if no structured sections
              const lines = data.result.content.split('\n');
              let currentParagraph = '';

              for (const line of lines) {
                if (line.startsWith('# ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading1', content: line.slice(2) });
                } else if (line.startsWith('## ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading2', content: line.slice(3) });
                } else if (line.startsWith('### ')) {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                  newSections.push({ type: 'heading3', content: line.slice(4) });
                } else if (line.trim() === '') {
                  if (currentParagraph) {
                    newSections.push({ type: 'paragraph', content: currentParagraph });
                    currentParagraph = '';
                  }
                } else {
                  currentParagraph += (currentParagraph ? ' ' : '') + line;
                }
              }

              if (currentParagraph) {
                newSections.push({ type: 'paragraph', content: currentParagraph });
              }
            }

            // Add standalone charts if present
            if (data.result.charts && Array.isArray(data.result.charts)) {
              data.result.charts.forEach((chart: any) => {
                newSections.push({
                  type: 'chart',
                  chart: chart
                });
              });
            }
          } else if (data.result.sections) {
            // Legacy format
            data.result.sections.forEach((section: any) => {
              if (section.type === 'chart' && section.chart) {
                newSections.push({
                  type: 'chart',
                  chart: section.chart
                });
              } else {
                newSections.push({
                  type: section.type as any,
                  content: section.content
                });
              }
            });
          }
          
          if (newSections.length > 0) {
            setSections(newSections);
            // Set title from first heading
            const firstHeading = newSections.find(s => s.type === 'heading1');
            if (firstHeading?.content) {
              setDocumentTitle(firstHeading.content);
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to generate document:', error);
    } finally {
      setIsGenerating(false);
      setAiPrompt('');
    }
  };

  // Format selected text
  const formatText = (format: string) => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    
    switch (format) {
      case 'bold':
        document.execCommand('bold');
        break;
      case 'italic':
        document.execCommand('italic');
        break;
      case 'underline':
        document.execCommand('underline');
        break;
      case 'link':
        const url = prompt('Enter URL:');
        if (url) document.execCommand('createLink', false, url);
        break;
    }
  };

  // Add new section
  const addSection = (type: DocumentSection['type']) => {
    const newSection: DocumentSection = { type };
    
    switch (type) {
      case 'heading1':
        newSection.content = 'New Heading';
        break;
      case 'heading2':
        newSection.content = 'New Subheading';
        break;
      case 'paragraph':
        newSection.content = 'New paragraph...';
        break;
      case 'list':
        newSection.items = ['Item 1', 'Item 2', 'Item 3'];
        break;
      case 'quote':
        newSection.content = 'Enter a quote...';
        break;
      case 'code':
        newSection.content = '// Code snippet';
        break;
      case 'chart':
        // Placeholder uses TableauLevelCharts-supported type (model router via unified-brain)
        newSection.chart = {
          type: 'pie',
          title: 'Sample Chart',
          data: [
            { name: 'A', value: 10 },
            { name: 'B', value: 20 },
            { name: 'C', value: 30 }
          ]
        };
        break;
    }
    
    const newSections = [...sections];
    newSections.splice(selectedSection + 1, 0, newSection);
    setSections(newSections);
    setSelectedSection(selectedSection + 1);
  };

  // Update section content
  const updateSection = (index: number, content: string) => {
    const newSections = [...sections];
    newSections[index] = { ...newSections[index], content };
    setSections(newSections);
  };

  // Delete section
  const deleteSection = (index: number) => {
    if (sections.length <= 1) return;
    const newSections = sections.filter((_, i) => i !== index);
    setSections(newSections);
    if (selectedSection >= newSections.length) {
      setSelectedSection(newSections.length - 1);
    }
  };

  // Export document
  const exportDocument = () => {
    const content = sections.map(section => {
      switch (section.type) {
        case 'heading1':
          return `# ${section.content}\n`;
        case 'heading2':
          return `## ${section.content}\n`;
        case 'heading3':
          return `### ${section.content}\n`;
        case 'paragraph':
          return `${section.content}\n`;
        case 'list':
          return section.items?.map(item => `- ${item}`).join('\n') + '\n';
        case 'quote':
          return `> ${section.content}\n`;
        case 'code':
          return `\`\`\`\n${section.content}\n\`\`\`\n`;
        case 'chart':
          return `[Chart: ${section.chart?.title || 'Untitled'}]\n`;
        default:
          return '';
      }
    }).join('\n');

    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${documentTitle}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Render section content
  const renderSection = (section: DocumentSection, index: number) => {
    const isSelected = index === selectedSection;
    
    switch (section.type) {
      case 'heading1':
        return (
          <h1 
            className={`text-3xl font-bold mb-4 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            {section.content}
          </h1>
        );
      
      case 'heading2':
        return (
          <h2
            className={`text-2xl font-semibold mb-3 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            {section.content}
          </h2>
        );

      case 'heading3':
        return (
          <h3
            className={`text-xl font-medium mb-2 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            {section.content}
          </h3>
        );

      case 'paragraph':
        return (
          <p 
            className={`mb-4 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            {section.content}
          </p>
        );
      
      case 'list':
        return (
          <ul className={`list-disc list-inside mb-4 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}>
            {section.items?.map((item, i) => (
              <li 
                key={i}
                contentEditable
                suppressContentEditableWarning
                onClick={() => setSelectedSection(index)}
                onBlur={(e) => {
                  const newItems = [...(section.items || [])];
                  newItems[i] = e.currentTarget.textContent || '';
                  const newSections = [...sections];
                  newSections[index] = { ...newSections[index], items: newItems };
                  setSections(newSections);
                }}
              >
                {item}
              </li>
            ))}
          </ul>
        );
      
      case 'quote':
        return (
          <blockquote 
            className={`border-l-4 border-gray-300 pl-4 italic mb-4 p-2 rounded ${isSelected ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            {section.content}
          </blockquote>
        );
      
      case 'code':
        return (
          <pre 
            className={`bg-gray-100 p-4 rounded mb-4 font-mono text-sm ${isSelected ? 'ring-2 ring-blue-500' : ''}`}
            contentEditable
            suppressContentEditableWarning
            onClick={() => setSelectedSection(index)}
            onBlur={(e) => updateSection(index, e.currentTarget.textContent || '')}
          >
            <code>{section.content}</code>
          </pre>
        );
      
      case 'chart':
        return (
          <div 
            className={`mb-6 p-4 border rounded-lg ${isSelected ? 'ring-2 ring-blue-500' : ''}`}
            onClick={() => setSelectedSection(index)}
          >
            {section.chart && (
              <TableauLevelCharts
                type={(section.chart.type ?? 'pie') as any}
                data={section.chart.data}
                title={section.chart.title}
                colors={section.chart.colors}
                height={400}
                interactive={true}
              />
            )}
          </div>
        );
      
      case 'image':
        return (
          <div 
            className={`mb-6 text-center ${isSelected ? 'ring-2 ring-blue-500 p-2 rounded' : ''}`}
            onClick={() => setSelectedSection(index)}
          >
            {section.imageUrl && (
              <>
                <img 
                  src={section.imageUrl} 
                  alt={section.imageCaption || 'Document image'}
                  className="max-w-full h-auto rounded-lg shadow-lg mx-auto"
                  style={{ maxHeight: '600px' }}
                />
                <p 
                  className="mt-2 text-sm text-gray-600 italic"
                  contentEditable
                  suppressContentEditableWarning
                  onBlur={(e) => {
                    const newSections = [...sections];
                    newSections[index] = { 
                      ...newSections[index], 
                      imageCaption: e.currentTarget.textContent || '' 
                    };
                    setSections(newSections);
                  }}
                >
                  {section.imageCaption}
                </p>
              </>
            )}
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <FileText className="w-6 h-6 text-blue-600" />
              <Input
                value={documentTitle}
                onChange={(e) => setDocumentTitle(e.target.value)}
                className="text-lg font-semibold border-0 focus:ring-0"
                placeholder="Document Title"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm" onClick={exportDocument}>
                <Download className="w-4 h-4 mr-1" />
                Export
              </Button>
              <Button variant="outline" size="sm">
                <Save className="w-4 h-4 mr-1" />
                Save
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white border-b sticky top-16 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-1 py-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => formatText('bold')}
              title="Bold"
            >
              <Bold className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => formatText('italic')}
              title="Italic"
            >
              <Italic className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => formatText('underline')}
              title="Underline"
            >
              <Underline className="w-4 h-4" />
            </Button>
            <div className="w-px h-6 bg-gray-300 mx-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('heading1')}
              title="Heading 1"
            >
              <Heading1 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('heading2')}
              title="Heading 2"
            >
              <Heading2 className="w-4 h-4" />
            </Button>
            <div className="w-px h-6 bg-gray-300 mx-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('list')}
              title="Bullet List"
            >
              <List className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('quote')}
              title="Quote"
            >
              <Quote className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('code')}
              title="Code"
            >
              <Code className="w-4 h-4" />
            </Button>
            <div className="w-px h-6 bg-gray-300 mx-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSection('chart')}
              title="Insert Chart"
            >
              <BarChart3 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => formatText('link')}
              title="Insert Link"
            >
              <Link className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'image/*';
                input.onchange = (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (file) handleImageFile(file);
                };
                input.click();
              }}
              title="Insert Image"
            >
              <Image className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* AI Generation Bar */}
        <Card className="mb-6 p-4">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <Input
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              placeholder="Generate document with AI... (e.g., 'Write an investment memo for @Stripe')"
              className="flex-1"
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !isGenerating) {
                  generateWithAI();
                }
              }}
              disabled={isGenerating}
            />
            <Button 
              onClick={generateWithAI}
              disabled={isGenerating || !aiPrompt.trim()}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                'Generate'
              )}
            </Button>
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              className="hidden"
              id="document-upload"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  handleDocumentUpload(file);
                }
              }}
              disabled={isGenerating}
            />
            <Button
              onClick={() => document.getElementById('document-upload')?.click()}
              disabled={isGenerating}
              variant="outline"
              title="Upload and analyze document via model router"
            >
              <FileText className="w-4 h-4 mr-2" />
              Upload Doc
            </Button>
          </div>
        </Card>

        {/* Document Content */}
        <Card className={`min-h-[600px] p-8 relative ${isDragging ? 'border-4 border-dashed border-blue-500 bg-blue-50' : ''}`}>
          {isDragging && (
            <div className="absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-90 z-10 rounded-lg">
              <div className="text-center">
                <Image className="w-12 h-12 mx-auto mb-2 text-blue-600" />
                <p className="text-lg font-semibold text-blue-600">Drop image here</p>
              </div>
            </div>
          )}
          <div 
            ref={contentEditableRef}
            className="prose prose-lg max-w-none"
          >
            {sections.map((section, index) => (
              <div key={index} className="relative group">
                {renderSection(section, index)}
                {selectedSection === index && (
                  <button
                    onClick={() => deleteSection(index)}
                    className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 transition-opacity"
                    title="Delete section"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Help Text */}
        <div className="mt-4 text-sm text-gray-500 text-center">
          Click on any section to edit. Use the toolbar to format text or add new sections. 
          Paste (Ctrl/Cmd+V) or drag & drop images directly into the document.
        </div>
      </div>
    </div>
  );
}