import { NextResponse } from 'next/server';
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

const NOTIFY_EMAIL = process.env.LEAD_NOTIFY_EMAIL ?? 'talfeingold6@gmail.com';
const FROM_ADDRESS = process.env.LEAD_FROM_ADDRESS ?? 'Dilla Leads <onboarding@resend.dev>';

const freeEmailDomains = new Set([
  'gmail.com',
  'yahoo.com',
  'outlook.com',
  'hotmail.com',
  'aol.com',
  'icloud.com',
  'me.com',
  'msn.com',
  'live.com',
  'hey.com',
  'protonmail.com',
  'pm.me',
  'gmx.com',
  'yandex.com',
  'zoho.com'
]);

interface LeadPayload {
  name: string;
  email: string;
  firmType: string;
  notes?: string;
}

const firmLabels: Record<string, string> = {
  solo: 'Solo VC / Angel',
  mid: 'Mid-Sized Shop',
  mega: 'Megafund / Financial Institution'
};

function isWorkEmail(email: string): boolean {
  const domain = email.split('@')[1]?.toLowerCase();
  if (!domain) return false;
  return !freeEmailDomains.has(domain);
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export async function POST(request: Request) {
  try {
    const { name, email, firmType, notes }: LeadPayload = await request.json();

    if (!name || !email || !firmType) {
      return NextResponse.json({ error: 'Missing required fields.' }, { status: 400 });
    }

    if (!isWorkEmail(email)) {
      return NextResponse.json({ error: 'Personal email domains are not supported.' }, { status: 400 });
    }

    const submittedAt = new Date().toISOString();
    const firmLabel = firmLabels[firmType] ?? firmType;

    const safeName = escapeHtml(name);
    const safeEmail = escapeHtml(email);
    const safeNotes = escapeHtml(notes || '—');
    const safeFirmLabel = escapeHtml(firmLabel);

    // Send notification email via Resend
    const { error: resendError } = await resend.emails.send({
      from: FROM_ADDRESS,
      to: NOTIFY_EMAIL,
      subject: `New lead: ${safeName} (${safeFirmLabel})`,
      html: `
        <h2>New Lead from dilla-ai.com</h2>
        <table style="border-collapse:collapse;font-family:sans-serif;font-size:14px;">
          <tr><td style="padding:6px 12px;font-weight:bold;">Name</td><td style="padding:6px 12px;">${safeName}</td></tr>
          <tr><td style="padding:6px 12px;font-weight:bold;">Email</td><td style="padding:6px 12px;"><a href="mailto:${safeEmail}">${safeEmail}</a></td></tr>
          <tr><td style="padding:6px 12px;font-weight:bold;">Firm Profile</td><td style="padding:6px 12px;">${safeFirmLabel}</td></tr>
          <tr><td style="padding:6px 12px;font-weight:bold;">Notes</td><td style="padding:6px 12px;">${safeNotes}</td></tr>
          <tr><td style="padding:6px 12px;font-weight:bold;">Submitted</td><td style="padding:6px 12px;">${submittedAt}</td></tr>
        </table>
      `
    });

    if (resendError) {
      console.error('Resend email failed:', resendError);
      return NextResponse.json(
        { error: 'Something went wrong on our end. Please try again or email us directly.' },
        { status: 502 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Lead submission error', error);
    return NextResponse.json({ error: 'Unexpected error.' }, { status: 500 });
  }
}

