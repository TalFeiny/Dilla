import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { sections, charts, title, companies, fundId } = body;

  if (!sections?.length) {
    return NextResponse.json({ error: 'No sections to export' }, { status: 400 });
  }

  // Convert memo sections to slides format for existing deck export
  const slides = sections.map((s: Record<string, unknown>, i: number) => ({
    id: `memo-${i}`,
    title: typeof s.type === 'string' && s.type.startsWith('heading') ? s.content : undefined,
    content: s,
    order: i,
  }));

  try {
    // Backend expects { deck_data: { ... }, format: "pdf" } per DeckExportRequest schema
    const response = await fetch(`${getBackendUrl()}/api/export/deck`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deck_data: {
          slides,
          charts: charts || [],
          title: title || 'Portfolio Memo',
          companies: companies || [],
          theme: 'memo',
          metadata: { fundId, exportType: 'memo' },
        },
        format: 'pdf',
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[MEMO_EXPORT] Backend export failed:', errorText);
      return NextResponse.json({ error: 'PDF export failed', details: errorText }, { status: 500 });
    }

    const pdfBuffer = await response.arrayBuffer();
    return new NextResponse(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="${(title || 'memo').replace(/[^a-zA-Z0-9]/g, '_')}.pdf"`,
      },
    });
  } catch (err) {
    console.error('[MEMO_EXPORT] Export error:', err);
    return NextResponse.json({ error: 'PDF export failed' }, { status: 500 });
  }
}
