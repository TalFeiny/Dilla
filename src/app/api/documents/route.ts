import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

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
 *           enum: [all, pitch_deck, financial_statement, due_diligence, term_sheet, other]
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
 *                 enum: [pitch_deck, financial_statement, due_diligence, term_sheet, other]
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
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '10');
    const status = searchParams.get('status');
    const processed = searchParams.get('processed');
    
    const offset = (page - 1) * limit;

    // Check cache first
    const cacheKey = `documents_${page}_${limit}_${status}_${processed}`;
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return NextResponse.json(cached.data, {
        headers: {
          'Cache-Control': 'public, max-age=30, stale-while-revalidate=60',
          'X-Cache': 'HIT'
        }
      });
    }

    // Optimized query - only select essential columns
    let query = supabaseService
      .from('processed_documents')
      .select('id, storage_path, status, document_type, created_at')
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (status) {
      query = query.eq('status', status);
    }

    if (processed !== null) {
      query = query.eq('status', processed === 'true' ? 'completed' : 'pending');
    }

    const { data, error } = await query;

    if (error) {
      console.error('Database error:', error);
      return NextResponse.json({ error: 'Failed to fetch documents' }, { status: 500 });
    }

    // Transform data for frontend - minimal version
    const transformedData = data?.map(doc => ({
      id: doc.id,
      filename: doc.storage_path?.split('/').pop() || 'Unknown',
      status: doc.status,
      document_type: doc.document_type,
      upload_date: doc.created_at,
      processed: doc.status === 'completed'
    })) || [];

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
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    
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
      return NextResponse.json({ error: 'Failed to upload file' }, { status: 500 });
    }

    // Simple document classification
    const documentType = file.name.toLowerCase().includes('pitch') ? 'pitch_deck' : 'other';

    // Insert into database with pending status
    const { data: insertData, error: insertError } = await supabaseService
      .from('processed_documents')
      .insert({
        storage_path: filePath,
        status: 'pending',
        document_type: documentType
      })
      .select()
      .single();

    if (insertError) {
      console.error('Database insert error:', insertError);
      return NextResponse.json({ error: 'Failed to save document metadata' }, { status: 500 });
    }

    // Clear cache
    cache.clear();

    // Trigger document processing using local Python script
    try {
      // The Python script will handle downloading and processing the file from Supabase storage
      
      // Call the local document processing API route
      const processResponse = await fetch(`${request.nextUrl.origin}/api/documents/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          documentId: insertData.id,
          filePath: filePath,
          documentType: documentType
        }),
      });

      if (processResponse.ok) {
        const processingResult = await processResponse.json();
        console.log(`Document processing completed for document ${insertData.id}`);
      } else {
        console.error(`Document processing failed with status ${processResponse.status}`);
        // Update status to failed
        await supabaseService
          .from('processed_documents')
          .update({ status: 'failed' })
          .eq('id', insertData.id);
      }
      
    } catch (processingError) {
      console.error('Failed to process document:', processingError);
      // Update status to failed
      await supabaseService
        .from('processed_documents')
        .update({ status: 'failed' })
        .eq('id', insertData.id);
    }

    return NextResponse.json({
      success: true,
      message: 'Document uploaded successfully and processing started',
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