'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

interface CustomAnalysisData {
  executive_summary?: string;
  financial_analysis?: string;
  operational_analysis?: string;
  market_analysis?: string;
  risk_assessment?: string;
  strategic_recommendations?: string;
}

interface AnalysisResponse {
  extracted_data: CustomAnalysisData;
  analysis_summary: {
    total_sections: number;
    analysis_completed: boolean;
    market_data_found: number;
    processing_time: string;
  };
  raw_text_preview: string;
  document_metadata: {
    filename: string;
    processed_at: string;
    document_type: string;
    analysis_version: string;
  };
}

export default function CustomAnalysisPage() {
  const params = useParams();
  const documentId = params.id as string;
  
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('executive_summary');

  useEffect(() => {
    fetchAnalysis();
  }, Array.from(umentId));

  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/documents/${documentId}/analysis`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch analysis');
      }
      
      const data = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const formatSectionTitle = (title: string) => {
    return title.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const renderSection = (sectionKey: string, content: string) => {
    if (!content) return null;
    
    return (
      <div key={sectionKey} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {formatSectionTitle(sectionKey)}
        </h3>
        <div className="prose prose-sm max-w-none">
          {content.split('\n').map((paragraph, index) => (
            <p key={index} className="text-gray-700 mb-3 leading-relaxed">
              {paragraph}
            </p>
          ))}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading comprehensive analysis...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-red-800 mb-2">Error Loading Analysis</h2>
            <p className="text-red-700 mb-4">{error}</p>
            <Link 
              href="/documents"
              className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              ← Back to Documents
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Analysis Not Found</h2>
            <p className="text-gray-600 mb-4">The analysis for this document could not be found.</p>
            <Link 
              href="/documents"
              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              ← Back to Documents
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const sections = analysis.extracted_data;
  const sectionKeys = Object.keys(sections).filter(key => sections[key as keyof CustomAnalysisData]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <nav className="flex" aria-label="Breadcrumb">
                  <ol className="flex items-center space-x-4">
                    <li>
                      <Link href="/documents" className="text-gray-500 hover:text-gray-700">
                        Documents
                      </Link>
                    </li>
                    <li>
                      <div className="flex items-center">
                        <svg className="flex-shrink-0 h-5 w-5 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                        <span className="ml-4 text-sm font-medium text-gray-500">
                          {analysis.document_metadata.filename}
                        </span>
                      </div>
                    </li>
                  </ol>
                </nav>
                <h1 className="mt-2 text-2xl font-bold text-gray-900">
                  Comprehensive Analysis
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                  Detailed analysis completed on {new Date(analysis.document_metadata.processed_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center space-x-3">
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                  Custom Analysis
                </span>
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                  v{analysis.document_metadata.analysis_version}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Analysis Summary */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Analysis Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{analysis.analysis_summary.total_sections}</div>
              <div className="text-sm text-gray-600">Analysis Sections</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {analysis.analysis_summary.analysis_completed ? '✓' : '✗'}
              </div>
              <div className="text-sm text-gray-600">Analysis Status</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{analysis.analysis_summary.market_data_found}</div>
              <div className="text-sm text-gray-600">Market Data Points</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {new Date(analysis.analysis_summary.processing_time).toLocaleTimeString()}
              </div>
              <div className="text-sm text-gray-600">Processing Time</div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-8">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8 px-6" aria-label="Tabs">
              {sectionKeys.map((sectionKey) => (
                <button
                  key={sectionKey}
                  onClick={() => setActiveTab(sectionKey)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === sectionKey
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {formatSectionTitle(sectionKey)}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-6">
          {activeTab && sections[activeTab as keyof CustomAnalysisData] && (
            renderSection(activeTab, sections[activeTab as keyof CustomAnalysisData]!)
          )}
        </div>

        {/* Raw Text Preview */}
        {analysis.raw_text_preview && (
          <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Document Text Preview</h3>
            <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                {analysis.raw_text_preview}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
} 