'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  LineChart,
  FileText,
  TrendingUp,
  Layers,
  GitBranch,
  Brain,
  Table2,
  FileSearch,
  Building2,
  Rocket,
  BarChart3,
  Network,
  CheckCircle2,
  Shield,
  Upload,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const features = [
  {
    icon: <LineChart className="h-5 w-5" />,
    title: 'FP&A',
    description: 'P&L, cash flow, balance sheet, and forecasts built from your actuals. Change a driver, see it cascade through every line item.',
  },
  {
    icon: <FileText className="h-5 w-5" />,
    title: 'Contract Intelligence',
    description: 'Upload any contract. Dilla extracts every clause, quantifies the financial impact, and feeds the terms directly into your model.',
  },
  {
    icon: <TrendingUp className="h-5 w-5" />,
    title: 'Capital Strategy',
    description: 'Cap table, waterfall, debt structures, and valuation — derived from your actual legal documents, not manual data entry.',
  },
  {
    icon: <GitBranch className="h-5 w-5" />,
    title: 'Scenario Engine',
    description: 'Branch any assumption. Revenue drops, a contract expires, rates move — see the full cascade across financials, covenants, and equity.',
  },
  {
    icon: <Brain className="h-5 w-5" />,
    title: 'Agent',
    description: 'Ask questions in plain English. The agent reasons across your P&L, contracts, and capital structure to give you one connected answer.',
  },
  {
    icon: <Layers className="h-5 w-5" />,
    title: 'Multi-Entity',
    description: 'Group structures, intercompany flows, and transfer pricing. Roll up subsidiaries into a consolidated view with full attribution.',
  },
  {
    icon: <FileSearch className="h-5 w-5" />,
    title: 'Document Processing',
    description: '50+ document types — term sheets, loan agreements, vendor contracts, leases. Automatically classified, extracted, and cross-referenced.',
  },
  {
    icon: <Table2 className="h-5 w-5" />,
    title: 'Covenant Monitoring',
    description: 'Tracks every obligation and threshold from your debt facilities. Alerts you months before a breach, not after.',
  },
];

const segments = [
  {
    icon: <Rocket className="h-5 w-5" />,
    title: 'Startups',
    description: 'Model your raise, understand your cap table, forecast your runway — all connected to the actual documents.',
  },
  {
    icon: <Building2 className="h-5 w-5" />,
    title: 'SMEs',
    description: 'Your contracts, financials, and obligations in one place. See the full picture without hiring a finance team.',
  },
  {
    icon: <BarChart3 className="h-5 w-5" />,
    title: 'Mid-Market',
    description: 'Complex capital structures, multiple debt facilities, dozens of contracts. Dilla keeps it all connected and monitored.',
  },
  {
    icon: <Network className="h-5 w-5" />,
    title: 'PE Roll-Ups',
    description: 'Consolidate multiple entities, harmonise reporting, and model the group structure with full intercompany visibility.',
  },
];

const integrations = [
  { name: 'QuickBooks', logo: '/logos/quickbooks.png' },
  { name: 'Xero', logo: '/logos/xero.png' },
  { name: 'NetSuite', logo: '/logos/netsuite.png' },
  { name: 'SAP', logo: '/logos/sap.jpg' },
  { name: 'Salesforce', logo: '/logos/salesforce.png' },
  { name: 'Attio', logo: '/logos/attio.png' },
  { name: 'Workday', logo: '/logos/workday.png' },
  { name: 'BambooHR', logo: '/logos/bamboohr.png' },
];

const planBullets = [
  'Unlimited financial analysis',
  'P&L, balance sheet, cash flow intelligence',
  'Cap table & legal document parsing',
  'Scenario modeling & forecasting',
  'Investor deck generation',
  'ERP integrations (Xero, QuickBooks, NetSuite)',
];

// ---------------------------------------------------------------------------
// Animated product demo data
// ---------------------------------------------------------------------------

const agentMessages = [
  { role: 'user' as const, text: 'What happens if we lose the Nexus contract?' },
  { role: 'agent' as const, text: 'Analysing impact across financials, contracts, and capital structure...' },
];

const cascadeSteps = [
  { label: 'P&L', detail: 'Revenue drops £340K — EBITDA turns negative' },
  { label: 'Cash Flow', detail: 'Runway shrinks from 14 months to 7' },
  { label: 'Covenants', detail: 'DSCR breaches 1.20x threshold in month 4' },
  { label: 'Debt', detail: 'Floating charge over receivables crystallises' },
  { label: 'Equity', detail: 'Bridge round triggers anti-dilution ratchet' },
  { label: 'Ownership', detail: 'Founder stake dilutes from 34% to 27%' },
];

