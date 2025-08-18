'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import Link from 'next/link';

interface Document {
  id: string;
  filename: string;
  status: string;
  document_type: string;
  upload_date: string;
  processed: boolean;
  file_size?: number;
  processing_time?: number;
}

const DocumentSkeleton = () => (
  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-4 animate-pulse">
    <div className="flex items-center justify-between mb-4">
      <div className="flex-1 min-w-0">
        <div className="h-6 bg-gray-200 rounded mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-1/3"></div>
      </div>
      <div className="flex items-center space-x-3 ml-4">
        <div className="h-6 bg-gray-200 rounded w-16"></div>
        <div className="h-6 bg-gray-200 rounded w-20"></div>
      </div>
    </div>
  </div>
);

const DocumentCard = React.memo(({ 
  document, 
  onViewAnalysis 
}: { 
  document: Document; 
  onViewAnalysis: (documentId: string) => void;
}) => {
  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'processing': return 'bg-yellow-100 text-yellow-800';
      case 'pending': return 'bg-gray-100 text-gray-800';
      case 'failed': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  }, []);

  const formatFileSize = useCallback((bytes?: number) => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  }, []);

  const formatDate = useCallback((dateString: string) => {
    const date = new Date(dateString);
    const year = date.getFullYear();
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = monthNames[date.getMonth()];
    const day = date.getDate();
    return `${month} ${day}, ${year}`;
  }, []);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 truncate">
            {document.filename}
          </h3>
          <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
            <span>{document.document_type || 'Unknown'}</span>
            <span>•</span>
            <span>{formatDate(document.upload_date)}</span>
            {document.file_size ? (
              <>
                <span>•</span>
                <span>{formatFileSize(document.file_size)}</span>
              </>
            ) : null}
          </div>
        </div>
        <div className="flex items-center space-x-3 ml-4">
          <Badge className={getStatusColor(document.status)}>
            {document.status}
          </Badge>
          <div className="text-xs text-gray-500">
            Processed: {document.processed ? 'Yes' : 'No'}
          </div>
          <Link href={`/documents/${document.id}/analysis`}>
            <Button variant="outline" size="sm">
              View Analysis
            </Button>
          </Link>
        </div>
      </div>
      
      {document.processing_time ? (
        <div className="text-xs text-gray-500">
          Processing time: {document.processing_time}s
        </div>
      ) : null}
    </div>
  );
});

DocumentCard.displayName = 'DocumentCard';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Wait for hydration to complete
  useEffect(() => {
    setHydrated(true);
  }, []);

  const fetchDocuments = useCallback(async () => {
    try {
      console.log('Fetching documents...');
      setLoading(true);
      const response = await fetch('/api/documents?limit=50');
      console.log('Response status:', response.status);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Documents data:', data);
      setDocuments(data.documents || []);
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, []);

  // Only fetch after hydration is complete
  useEffect(() => {
    if (hydrated) {
      fetchDocuments();
    }
  }, [fetchDocuments, hydrated]);

  const handleViewAnalysis = useCallback((documentId: string) => {
    // This function is no longer needed since we're using direct links
    console.log('View analysis for document:', documentId);
  }, []);

  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/documents', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Upload successful:', result);
      
      await fetchDocuments();
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
      event.target.value = '';
    }
  }, [fetchDocuments]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Documents</h1>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <DocumentSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Documents</h1>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <Button onClick={fetchDocuments} className="mt-2">
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Documents</h1>
        
        <div className="flex items-center space-x-4">
          {uploading ? (
            <div className="flex items-center space-x-2">
              <Progress value={uploadProgress} className="w-32" />
              <span className="text-sm text-gray-600">Uploading...</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <div className="w-32 h-2 bg-gray-200 rounded"></div>
              <span className="text-sm text-gray-400 invisible">Uploading...</span>
            </div>
          )}
          
          <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors">
            <span>Upload Document</span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>
      </div>
      
      {documents.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600 mb-4">No documents found</p>
          <p className="text-sm text-gray-500">Upload a document to get started</p>
        </div>
      ) : (
        <div className="space-y-4">
          {documents.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              onViewAnalysis={handleViewAnalysis}
            />
          ))}
        </div>
      )}
    </div>
  );
}
