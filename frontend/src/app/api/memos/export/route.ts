import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { sections, title, fundId } = body;

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
    const response = await fetch(`${getBackendUrl()}/api/export/deck`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        slides,
        theme: 'memo',
        title: title || 'Portfolio Memo',
        metadata: { fundId, exportType: 'memo' },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[MEMO_EXPORT] Backend export failed:', errorText);
      return NextResponse.json({ error: 'PDF export failed' }, { status: 500 });
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
