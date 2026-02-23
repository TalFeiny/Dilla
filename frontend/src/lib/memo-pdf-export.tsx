/**
 * Memo PDF Export — uses jsPDF + html2canvas (already in package.json).
 * Works on Vercel (pure JS, no Playwright/Puppeteer).
 */

import type { DocumentSection } from '@/components/memo/MemoEditor';

export async function exportMemoPdf(
  sections: DocumentSection[],
  title?: string,
  /** Pass the memo editor container element to enable chart capture */
  containerEl?: HTMLElement | null,
): Promise<void> {
  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import('jspdf'),
    import('html2canvas'),
  ]);

  const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 50;
  const contentW = pageW - margin * 2;
  let y = margin;

  const addPage = () => {
    doc.addPage();
    y = margin;
  };

  const ensureSpace = (needed: number) => {
    if (y + needed > pageH - margin) addPage();
  };

  // Title
  if (title) {
    doc.setFontSize(20);
    doc.setFont('helvetica', 'bold');
    doc.text(title, margin, y);
    y += 30;
  }

  // Date
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(120, 120, 120);
  doc.text(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), margin, y);
  y += 20;
  doc.setTextColor(0, 0, 0);

  for (const section of sections) {
    switch (section.type) {
      case 'heading1':
        ensureSpace(35);
        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.text(stripHtml(section.content || ''), margin, y, { maxWidth: contentW });
        y += 28;
        break;

      case 'heading2':
        ensureSpace(30);
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        // Underline
        doc.setDrawColor(200, 200, 200);
        doc.line(margin, y + 4, pageW - margin, y + 4);
        doc.text(stripHtml(section.content || ''), margin, y);
        y += 24;
        break;

      case 'heading3':
        ensureSpace(25);
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.text(stripHtml(section.content || ''), margin, y, { maxWidth: contentW });
        y += 20;
        break;

      case 'paragraph': {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        const text = stripHtml(section.content || '');
        if (!text) break;
        const lines = doc.splitTextToSize(text, contentW);
        for (const line of lines) {
          ensureSpace(14);
          doc.text(line, margin, y);
          y += 14;
        }
        y += 6;
        break;
      }

      case 'list':
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        for (const item of section.items || []) {
          const text = stripHtml(item);
          if (!text) continue;
          ensureSpace(14);
          doc.text(`•  ${text}`, margin + 10, y, { maxWidth: contentW - 20 });
          const itemLines = doc.splitTextToSize(`•  ${text}`, contentW - 20);
          y += itemLines.length * 14;
        }
        y += 6;
        break;

      case 'table':
        if (section.table) {
          const { headers, rows, caption } = section.table;
          if (caption) {
            ensureSpace(16);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'italic');
            doc.setTextColor(100, 100, 100);
            doc.text(caption, margin, y);
            y += 14;
            doc.setTextColor(0, 0, 0);
          }

          const colW = contentW / headers.length;
          const rowH = 18;

          // Header
          ensureSpace(rowH + 4);
          doc.setFillColor(240, 240, 240);
          doc.rect(margin, y - 12, contentW, rowH, 'F');
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          headers.forEach((h, i) => {
            doc.text(h, margin + i * colW + 4, y);
          });
          y += rowH;

          // Rows
          doc.setFont('helvetica', 'normal');
          for (const row of rows) {
            ensureSpace(rowH);
            row.forEach((cell, i) => {
              doc.text(String(cell ?? ''), margin + i * colW + 4, y, { maxWidth: colW - 8 });
            });
            y += rowH;
          }
          y += 8;
        }
        break;

      case 'chart': {
        // Capture rendered chart from DOM via html2canvas
        const chartTitle = section.chart?.title;
        const sectionIndex = sections.indexOf(section);
        const chartEl = containerEl?.querySelectorAll('.chart-container')?.[
          // Map section index to chart-container index (only chart sections have .chart-container)
          sections.slice(0, sectionIndex).filter(s => s.type === 'chart' && s.chart).length
        ] as HTMLElement | undefined;

        if (chartEl) {
          try {
            const canvas = await html2canvas(chartEl, {
              scale: 2,
              backgroundColor: '#ffffff',
              logging: false,
              useCORS: true,
            });
            const imgData = canvas.toDataURL('image/png');
            const imgAspect = canvas.width / canvas.height;
            const imgW = contentW;
            const imgH = imgW / imgAspect;
            ensureSpace(imgH + 24);
            if (chartTitle) {
              doc.setFontSize(9);
              doc.setFont('helvetica', 'bold');
              doc.setTextColor(60, 60, 60);
              doc.text(chartTitle, margin, y);
              y += 14;
              doc.setTextColor(0, 0, 0);
            }
            doc.addImage(imgData, 'PNG', margin, y, imgW, imgH);
            y += imgH + 10;
          } catch {
            // Fallback to text placeholder on capture failure
            if (chartTitle) {
              ensureSpace(30);
              doc.setFontSize(9);
              doc.setFont('helvetica', 'italic');
              doc.setTextColor(100, 100, 100);
              doc.text(`[Chart: ${chartTitle}]`, margin, y);
              y += 16;
              doc.setTextColor(0, 0, 0);
            }
          }
        } else if (chartTitle) {
          ensureSpace(30);
          doc.setFontSize(9);
          doc.setFont('helvetica', 'italic');
          doc.setTextColor(100, 100, 100);
          doc.text(`[Chart: ${chartTitle}]`, margin, y);
          y += 16;
          doc.setTextColor(0, 0, 0);
        }
        break;
      }

      case 'quote':
        ensureSpace(20);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(80, 80, 80);
        doc.setDrawColor(78, 121, 167);
        doc.setLineWidth(2);
        doc.line(margin, y - 10, margin, y + 10);
        const quoteText = stripHtml(section.content || '');
        const quoteLines = doc.splitTextToSize(quoteText, contentW - 20);
        for (const line of quoteLines) {
          ensureSpace(14);
          doc.text(line, margin + 12, y);
          y += 14;
        }
        doc.setTextColor(0, 0, 0);
        y += 6;
        break;

      default:
        break;
    }
  }

  // Footer on each page
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(150, 150, 150);
    doc.text(`Page ${i} of ${totalPages}`, pageW - margin, pageH - 20, { align: 'right' });
    doc.text('Generated by Dilla AI', margin, pageH - 20);
  }

  // Download
  const filename = title
    ? `${title.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50)}.pdf`
    : 'memo.pdf';
  doc.save(filename);
}

function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .trim();
}
