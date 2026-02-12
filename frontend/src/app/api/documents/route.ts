import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * @swagger
 * /api/documents:
 *   get:
 *     summary: Get all documents
 *     description: Retrieve a paginated list of documents with optional filtering
 *     tags: [Documents]
 *     parameters:
 *       - in: query
 *         name: page
 *         schema:
 *           type: integer
 *           default: 1
 *         description: Page number for pagination
 *       - in: query
 *         name: limit
 *         schema:
 *           type: integer
 *           default: 10
 *         description: Number of documents per page
 *       - in: query
 *         name: document_type
 *         schema:
 *           type: string
 *           enum: [all, pitch_deck, financial_statement, due_diligence, term_sheet, investment_memo, other]
 *         description: Filter by document type
 *       - in: query
 *         name: processed
 *         schema:
 *           type: string
 *           enum: [all, true, false]
 *         description: Filter by processing status
 *     responses:
 *       200:
 *         description: List of documents retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DocumentsResponse'
 *       500:
 *         description: Internal server error
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Error'
 *   post:
 *     summary: Upload and process a document
 *     description: Upload a VC document (PDF, DOCX, etc.) and process it with AI to extract key metrics
 *     tags: [Documents]
 *     requestBody:
 *       required: true
 *       content:
 *         multipart/form-data:
 *           schema:
 *             type: object
 *             properties:
 *               document:
 *                 type: string
 *                 format: binary
 *                 description: The document file to upload
 *               document_type:
 *                 type: string
 *                 enum: [pitch_deck, financial_statement, due_diligence, term_sheet, investment_memo, other]
 *                 description: Type of document being uploaded
 *     responses:
 *       201:
 *         description: Document uploaded and processed successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 documentId:
 *                   type: string
 *                 message:
 *                   type: string
 *                 document:
 *                   $ref: '#/components/schemas/DocumentMetadata'
 *                 processing:
 *                   $ref: '#/components/schemas/ProcessingResult'
 *       400:
 *         description: Bad request - invalid file or missing data
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Error'
 *       500:
 *         description: Server error during processing
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Error'
 */

// Cache configuration
const CACHE_TTL = 2 * 60 * 1000; // 2 minutes for faster updates
const cache = new Map<string, { data: any; timestamp: number }>();

// Clean up old cache entries every 5 minutes
function cleanupCache() {
  const now = Date.now();
  for (const [key, value] of cache.entries()) {
    if (now - value.timestamp > CACHE_TTL) {
      cache.delete(key);
    }
  }
}

