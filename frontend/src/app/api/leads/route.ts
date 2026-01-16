import { NextResponse } from 'next/server';

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

function isWorkEmail(email: string): boolean {
  const domain = email.split('@')[1]?.toLowerCase();
  if (!domain) return false;
  return !freeEmailDomains.has(domain);
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

    const webhook = process.env.LEAD_ALERT_WEBHOOK;
    const beehiivEndpoint = process.env.BEEHIIV_WEBHOOK_URL;

    const payload = {
      name,
      email,
      firmType,
      notes: notes ?? '',
      submittedAt: new Date().toISOString(),
      source: 'marketing-site'
    };

    let delivered = false;
    const failures: string[] = [];

    if (webhook) {
      try {
        const webhookResponse = await fetch(webhook, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (!webhookResponse.ok) {
          failures.push(`Webhook responded with ${webhookResponse.status}`);
        } else {
          delivered = true;
        }
      } catch (error) {
        failures.push(`Webhook delivery failed: ${(error as Error).message}`);
      }
    }

    if (beehiivEndpoint) {
      try {
        const beehiivResponse = await fetch(beehiivEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (!beehiivResponse.ok) {
          failures.push(`Beehiiv webhook responded with ${beehiivResponse.status}`);
        } else {
          delivered = true;
        }
      } catch (error) {
        failures.push(`Beehiiv webhook delivery failed: ${(error as Error).message}`);
      }
    }

    if (!webhook && !beehiivEndpoint) {
      console.warn('Lead captured but no webhook configured.', payload);
    }

    if (failures.length > 0 && delivered) {
      console.warn('Lead captured with partial delivery failures', { failures });
    }

    if (!delivered && failures.length > 0) {
      return NextResponse.json(
        { error: 'Lead captured but delivery failed. Check server logs.' },
        { status: 502 }
      );
    }

    return NextResponse.json({
      success: true,
      delivered,
      requiresConfiguration: !webhook && !beehiivEndpoint
    });
  } catch (error) {
    console.error('Lead submission error', error);
    return NextResponse.json({ error: 'Unexpected error.' }, { status: 500 });
  }
}