const chartBars = [
  { label: 'Q1', base: 82, scenario: 82 },
  { label: 'Q2', base: 91, scenario: 74 },
  { label: 'Q3', base: 97, scenario: 58 },
  { label: 'Q4', base: 105, scenario: 43 },
];

// ---------------------------------------------------------------------------
// Free email domain list
// ---------------------------------------------------------------------------

const freeEmailDomains = new Set([
  'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com',
  'icloud.com', 'me.com', 'msn.com', 'live.com', 'hey.com',
  'protonmail.com', 'pm.me', 'gmx.com', 'yandex.com', 'zoho.com',
]);

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  return (
    <div className="bg-white text-gray-900" data-theme="day">
      <div className="bg-gradient-to-b from-white via-white to-gray-50">
        <Nav />
        <Hero />
        <ProductDemo />
        <Features />
        <Integrations />
        <Segments />
        <Pricing />
        <CTA />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Nav
// ---------------------------------------------------------------------------

function Nav() {
  return (
    <header className="marketing-container flex items-center justify-between py-6">
      <Link href="/" className="flex items-center gap-3">
        <img src="/dilla-logo.svg" alt="Dilla AI" className="h-8 w-auto" />
        <span className="sr-only">Dilla</span>
      </Link>
      <div className="flex items-center gap-4">
        <Link
          href="#pricing"
          className="hidden sm:inline-flex text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          Pricing
        </Link>
        <Link
          href="/login"
          className="rounded-full border border-gray-200 px-5 py-2 text-sm font-medium text-gray-900 transition-colors hover:bg-gray-100"
        >
          Login
        </Link>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero() {
  return (
    <section className="marketing-section pt-20 lg:pt-28">
      <div className="marketing-container max-w-3xl text-center mx-auto space-y-8">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl"
        >
          An AI CFO for your business.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="max-w-2xl mx-auto text-lg leading-relaxed text-muted-foreground"
        >
          Dilla connects to your ERP, reads your contracts, and reasons across your
          entire financial stack. FP&A, contract lifecycle management, and capital strategy
          — connected, not siloed.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-wrap justify-center gap-4"
        >
          <ScrollButton target="get-started" label="Get Started" primary />
          <ScrollButton target="features" label="See Features" />
        </motion.div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Animated Product Demo
// ---------------------------------------------------------------------------

function ProductDemo() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    const timers = [
      setTimeout(() => setPhase(1), 400),   // user message
      setTimeout(() => setPhase(2), 1600),   // agent thinking
      setTimeout(() => setPhase(3), 2800),   // cascade starts
      setTimeout(() => setPhase(4), 3400),   // cascade step 2
      setTimeout(() => setPhase(5), 4000),   // cascade step 3
      setTimeout(() => setPhase(6), 4600),   // cascade step 4
      setTimeout(() => setPhase(7), 5200),   // cascade step 5
      setTimeout(() => setPhase(8), 5800),   // cascade step 6
      setTimeout(() => setPhase(9), 6600),   // chart appears
    ];
    return () => timers.forEach(clearTimeout);
  }, [isInView]);

  return (
    <section ref={ref} className="marketing-section">
      <div className="marketing-container space-y-6">
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">How it thinks</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            One question. Full cascade.
          </h2>
          <p className="mt-3 text-base text-muted-foreground">
            Ask a question and watch Dilla reason across your financials, contracts, and capital structure in real time.
          </p>
        </div>

        {/* Demo container — dark, looks like the product */}
        <div className="mx-auto max-w-4xl rounded-2xl border border-gray-800 bg-[#0f1117] p-6 shadow-2xl overflow-hidden">
          <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
            {/* Left: Agent chat + cascade */}
            <div className="space-y-4 min-h-[360px]">
              {/* Agent header */}
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <div className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>dilla agent</span>
              </div>

              <AnimatePresence>
                {/* User message */}
                {phase >= 1 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-lg bg-gray-800/60 px-4 py-3 text-sm text-gray-200"
                  >
                    {agentMessages[0].text}
                  </motion.div>
                )}

                {/* Agent response */}
                {phase >= 2 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-lg bg-gray-800/30 border border-gray-700/50 px-4 py-3 text-sm text-gray-400"
                  >
                    {agentMessages[1].text}
                  </motion.div>
                )}

                {/* Cascade steps */}
                {phase >= 3 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="space-y-2 pt-2"
                  >
                    {cascadeSteps.map((step, i) => {
                      const stepPhase = 3 + i;
                      if (phase < stepPhase) return null;
                      return (
                        <motion.div
                          key={step.label}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.3 }}
                          className="flex items-start gap-3"
                        >
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-emerald-500/20 text-[10px] font-medium text-emerald-400">
                            {i + 1}
                          </span>
                          <div className="text-xs">
                            <span className="font-medium text-gray-300">{step.label}</span>
                            <span className="text-gray-500"> — {step.detail}</span>
                          </div>
                        </motion.div>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Right: Animated chart */}
            <div className="flex flex-col justify-end">
              <AnimatePresence>
                {phase >= 9 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.4 }}
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>Cash Flow Forecast — Base vs. Scenario</span>
                      <div className="flex gap-3">
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-gray-500" />Base</span>
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" />Scenario</span>
                      </div>
                    </div>
                    <div className="flex items-end gap-3 h-40">
                      {chartBars.map((bar, i) => (
                        <div key={bar.label} className="flex-1 flex flex-col items-center gap-1">
                          <div className="flex items-end gap-1 w-full h-32">
                            <motion.div
                              initial={{ height: 0 }}
                              animate={{ height: `${bar.base}%` }}
                              transition={{ duration: 0.6, delay: i * 0.1 }}
                              className="flex-1 rounded-t bg-gray-600"
                            />
                            <motion.div
                              initial={{ height: 0 }}
                              animate={{ height: `${bar.scenario}%` }}
                              transition={{ duration: 0.6, delay: i * 0.1 + 0.05 }}
                              className="flex-1 rounded-t bg-red-500/80"
                            />
                          </div>
                          <span className="text-[10px] text-gray-600">{bar.label}</span>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Features
// ---------------------------------------------------------------------------

function Features() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section id="features" ref={ref} className="marketing-section">
      <div className="marketing-container space-y-12">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Features</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            What Dilla does.
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: i * 0.06 }}
              className="rounded-2xl border border-border/60 bg-white p-5 space-y-3 hover:shadow-md transition-shadow"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-primary">
                {f.icon}
              </div>
              <h3 className="text-sm font-semibold text-foreground">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Integrations
// ---------------------------------------------------------------------------

function Integrations() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="marketing-section">
      <div className="marketing-container space-y-10">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Integrations</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            Connect your stack. Or just upload a CSV.
          </h2>
          <p className="mt-3 text-base text-muted-foreground">
            Pull actuals directly from your ERP, CRM, or HRIS. No connector? Drop a CSV and Dilla maps it automatically.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {integrations.map(({ name, logo }, i) => (
            <motion.span
              key={name}
              initial={{ opacity: 0, y: 12 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.3, delay: i * 0.04 }}
              className="inline-flex items-center gap-2.5 rounded-full border border-border/60 bg-white px-5 py-2.5 text-sm font-medium text-foreground shadow-sm"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={logo}
                alt={name}
                className="h-5 w-auto max-w-[20px] object-contain"
                loading="lazy"
              />
              {name}
            </motion.span>
          ))}
          <motion.span
            initial={{ opacity: 0, y: 12 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.3, delay: integrations.length * 0.04 }}
            className="inline-flex items-center gap-2 rounded-full border border-dashed border-border bg-secondary/50 px-5 py-2.5 text-sm font-medium text-muted-foreground"
          >
            <Upload className="h-4 w-4" />
            Upload CSV
          </motion.span>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Segments
// ---------------------------------------------------------------------------

function Segments() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="marketing-section">
      <div className="marketing-container space-y-12">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Who it&apos;s for</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            Built for financial complexity.
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {segments.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              className="rounded-2xl border border-border/60 bg-white p-5 space-y-3 hover:shadow-md transition-shadow"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-primary">
                {s.icon}
              </div>
              <h3 className="text-sm font-semibold text-foreground">{s.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{s.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

function Pricing() {
  return (
    <section id="pricing" className="marketing-section">
      <div className="marketing-container space-y-12">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Pricing</p>
          <h2 className="mt-3 text-3xl font-semibold text-foreground sm:text-4xl">
            Simple pricing. Start immediately.
          </h2>
        </div>
        <div className="grid gap-8 lg:grid-cols-2 max-w-4xl">
          {/* Main plan */}
          <div className="flex flex-col rounded-2xl border-2 border-primary/80 bg-white p-8 shadow-xl">
            <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Pro</p>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-4xl font-bold text-foreground">&pound;100</span>
              <span className="text-muted-foreground">/month</span>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Full access to Dilla&apos;s CFO agent. Cancel anytime.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm text-muted-foreground">
              {planBullets.map(b => (
                <li key={b} className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary flex-shrink-0" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-8">
              <Link
                href="/pricing"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Subscribe
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {/* Enterprise */}
          <div className="flex flex-col rounded-2xl border border-border/60 bg-white p-8">
            <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Enterprise</p>
            <h3 className="mt-3 text-2xl font-semibold text-foreground">Custom</h3>
            <p className="mt-3 text-sm text-muted-foreground">
              Multi-entity consolidation, custom integrations, dedicated support, and SLA.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm text-muted-foreground">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary flex-shrink-0" />
                <span>Everything in Pro</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary flex-shrink-0" />
                <span>Group structure with transfer pricing</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary flex-shrink-0" />
                <span>Custom ERP integrations</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary flex-shrink-0" />
                <span>Dedicated implementation team</span>
              </li>
            </ul>
            <div className="mt-auto pt-8">
              <ScrollButton target="get-started" label="Get in Touch" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// CTA + Lead Form
// ---------------------------------------------------------------------------

function CTA() {
  return (
    <section id="get-started" className="marketing-section">
      <div className="marketing-container grid items-center gap-12 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <h2 className="text-3xl font-semibold text-foreground sm:text-4xl">
            See it with your own data.
          </h2>
          <p className="text-base text-muted-foreground">
            Tell us what you're working with. We'll walk you through Dilla with a setup
            tailored to your business — your structure, your contracts, your questions.
          </p>
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-2.5">
              <Shield className="h-4 w-4 text-primary" />
              <span>Your data stays yours. Always.</span>
            </div>
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-primary" />
              <span>No commitment. See if it fits.</span>
            </div>
          </div>
        </div>
        <LeadForm />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shared Components
// ---------------------------------------------------------------------------

function ScrollButton({ target, label, primary }: { target: string; label: string; primary?: boolean }) {
  const handleClick = () => {
    document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (primary) {
    return (
      <button
        onClick={handleClick}
        className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow-sm transition-transform hover:translate-y-[-2px] hover:bg-primary/90"
      >
        {label}
        <ArrowRight className="h-4 w-4" />
      </button>
    );
  }

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary/80"
    >
      {label}
      <ArrowRight className="h-4 w-4" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Lead Form
// ---------------------------------------------------------------------------

interface LeadFormState {
  name: string;
  email: string;
  companyType: string;
  notes: string;
}

function LeadForm() {
  const [form, setForm] = useState<LeadFormState>({
    name: '',
    email: '',
    companyType: 'sme',
    notes: '',
  });
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const handleChange = (field: keyof LeadFormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setForm(prev => ({ ...prev, [field]: e.target.value }));
    if (status === 'success' || status === 'error') {
      setStatus('idle');
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Name is required.');
      return;
    }

    const domain = form.email.split('@')[1]?.toLowerCase();
    if (!domain || freeEmailDomains.has(domain)) {
      setError('Please use your work email.');
      return;
    }

    setStatus('submitting');
    try {
      const res = await fetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          firmType: form.companyType,
          notes: form.notes,
        }),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.error ?? 'Something went wrong. Try again.');
      }

      setStatus('success');
      setForm({ name: '', email: '', companyType: form.companyType, notes: '' });
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Submission failed.');
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-border/60 bg-white p-7 shadow-sm space-y-5"
      aria-label="Get started form"
    >
      <div className="space-y-4">
        <FormField label="Name" id="lead-name">
          <input
            id="lead-name"
            value={form.name}
            onChange={handleChange('name')}
            placeholder="Jane Smith"
            className="form-input"
            required
          />
        </FormField>

        <FormField label="Work Email" id="lead-email">
          <input
            id="lead-email"
            type="email"
            value={form.email}
            onChange={handleChange('email')}
            placeholder="jane@company.com"
            className="form-input"
            required
          />
        </FormField>

        <FormField label="Company Type" id="lead-type">
          <select
            id="lead-type"
            value={form.companyType}
            onChange={handleChange('companyType')}
            className="form-input"
          >
            <option value="startup">Startup</option>
            <option value="sme">SME</option>
            <option value="midmarket">Mid-Market</option>
            <option value="pe">PE / Multi-Entity</option>
          </select>
        </FormField>

        <FormField label="What are you trying to solve?" id="lead-notes">
          <textarea
            id="lead-notes"
            value={form.notes}
            onChange={handleChange('notes')}
            placeholder="E.g. forecasting, contract management, cap table, scenario modeling..."
            rows={3}
            className="form-input"
          />
        </FormField>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {status === 'success' && (
        <p className="rounded-xl border border-primary/30 bg-secondary px-4 py-3 text-sm text-foreground">
          Thanks — we&apos;ll be in touch within one business day.
        </p>
      )}

      <button
        type="submit"
        disabled={status === 'submitting'}
        className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors disabled:opacity-70 hover:bg-primary/90"
      >
        {status === 'submitting' ? 'Sending...' : 'Book a Walkthrough'}
      </button>
    </form>
  );
}

function FormField({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-foreground">{label}</label>
      {children}
    </div>
  );
}
