'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Shield,
  LineChart,
  Users,
  Sparkles,
  CheckCircle2,
  Target,
  BarChart3
} from 'lucide-react';

const proofPoints = [
  {
    label: 'Deal Boards',
    value: '18+',
    description: 'Funds standardize their IC materials on Dilla.'
  },
  {
    label: 'Faster Decisions',
    value: '4x',
    description: 'Reduction in time spent from intake to IC review.'
  },
  {
    label: 'Sources Consolidated',
    value: '40+',
    description: 'Data providers, models, and war rooms unified.'
  }
];

const capabilityHighlights = [
  {
    title: 'Institutional Intelligence',
    description: 'On-demand models, deal pacing, and custom diligence narratives driven by your playbook.',
    icon: <LineChart className="w-6 h-6 text-primary" />
  },
  {
    title: 'Operational OS',
    description: 'Full-firm operating system across fund admin, LP reporting, portfolio monitoring, and audit.',
    icon: <Shield className="w-6 h-6 text-primary" />
  },
  {
    title: 'Collaboration Layer',
    description: 'Single workspace for investment committee, finance, and platform teams to make decisions faster.',
    icon: <Users className="w-6 h-6 text-primary" />
  }
];

const packages = [
  {
    id: 'solo',
    label: 'Solo VC / Angel',
    price: 'From $1,250 / month',
    summary: 'Everything you need to run institutional-grade diligence with zero back office.',
    bullets: [
      'Unlimited memo generation and IC-ready packets',
      'Automated market maps, pacing models, and cap table insights',
      'Hands-on onboarding with a forward deployed engineer'
    ]
  },
  {
    id: 'mid',
    label: 'Mid-Sized Shop',
    price: 'From $3,800 / month',
    summary: 'Purpose-built workflows for dedicated deal, finance, and platform teams.',
    bullets: [
      'Firm-wide workspace with role-based governance',
      'Fund admin automation and LP reporting templates',
      'Dedicated forward deployed engineer embedded with your team'
    ],
    badge: 'Most Popular'
  },
  {
    id: 'mega',
    label: 'Megafund / Financial Institution',
    price: 'Custom Annual Engagements',
    summary: 'Deep integration into legacy systems, data governance, and controls.',
    bullets: [
      'Signed SLAs, on-premise options, and advanced security',
      'Custom modeling across funds, credit, and secondaries',
      'Dedicated pod of forward deployed engineers + solutions lead'
    ]
  }
];

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

interface LeadFormState {
  name: string;
  email: string;
  firmType: string;
  notes: string;
}

export default function LandingPage() {
  return (
    <div className="bg-white text-gray-900" data-theme="day">
      <div className="bg-gradient-to-b from-white via-white to-gray-50">
        <header className="marketing-container flex items-center justify-between py-6">
          <Link href="/" className="flex items-center gap-3">
            <img
              src="/dilla-logo.svg"
              alt="Dilla AI"
              className="h-8 w-auto"
            />
            <span className="sr-only">Dilla</span>
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-gray-200 px-5 py-2 text-sm font-medium text-gray-900 transition-colors hover:bg-gray-100"
          >
            Login
          </Link>
        </header>
        <HeroSection />
        <ProofPoints />
        <Capabilities />
        <ForwardDeployedSection />
        <PricingSection />
        <FinalCTA />
      </div>
    </div>
  );
}

function HeroSection() {
  return (
    <section className="marketing-section pt-24 lg:pt-32">
      <div className="marketing-container grid gap-12 lg:grid-cols-[1.2fr_1fr] items-center">
        <div className="space-y-8">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-white/70 px-4 py-1 text-sm text-muted-foreground shadow-sm backdrop-blur">
            <Sparkles className="h-4 w-4 text-primary" />
            Institutional-grade venture automation
          </span>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
            The operating system for conviction-driven venture investors.
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
            Dilla unifies your deal flow, diligence engine, fund operations, and LP communications into a
            single monochrome workspace that firms can trust. No free runs, just the infrastructure you need
            to compound edge.
          </p>
          <div className="flex flex-wrap gap-4">
            <ActionButton />
            <Link
              href="#pricing"
              className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary/80"
            >
              View Pricing Overview
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
        <div className="relative">
          <div className="marketing-card p-8">
            <div className="space-y-6">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Modern IC Packet</p>
                <h3 className="mt-2 text-2xl font-medium text-foreground">
                  Every question answered before committee convenes.
                </h3>
              </div>
              <ul className="space-y-3 text-sm text-muted-foreground">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                  <span>Live company dossiers with financial, product, and talent signals.</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                  <span>Scenario modeling and pacing controls aligned to mandate.</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                  <span>Audit-ready archive covering LP updates, compliance, and risk.</span>
                </li>
              </ul>
              <div className="rounded-2xl border border-border/60 bg-secondary/50 px-6 py-5 text-sm text-muted-foreground">
                “We eliminated five tools and hit IC with the exact story we wanted. The forward deployed team
                rewired our entire diligence flow in weeks.”
              </div>
            </div>
          </div>
          <div className="absolute -bottom-10 -right-10 hidden w-32 rounded-3xl border border-border/70 bg-white/80 p-4 text-xs tracking-wide text-muted-foreground shadow-lg lg:block">
            Backed by teams investing from New York, London, Dubai, and Singapore.
          </div>
        </div>
      </div>
    </section>
  );
}