// Run cleanup every 5 minutes
setInterval(cleanupCache, 5 * 60 * 1000);

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      console.error('Supabase service not initialized');
      const hasUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
      const hasKey = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
      return NextResponse.json({
        error: 'Database connection not available',
        details: {
          hasUrl,
          hasKey,
          message: 'Missing required environment variables: NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'
        },
        documents: [],
        pagination: { page: 1, limit: 10, total: 0, hasMore: false }
      }, { status: 503 });
    }

    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '10');
    const status = searchParams.get('status');
    const processed = searchParams.get('processed');
    const nocache = searchParams.get('nocache');
    
    const offset = (page - 1) * limit;

    // Check cache first (skip if nocache=1 for post-upload refresh)
    const cacheKey = `documents_${page}_${limit}_${status}_${processed}`;
    const cached = !nocache && cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return NextResponse.json(cached.data, {
        headers: {
          'Cache-Control': 'public, max-age=30, stale-while-revalidate=60',
          'X-Cache': 'HIT'
        }
      });
    }

    // Query with all needed columns (company_id, fund_id for document linkage)
    let query = supabaseService
      .from('processed_documents')
      .select('id, storage_path, status, document_type, created_at, processed_at, processing_summary, extracted_data, company_id, fund_id')
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (status) {
      query = query.eq('status', status);
    }

    if (processed !== null && processed !== undefined) {
      // processed is a string from query params: 'true', 'false', or null
      if (processed === 'true') {
        query = query.eq('status', 'completed');
      } else if (processed === 'false') {
        query = query.neq('status', 'completed');
      }
    }

    const { data, error } = await query;

    if (error) {
      console.error('Database error:', error);
      console.error('Error details:', JSON.stringify(error, null, 2));
      return NextResponse.json({ 
        error: 'Failed to fetch documents',
        details: error.message || String(error)
      }, { status: 500 });
    }

    // Handle null/undefined data
    if (!data) {
      console.warn('Query returned null/undefined data');
      return NextResponse.json({
        documents: [],
        pagination: {
          page,
          limit,
          total: 0,
          hasMore: false
        }
      });
    }

    // Transform data for frontend with all needed fields
    const transformedData = (data || []).map(doc => {
      const filename = doc.storage_path?.split('/').pop() || 'Unknown';
      const processingSummary = doc.processing_summary || {};
      const extractedData = doc.extracted_data || {};
      
      // Calculate file size from storage if available, or estimate
      let fileSize: number | undefined;
      if (processingSummary.file_size) {
        fileSize = processingSummary.file_size;
      } else if (extractedData.file_size) {
        fileSize = extractedData.file_size;
      }
      
      // Calculate processing time
      let processingTime: number | undefined;
      if (doc.processed_at && doc.created_at) {
        const start = new Date(doc.created_at).getTime();
        const end = new Date(doc.processed_at).getTime();
        if (!isNaN(start) && !isNaN(end) && end > start) {
          processingTime = Math.round((end - start) / 1000); // seconds
        }
      }
      
      return {
        id: doc.id,
        filename,
        status: doc.status || 'pending',
        document_type: doc.document_type || 'other',
        upload_date: doc.created_at,
        processed: doc.status === 'completed',
        file_size: fileSize,
        processing_time: processingTime,
        company_id: doc.company_id ?? null,
        fund_id: doc.fund_id ?? null
      };
    });

    const response = {
      documents: transformedData,
      pagination: {
        page,
        limit,
        total: transformedData.length,
        hasMore: transformedData.length === limit
      }
    };

    // Cache the response
    cache.set(cacheKey, {
      data: response,
      timestamp: Date.now()
    });

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=30, stale-while-revalidate=60',
        'X-Cache': 'MISS'
      }
    });

  } catch (error: unknown) {
    console.error('GET /api/documents error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  console.log('[documents] POST /api/documents received');
  try {
    // Check Supabase connection first
    if (!supabaseService) {
      console.error('Supabase service not initialized');
      const hasUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
      const hasKey = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
      return NextResponse.json({ 
        error: 'Database connection not available',
        details: {
          hasUrl,
          hasKey,
          message: 'Missing required environment variables: NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'
        }
      }, { status: 503 });
    }

    const formData = await request.formData();
    const file = formData.get('file') as File;
    const companyId = formData.get('company_id') as string | null;
    const fundId = formData.get('fund_id') as string | null;
    const formDocumentType = formData.get('document_type') as string | null;
    
    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    // Validate file size (100MB limit)
    if (file.size > 100 * 1024 * 1024) {
      return NextResponse.json({ error: 'File too large. Maximum size is 100MB.' }, { status: 400 });
    }

    // Generate unique filename
    const timestamp = Date.now();
    const filePath = `${timestamp}/${file.name}`;

    // Upload to Supabase storage
    const { data: uploadData, error: uploadError } = await supabaseService.storage
      .from('documents')
      .upload(filePath, file);

    if (uploadError) {
      console.error('Upload error:', uploadError);
      console.error('Upload error details:', JSON.stringify(uploadError, null, 2));
      return NextResponse.json({ 
        error: 'Failed to upload file to storage',
        details: uploadError.message || String(uploadError)
      }, { status: 500 });
    }

    // Document classification: use formData document_type if provided, otherwise infer from filename
    // Memos, updates, board decks, board transcripts use signal-first extraction (not pitch decks)
    const name = file.name.toLowerCase();
    const documentType = formDocumentType
      || (name.includes('memo') ? 'investment_memo'
        : name.includes('transcript') ? 'board_transcript'
        : name.includes('board') ? 'board_deck'
        : name.includes('update') ? 'monthly_update'
        : 'other');

    // Insert into database with pending status, file metadata, and company/fund linking
    const insertPayload: any = {
      storage_path: filePath,
      status: 'pending',
      document_type: documentType,
      processing_summary: {
        file_name: file.name,
        file_size: file.size,
        file_type: file.type,
        uploaded_at: new Date().toISOString()
      }
    };

    // Add company_id and fund_id if provided (for upload-in-cell)
    if (companyId) {
      insertPayload.company_id = companyId;
    }
    if (fundId) {
      insertPayload.fund_id = fundId;
    }

    const { data: insertData, error: insertError } = await supabaseService
      .from('processed_documents')
      .insert(insertPayload)
      .select()
      .single();

    if (insertError) {
      console.error('Database insert error:', insertError);
      console.error('Insert error details:', JSON.stringify(insertError, null, 2));
      
      // Try to clean up uploaded file if database insert failed
      try {
        await supabaseService.storage
          .from('documents')
          .remove([filePath]);
      } catch (cleanupError) {
        console.error('Failed to cleanup uploaded file:', cleanupError);
      }
      
      return NextResponse.json({ 
        error: 'Failed to save document metadata',
        details: insertError.message || String(insertError)
      }, { status: 500 });
    }

    // Clear cache
    cache.clear();

    // Trigger document processing: call backend directly so we don't rely on internal Next.js hop
    const backendUrl = getBackendUrl();
    try {
      const processPayload = {
        document_id: String(insertData.id),
        file_path: filePath,
        document_type: documentType,
        company_id: companyId ?? null,
        fund_id: fundId ?? null,
      };
      console.log('[documents] Calling backend directly', backendUrl, '/api/documents/process', 'documentId=', insertData.id);
      const processResponse = await fetch(`${backendUrl}/api/documents/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(processPayload),
      });

      if (processResponse.ok) {
        console.log('[documents] Backend processing completed for document', insertData.id);
      } else {
        const errText = await processResponse.text();
        console.error('[documents] Backend processing failed', processResponse.status, errText);
        await supabaseService
          .from('processed_documents')
          .update({ status: 'failed' })
          .eq('id', insertData.id);
      }
    } catch (processingError) {
      console.error('[documents] Backend call failed (is backend running at', backendUrl, '?):', processingError);
      await supabaseService
        .from('processed_documents')
        .update({ status: 'failed' })
        .eq('id', insertData.id);
    }

    return NextResponse.json({
      success: true,
      message: 'Document uploaded successfully and processing started',
      id: insertData.id,
      document: {
        id: insertData.id,
        filename: file.name,
        file_type: file.type,
        file_size: formatFileSize(file.size),
        document_type: documentType,
        status: 'pending'
      }
    });

  } catch (error: unknown) {
    console.error('Upload error:', error);
    return NextResponse.json({ error: 'Failed to upload document' }, { status: 500 });
  }
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
} 