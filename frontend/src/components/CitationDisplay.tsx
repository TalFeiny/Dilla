'use client';

import React, { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, FileText, Calendar, Link2 } from 'lucide-react';

interface Citation {
  id: number;
  number: number;
  source: string;
  date: string;
  title: string;
  content: string;
  url?: string;
  metadata?: Record<string, any>;
}

interface CitationDisplayProps {
  citations: Citation[];
  synthesis?: string;
  format?: 'inline' | 'bibliography' | 'both';
  className?: string;
}

export const CitationDisplay: React.FC<CitationDisplayProps> = ({
  citations,
  synthesis,
  format = 'both',
  className = ''
}) => {
  const [expandedCitations, setExpandedCitations] = useState<Set<number>>(new Set());
  const [showAllCitations, setShowAllCitations] = useState(false);

  const toggleCitation = (citationNumber: number) => {
    const newExpanded = new Set(expandedCitations);
    if (newExpanded.has(citationNumber)) {
      newExpanded.delete(citationNumber);
    } else {
      newExpanded.add(citationNumber);
    }
    setExpandedCitations(newExpanded);
  };

  const renderInlineText = (text: string) => {
    // Replace [1], [2] etc with clickable links
    const citationPattern = /\[(\d+)\]/g;
    const parts = text.split(citationPattern);
    
    return parts.map((part, index) => {
      // Check if this part is a citation number
      const citationNum = parseInt(part);
      if (!isNaN(citationNum) && citations.find(c => c.number === citationNum)) {
        return (
          <sup key={index}>
            <a
              href={`#citation-${citationNum}`}
              className="text-blue-600 hover:text-blue-800 font-semibold mx-0.5 transition-colors"
              onClick={(e) => {
                e.preventDefault();
                const element = document.getElementById(`citation-${citationNum}`);
                element?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              [{citationNum}]
            </a>
          </sup>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const renderCitation = (citation: Citation, isExpanded: boolean) => (
    <li
      key={citation.number}
      id={`citation-${citation.number}`}
      className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
              {citation.number}
            </span>
            {citation.url ? (
              <a
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 group"
              >
                {citation.title}
                <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
              </a>
            ) : (
              <span className="font-medium text-gray-900">{citation.title}</span>
            )}
          </div>
          
          <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3" />
              {citation.source}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {citation.date}
            </span>
          </div>

          {isExpanded && (
            <div className="mt-3 p-3 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-700 italic">
                "{citation.content}"
              </p>
              {citation.metadata && Object.keys(citation.metadata).length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-500">Additional metadata:</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {Object.entries(citation.metadata).map(([key, value]) => (
                      <span key={key} className="text-xs bg-white px-2 py-1 rounded border border-gray-200">
                        {key}: {String(value)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        
        <button
          onClick={() => toggleCitation(citation.number)}
          className="ml-4 p-1 hover:bg-gray-100 rounded transition-colors"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          )}
        </button>
      </div>
    </li>
  );

  const displayCitations = showAllCitations ? citations : citations.slice(0, 5);

  return (
    <div className={`citation-display ${className}`}>
      {format !== 'bibliography' && synthesis && (
        <div className="synthesis-section mb-6">
          <div className="prose max-w-none">
            {renderInlineText(synthesis)}
          </div>
        </div>
      )}

      {format !== 'inline' && citations.length > 0 && (
        <div className="citations-bibliography">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Link2 className="w-5 h-5" />
              Sources & Citations
              <span className="text-sm font-normal text-gray-500">
                ({citations.length} total)
              </span>
            </h3>
            
            {citations.length > 5 && (
              <button
                onClick={() => setShowAllCitations(!showAllCitations)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                {showAllCitations ? 'Show Less' : `Show All ${citations.length} Citations`}
              </button>
            )}
          </div>

          <ol className="space-y-3">
            {displayCitations.map((citation) => 
              renderCitation(citation, expandedCitations.has(citation.number))
            )}
          </ol>

          {!showAllCitations && citations.length > 5 && (
            <div className="mt-4 text-center">
              <button
                onClick={() => setShowAllCitations(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700"
              >
                <ChevronDown className="w-4 h-4" />
                View {citations.length - 5} More Citations
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CitationDisplay;