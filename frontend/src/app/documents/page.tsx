'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { SkeletonCard } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import Link from 'next/link';
import supabase from '@/lib/supabase';

const DOCUMENT_TYPES = [
  { value: 'other', label: 'Other / General' },
  { value: 'monthly_update', label: 'Monthly Update' },
  { value: 'board_deck', label: 'Board Deck' },
  { value: 'pitch_deck', label: 'Pitch Deck' },
  { value: 'investment_memo', label: 'Investment Memo' },
] as const;

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

interface CompanyOption { id: string; name: string; }
interface FundOption { id: string; name: string; }

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<string>('other');
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [selectedFundId, setSelectedFundId] = useState<string>('');
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [funds, setFunds] = useState<FundOption[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());

  // Wait for hydration to complete
  useEffect(() => {
    setHydrated(true);
  }, []);

  // Fetch companies and funds for linking
  useEffect(() => {
    if (!hydrated) return;
    const fetchOptions = async () => {
      try {
        const [companiesRes, fundsRes] = await Promise.all([
          supabase.from('companies').select('id, name').order('name').limit(200),
          supabase.from('funds').select('id, name').order('name').limit(50),
        ]);
        if (companiesRes.data) setCompanies(companiesRes.data.map((c: any) => ({ id: c.id, name: c.name })));
        if (fundsRes.data) setFunds(fundsRes.data.map((f: any) => ({ id: f.id, name: f.name })));
      } catch (err) {
        console.warn('Could not fetch companies/funds for linking:', err);
      }
    };
    fetchOptions();
  }, [hydrated]);

  const fetchDocuments = useCallback(async (skipCache = false) => {
    try {
      console.log('Fetching documents...');
      setLoading(true);
      setError(''); // Clear any previous errors
      const response = await fetch(`/api/documents?limit=50${skipCache ? '&nocache=1' : ''}`);
      console.log('Response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('API error response:', errorText);
        let msg = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errData = JSON.parse(errorText);
          if (errData.error) msg = errData.error;
          if (response.status === 503 && errData.details?.message) {
            msg = 'Database not configured. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment.';
          }
        } catch (_) {}
        throw new Error(msg);
      }
      const data = await response.json();
      console.log('Documents data:', data);
      if (!data || !Array.isArray(data.documents)) {
        console.warn('Unexpected data format:', data);
        setDocuments([]);
      } else {
        setDocuments(data.documents || []);
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError(err instanceof Error ? err.message : 'Failed to load documents');
      setDocuments([]); // Ensure documents array is set even on error
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
    const fileList = event.target.files;
    if (!fileList?.length) return;

    const files = Array.from(fileList);
    setUploading(true);
    setUploadProgress(0);
    setError('');

    try {
      if (files.length > 1) {
        // Batch upload: one request, N docs in processed_documents, processing in background
        const formData = new FormData();
        for (const file of files) {
          formData.append('file', file);
        }
        formData.append('document_type', documentType);
        if (selectedCompanyId) formData.append('company_id', selectedCompanyId);
        if (selectedFundId) formData.append('fund_id', selectedFundId);
        const res = await fetch('/api/documents/batch', {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || res.statusText);
        }
        setUploadProgress(100);
        const data = await res.json();
        console.log('Batch upload:', data.documentIds?.length ?? 0, 'documents');
      } else {
        // Single file: existing flow (upload + process in one request)
        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('document_type', documentType);
        if (selectedCompanyId) formData.append('company_id', selectedCompanyId);
        if (selectedFundId) formData.append('fund_id', selectedFundId);
        const xhr = new XMLHttpRequest();
        await new Promise<void>((resolve, reject) => {
          xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
          });
          xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              setUploadProgress(100);
              resolve();
            } else {
              let msg = xhr.statusText;
              try {
                const d = JSON.parse(xhr.responseText);
                msg = d.error || msg;
                if (xhr.status === 503 && d.details?.hasUrl === false) {
                  msg = 'Database not configured. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.';
                }
              } catch (_) {}
              reject(new Error(msg));
            }
          });
          xhr.addEventListener('error', () => reject(new Error('Network error')));
          xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
          xhr.open('POST', '/api/documents');
          xhr.send(formData);
        });
      }

      setTimeout(() => { void fetchDocuments(true); }, 1000);
    } catch (err) {
      console.error('Upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadProgress(0);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }, [fetchDocuments, documentType]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Documents</h1>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonCard key={i} className="mb-4" />
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
          <Button onClick={() => fetchDocuments()} className="mt-2">
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
          {uploading && (
            <div className="flex items-center space-x-2">
              <Progress value={uploadProgress} className="w-32" />
              <span className="text-sm text-gray-600">{uploadProgress}%</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Label htmlFor="doc-type" className="text-sm text-gray-600 whitespace-nowrap">Doc type:</Label>
            <Select value={documentType} onValueChange={setDocumentType}>
              <SelectTrigger id="doc-type" className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {companies.length > 0 && (
            <div className="flex items-center gap-2">
              <Label htmlFor="company-link" className="text-sm text-gray-600 whitespace-nowrap">Company:</Label>
              <Select value={selectedCompanyId || "__none__"} onValueChange={(v) => setSelectedCompanyId(v === "__none__" ? "" : v)}>
                <SelectTrigger id="company-link" className="w-[160px]">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {companies.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {funds.length > 0 && (
            <div className="flex items-center gap-2">
              <Label htmlFor="fund-link" className="text-sm text-gray-600 whitespace-nowrap">Fund:</Label>
              <Select value={selectedFundId || "__none__"} onValueChange={(v) => setSelectedFundId(v === "__none__" ? "" : v)}>
                <SelectTrigger id="fund-link" className="w-[140px]">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {funds.map((f) => (
                    <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors">
            <span>Upload Document</span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              multiple
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>
      </div>
      
      {/* Multi-doc actions */}
      {selectedDocs.size > 0 && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-800">{selectedDocs.size} selected</span>
          <Button
            size="sm"
            onClick={async () => {
              try {
                const docIds = Array.from(selectedDocs);
                const res = await fetch('/api/export/deck', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ documentIds: docIds, outputFormat: 'memo' }),
                });
                if (res.ok) {
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `memo-${Date.now()}.pdf`;
                  a.click();
                  URL.revokeObjectURL(url);
                }
              } catch (err) {
                console.error('Memo generation failed:', err);
              }
            }}
          >
            Generate Memo
          </Button>
          <Button variant="outline" size="sm" onClick={() => setSelectedDocs(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {documents.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600 mb-4">No documents found</p>
          <p className="text-sm text-gray-500">Upload a document to get started</p>
        </div>
      ) : (
        <div className="space-y-4">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-start gap-3">
              <input
                type="checkbox"
                className="mt-6 h-4 w-4 rounded border-gray-300"
                checked={selectedDocs.has(doc.id)}
                onChange={(e) => {
                  setSelectedDocs(prev => {
                    const next = new Set(prev);
                    if (e.target.checked) next.add(doc.id);
                    else next.delete(doc.id);
                    return next;
                  });
                }}
              />
              <div className="flex-1">
                <DocumentCard
                  document={doc}
                  onViewAnalysis={handleViewAnalysis}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