function ProofPoints() {
  return (
    <section className="marketing-section pt-0">
      <div className="marketing-container">
        <div className="grid gap-6 rounded-3xl border border-border/70 bg-white/80 p-8 backdrop-blur-lg sm:grid-cols-3">
          {proofPoints.map(point => (
            <div key={point.label} className="space-y-2">
              <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">{point.label}</p>
              <p className="text-3xl font-semibold text-foreground">{point.value}</p>
              <p className="text-sm text-muted-foreground">{point.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Capabilities() {
  return (
    <section className="marketing-section">
      <div className="marketing-container space-y-12">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Capabilities</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            A monochrome workspace built for consistent investment judgment.
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            Dilla orchestrates models, narrative intelligence, compliance, and fund operations with controls that
            satisfy your mandate and downstream partners.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {capabilityHighlights.map(capability => (
            <div key={capability.title} className="marketing-card p-6">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-secondary">
                {capability.icon}
              </div>
              <h3 className="mt-6 text-xl font-medium text-foreground">{capability.title}</h3>
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                {capability.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ForwardDeployedSection() {
  return (
    <section className="marketing-section">
      <div className="marketing-container grid items-center gap-12 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Forward Deployed Engineers</p>
          <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
            A team embedded directly into your firm.
          </h2>
          <p className="text-base text-muted-foreground">
            We pair every engagement with forward deployed engineers who live inside your investment and
            operations rhythms. They own instrumentation, workflow rewiring, and the integrations that make
            the platform feel native.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
            <ListItem icon={<Target className="h-4 w-4 text-primary" />} text="Implementation roadmap aligned to fundraising, deployment, and reporting cycles." />
            <ListItem icon={<BarChart3 className="h-4 w-4 text-primary" />} text="Custom data pipelines, model calibration, and bespoke dashboards per fund." />
            <ListItem icon={<Shield className="h-4 w-4 text-primary" />} text="Security review, audits, and runbooks that satisfy LP, regulatory, and internal controls." />
          </ul>
        </div>
        <div className="marketing-card p-8 space-y-6">
          <div className="rounded-3xl border border-border/60 bg-white/70 p-6">
            <h3 className="text-lg font-medium text-foreground">Embedded Partnership</h3>
            <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
              Weekly working sessions, shared OKRs, and direct lines into product engineering ensure your edge
              compounds. Our team ships in your Slack, Notion, and data warehouse.
            </p>
          </div>
          <div className="rounded-3xl border border-border/60 bg-secondary/60 p-6">
            <h4 className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">What we ship</h4>
            <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
              <li className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <span>Analyst-grade ingestion of decks, datasites, and management reports.</span>
              </li>
              <li className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <span>Firm-wide single source of truth for deal, finance, and platform data.</span>
              </li>
              <li className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <span>Custom automations for LP questionnaires, compliance, and audit trails.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

function PricingSection() {
  return (
    <section id="pricing" className="marketing-section pt-0">
      <div className="marketing-container space-y-12">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Pricing Overview</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            Three packages tuned to how your firm operates today.
          </h2>
          <p className="mt-4 text-base text-muted-foreground">
            Every tier includes onboarding with a forward deployed engineer, secured workspace, and direct access to
            the Dilla product roadmap. No card collection—talk to sales to activate.
          </p>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {packages.map(pkg => (
            <div
              key={pkg.id}
              className={[
                'marketing-card flex flex-col p-8',
                pkg.badge ? 'border-2 border-primary/80 shadow-xl' : ''
              ].join(' ')}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">{pkg.label}</p>
                  <h3 className="mt-4 text-2xl font-semibold text-foreground">{pkg.price}</h3>
                </div>
                {pkg.badge && (
                  <span className="rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
                    {pkg.badge}
                  </span>
                )}
              </div>
              <p className="mt-4 text-sm text-muted-foreground leading-relaxed">{pkg.summary}</p>
              <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
                {pkg.bullets.map(item => (
                  <li key={item} className="flex items-start gap-3">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-auto pt-6">
                <a
                  href="#talk-to-sales"
                  className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Talk to Sales
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCTA() {
  return (
    <section id="talk-to-sales" className="marketing-section pt-0">
      <div className="marketing-container grid items-center gap-12 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-6">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Talk To Sales</p>
          <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
            Share your name and work email, we’ll route the right forward deployed engineer.
          </h2>
          <p className="text-base text-muted-foreground">
            Tell us which package fits your current stage. We’ll follow up within one business day with a tailored
            walkthrough, sample outputs, and an integration checklist. Work emails only—we partner directly with funds.
          </p>
          <div className="flex flex-wrap gap-6 text-sm text-muted-foreground">
            <ListItem icon={<Users className="h-4 w-4 text-primary" />} text="Built with security reviews cleared by global LPs." />
            <ListItem icon={<Sparkles className="h-4 w-4 text-primary" />} text="Monochrome interface across every module." />
          </div>
        </div>
        <LeadCaptureForm />
      </div>
    </section>
  );
}

function ActionButton() {
  const handleClick = () => {
    const target = document.getElementById('talk-to-sales');
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow-sm transition-transform hover:translate-y-[-2px] hover:bg-primary/90"
    >
      Talk to Sales
      <ArrowRight className="h-4 w-4" />
    </button>
  );
}

function LeadCaptureForm() {
  const [form, setForm] = useState<LeadFormState>({
    name: '',
    email: '',
    firmType: 'solo',
    notes: ''
  });
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const handleChange = (field: keyof LeadFormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [field]: e.target.value }));
  };

  const validateWorkEmail = (email: string) => {
    const domain = email.split('@')[1]?.toLowerCase();
    if (!domain) return false;
    return !freeEmailDomains.has(domain);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Please share your name.');
      return;
    }

    if (!form.email.trim() || !validateWorkEmail(form.email)) {
      setError('Use your work email so we can route you correctly.');
      return;
    }

    setStatus('submitting');
    try {
      const response = await fetch('/api/leads', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(form)
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const message = payload?.error ?? 'Unable to submit right now. Please try again.';
        throw new Error(message);
      }

      setStatus('success');
      setForm({
        name: '',
        email: '',
        firmType: form.firmType,
        notes: ''
      });
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Submission failed.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="marketing-card space-y-6 p-8" aria-label="Talk to sales lead form">
      <div>
        <h3 className="text-xl font-semibold text-foreground">Route me to the right pod</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          We’ll send a calendar link and sample outputs straight to your inbox.
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="lead-name" className="text-sm font-medium text-foreground">
            Name
          </label>
          <input
            id="lead-name"
            name="name"
            value={form.name}
            onChange={handleChange('name')}
            placeholder="Alex, Partner @ Example Ventures"
            className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
            required
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="lead-email" className="text-sm font-medium text-foreground">
            Work Email
          </label>
          <input
            id="lead-email"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange('email')}
            placeholder="alex@firm.com"
            className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
            required
          />
          <p className="text-xs text-muted-foreground">
            Personal email domains are automatically filtered out.
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="lead-firm-type" className="text-sm font-medium text-foreground">
            Firm Profile
          </label>
          <select
            id="lead-firm-type"
            name="firmType"
            value={form.firmType}
            onChange={handleChange('firmType')}
            className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
          >
            <option value="solo">Solo VC / Angel</option>
            <option value="mid">Mid-Sized Shop</option>
            <option value="mega">Megafund / Financial Institution</option>
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="lead-notes" className="text-sm font-medium text-foreground">
            What do you want to see?
          </label>
          <textarea
            id="lead-notes"
            name="notes"
            value={form.notes}
            onChange={handleChange('notes')}
            placeholder="Share focus areas, portfolio workflow gaps, or must-have integrations."
            rows={4}
            className="w-full rounded-2xl border border-border bg-white/80 px-4 py-3 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {status === 'success' && (
        <p className="rounded-2xl border border-primary/40 bg-secondary px-4 py-3 text-sm text-foreground">
          Thanks—we’ll be in touch within one business day.
        </p>
      )}

      <button
        type="submit"
        disabled={status === 'submitting'}
        className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-70 hover:bg-primary/90"
      >
        {status === 'submitting' ? 'Sending…' : 'Submit'}
      </button>
      <p className="text-xs text-muted-foreground">
        We’ll keep you off any marketing drips until you opt-in via Beehiiv.
      </p>
    </form>
  );
}

function ListItem({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-7 w-7 items-center justify-center rounded-xl bg-secondary">
        {icon}
      </div>
      <span>{text}</span>
    </div>
  );
}
