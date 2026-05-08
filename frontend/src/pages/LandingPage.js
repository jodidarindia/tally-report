import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  BarChart3, Shield, Package, Users, Brain, Truck, Zap,
  ArrowRight, Check, ChevronRight, Lock, Database, Eye,
  Star, Clock, Globe, Phone, Mail, Lightbulb, MessageCircle, Landmark,
  FileText, ClipboardList, Download, ChevronDown, ShoppingCart,
  Menu, X, ChevronDown as _ChevDown, Sparkles, Rocket, Warehouse
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    monthly: 999,
    annual: 9990,
    desc: 'Perfect for small businesses getting started',
    features: ['Dashboard & Overview', 'Sales Voucher Tracking', 'Inventory Management', 'Tally* / Busy* Sync', 'Setup & Configuration', 'Daily MongoDB Backups'],
    maxCompanies: 1,
    maxEmployees: 2,
    popular: false
  },
  {
    id: 'professional',
    name: 'Professional',
    monthly: 2499,
    annual: 24990,
    desc: 'For growing businesses needing deeper insights',
    features: ['Everything in Starter', 'Customer CRM & Outstanding', 'Inventory Movement Analytics', 'A/B/C/D Pareto Categorisation', 'Multi-Company Support (3)', 'Excel & PDF Exports', 'DPDP Data Export (.zip)'],
    maxCompanies: 3,
    maxEmployees: 5,
    popular: true
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    monthly: 3799,
    annual: 37990,
    desc: 'Full suite with AI and unlimited features',
    features: ['Everything in Professional', 'Dispatch Terminal (Kanban, LR, Docs)', 'Salesman Order System (Mobile)', 'Beat Plans + Beat Run Today', 'Salesman Performance Dashboard', 'AI-Powered Reports (GPT-5.2)', 'Insider Result BI Analytics', 'CA Corner — 100% Tally/Busy Parity', 'Multi-Company Support (10)', 'Priority Support & Training'],
    maxCompanies: 10,
    maxEmployees: 20,
    popular: false
  }
];

const FEATURES = [
  { icon: BarChart3, title: 'Inventory Analytics', desc: 'A/B/C/D Pareto categorisation, movement analysis, below-cost detection. Auto-ABC button distributes 80-15-4-1 across FY revenue. New Category Sales tab drills into top customers per tier.', isNew: true },
  { icon: Users, title: 'Customer CRM', desc: 'Payment behavior tracking, outstanding management, aging analysis with FY-based opening balance. Tally/Busy-verified outstanding ✓ badge.' },
  { icon: Truck, title: 'Dispatch Terminal', desc: 'Warehouse Kanban with LR tracking, document uploads, porter & transporter settlement, online-orders panel sorted by invoice, and Close-of-Day PDF.' },
  { icon: ShoppingCart, title: 'Salesman Orders & Beat Plans', desc: 'Mobile-first order collection. Daily Beat Run sheet auto-derived from your plan. Single-salesman-per-customer enforcement. FY-aware achievement %, customer-wise drill-down.', isNew: true },
  { icon: Brain, title: 'AI-Powered Reports', desc: 'GPT-5.2 powered purchase order generation, expense insights, natural-language queries across your entire Tally* / Busy* data.' },
  { icon: Landmark, title: 'CA Corner — Tally/Busy Parity', desc: 'Cash Flow, P&L with ledger drill-down, Balance Sheet — matches your accounting software exactly to the rupee. AI expense insights powered by GPT-5.2.' },
  { icon: Lightbulb, title: 'Insider Result BI', desc: 'Customer lifecycle, sales forecast, SPIP gap analysis, concentration risk with Pareto charts.' },
  { icon: Database, title: 'Backups & DPDP Data Export', desc: 'Daily encrypted MongoDB dumps + one-click ZIP export of your full tenant data — DPDP Act 2023 right-to-portability compliant.', isNew: true },
  { icon: Shield, title: 'Bank-Grade Security', desc: 'AES-256 encryption, bcrypt hashing, JWT auth, field-level PII encryption, multi-tenant data isolation, complete audit trail.' },
];

const TESTIMONIALS = [
  { name: 'Rajesh Agarwal', company: 'Agarwal Auto Parts, Raipur', text: 'FLOWRA completely transformed how we track inventory. We identified 15 lakh in dead stock within the first week.', img: 'https://images.unsplash.com/photo-1695391396401-5fbb4bedafc1?w=120&h=120&fit=crop' },
  { name: 'Priya Sharma', company: 'Sharma Trading Co., Indore', text: 'The salesman performance module helped us increase collection efficiency by 40%. The FY-locked targets are brilliant.', img: 'https://images.unsplash.com/photo-1770627000564-3feb36aecbcd?w=120&h=120&fit=crop' },
  { name: 'Vikram Patel', company: 'National Engineering Works', text: 'AI reports save us 3 hours daily. The Tally* / Busy* sync is seamless — our data is always up to date without any manual work.', img: 'https://images.pexels.com/photos/5920775/pexels-photo-5920775.jpeg?w=120&h=120&fit=crop' },
];

const LandingPage = ({ onNavigateToLogin, onNavigateToSignup, onNavigate }) => {
  const [billingCycle, setBillingCycle] = useState('annual');
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileResourcesOpen, setMobileResourcesOpen] = useState(false);
  const resourcesRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (resourcesRef.current && !resourcesRef.current.contains(e.target)) setResourcesOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
      {/* Sticky Header */}
      <header className="bg-white/90 backdrop-blur-xl border-b border-zinc-100 sticky top-0 z-50" data-testid="landing-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/flowra-logo.png" alt="FLOWRA" className="h-8 object-contain" />
            <span className="text-lg font-bold text-zinc-950 tracking-tight" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>FLOWRA</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-zinc-600">
            <button onClick={() => scrollTo('features')} className="hover:text-zinc-950 transition-colors">Features</button>
            <button onClick={() => scrollTo('pricing')} className="hover:text-zinc-950 transition-colors">Pricing</button>
            <button onClick={() => scrollTo('testimonials')} className="hover:text-zinc-950 transition-colors">Testimonials</button>
            <button onClick={() => scrollTo('security')} className="hover:text-zinc-950 transition-colors">Security</button>
            <div className="relative" ref={resourcesRef}>
              <button onClick={() => setResourcesOpen(!resourcesOpen)} className="hover:text-zinc-950 transition-colors flex items-center gap-1" data-testid="resources-menu-btn">
                Resources <ChevronDown size={14} className={`transition-transform ${resourcesOpen ? 'rotate-180' : ''}`} />
              </button>
              {resourcesOpen && (
                <div className="absolute top-full right-0 mt-2 w-72 bg-white border border-zinc-200 rounded-xl shadow-xl py-2 z-50" data-testid="resources-dropdown">
                  <div className="px-4 py-2 text-[10px] uppercase tracking-wider font-bold text-zinc-400">Forms</div>
                  <button onClick={() => { onNavigate?.('questionnaire'); setResourcesOpen(false); }}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-questionnaire">
                    <ClipboardList size={16} className="text-[#0052FF]" /> Needs Assessment (online)
                  </button>
                  <a href="/FLOWRA_Customer_Questionnaire.pdf" target="_blank" rel="noopener noreferrer" onClick={() => setResourcesOpen(false)}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-pdf-questionnaire">
                    <Download size={16} className="text-[#0052FF]" /> Customer Questionnaire (PDF)
                  </a>

                  <div className="border-t border-zinc-100 my-1"></div>
                  <div className="px-4 py-2 text-[10px] uppercase tracking-wider font-bold text-zinc-400">Documents</div>
                  <a href="/FLOWRA_Presentation.pdf" target="_blank" rel="noopener noreferrer" onClick={() => setResourcesOpen(false)}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-presentation">
                    <FileText size={16} className="text-[#0052FF]" /> Product Presentation
                  </a>
                  <a href="/FLOWRA_Deployment_Guide.pdf" target="_blank" rel="noopener noreferrer" onClick={() => setResourcesOpen(false)}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-deployment">
                    <Warehouse size={16} className="text-[#0052FF]" /> Deployment Guide
                  </a>
                  <a href="/FLOWRA_Whats_New.pdf" target="_blank" rel="noopener noreferrer" onClick={() => setResourcesOpen(false)}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-whats-new">
                    <Sparkles size={16} className="text-[#0052FF]" /> What's New (Latest Features)
                  </a>
                  <a href="/FLOWRA_Coming_Soon.pdf" target="_blank" rel="noopener noreferrer" onClick={() => setResourcesOpen(false)}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-zinc-50 flex items-center gap-2.5 text-zinc-700" data-testid="resources-coming-soon">
                    <Rocket size={16} className="text-[#0052FF]" /> Coming Soon
                  </a>
                </div>
              )}
            </div>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <button onClick={onNavigateToLogin} data-testid="header-login-btn" className="text-xs sm:text-sm font-bold text-zinc-950 border border-zinc-950 rounded-sm px-3 sm:px-5 py-2 hover:bg-zinc-100 transition-colors">
              Login
            </button>
            <button onClick={onNavigateToSignup} data-testid="header-signup-btn" className="text-xs sm:text-sm font-bold bg-[#0052FF] text-white rounded-sm px-3 sm:px-5 py-2 hover:bg-[#0039B3] transition-colors">
              Get Started
            </button>
            <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    className="md:hidden p-1.5 rounded-md hover:bg-zinc-100 transition-colors"
                    data-testid="mobile-menu-toggle"
                    aria-label="Toggle menu">
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile menu drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-zinc-100 bg-white" data-testid="mobile-menu">
            <div className="max-w-7xl mx-auto px-6 py-3 space-y-1 text-sm font-medium text-zinc-700">
              <button onClick={() => { scrollTo('features'); setMobileMenuOpen(false); }} className="w-full text-left py-2.5 hover:text-[#0052FF]">Features</button>
              <button onClick={() => { scrollTo('pricing'); setMobileMenuOpen(false); }} className="w-full text-left py-2.5 hover:text-[#0052FF]">Pricing</button>
              <button onClick={() => { scrollTo('testimonials'); setMobileMenuOpen(false); }} className="w-full text-left py-2.5 hover:text-[#0052FF]">Testimonials</button>
              <button onClick={() => { scrollTo('security'); setMobileMenuOpen(false); }} className="w-full text-left py-2.5 hover:text-[#0052FF]">Security</button>

              <button onClick={() => setMobileResourcesOpen(!mobileResourcesOpen)}
                      className="w-full flex items-center justify-between py-2.5 hover:text-[#0052FF]"
                      data-testid="mobile-resources-toggle">
                <span>Resources</span>
                <ChevronDown size={16} className={`transition-transform ${mobileResourcesOpen ? 'rotate-180' : ''}`} />
              </button>
              {mobileResourcesOpen && (
                <div className="ml-3 pl-3 border-l-2 border-zinc-100 space-y-1 pb-2" data-testid="mobile-resources-list">
                  <button onClick={() => { onNavigate?.('questionnaire'); setMobileMenuOpen(false); }}
                          className="w-full text-left py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <ClipboardList size={14} className="text-[#0052FF]" /> Needs Assessment
                  </button>
                  <a href="/FLOWRA_Customer_Questionnaire.pdf" target="_blank" rel="noopener noreferrer"
                     className="block py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <Download size={14} className="text-[#0052FF]" /> Customer Questionnaire
                  </a>
                  <a href="/FLOWRA_Presentation.pdf" target="_blank" rel="noopener noreferrer"
                     className="block py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <FileText size={14} className="text-[#0052FF]" /> Product Presentation
                  </a>
                  <a href="/FLOWRA_Deployment_Guide.pdf" target="_blank" rel="noopener noreferrer"
                     className="block py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <Warehouse size={14} className="text-[#0052FF]" /> Deployment Guide
                  </a>
                  <a href="/FLOWRA_Whats_New.pdf" target="_blank" rel="noopener noreferrer"
                     className="block py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <Sparkles size={14} className="text-[#0052FF]" /> What's New
                  </a>
                  <a href="/FLOWRA_Coming_Soon.pdf" target="_blank" rel="noopener noreferrer"
                     className="block py-2 text-sm hover:text-[#0052FF] flex items-center gap-2">
                    <Rocket size={14} className="text-[#0052FF]" /> Coming Soon
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="py-20 lg:py-28 bg-white" data-testid="hero-section">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-4">Tally* + Busy* Analytics Platform</p>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-zinc-950 tracking-tighter leading-[1.05] mb-6" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Unlock the full power of your <span className="text-[#0052FF]">Tally* / Busy* Data</span>
            </h1>
            <p className="text-lg text-zinc-600 leading-relaxed mb-8 max-w-lg">
              Real-time inventory analytics with A/B/C/D Pareto, sales tracking, CRM, beat plans, dispatch terminal and AI-powered insights — synced directly from Tally* or Busy*. Built for Indian SMEs with bank-grade security.
            </p>
            <div className="flex flex-wrap gap-4">
              <button onClick={onNavigateToSignup} data-testid="hero-signup-btn" className="bg-[#0052FF] text-white rounded-sm px-8 py-3.5 font-bold text-base hover:bg-[#0039B3] transition-colors flex items-center gap-2">
                Start Free Trial <ArrowRight size={18} />
              </button>
              <button onClick={() => scrollTo('features')} className="text-zinc-950 border border-zinc-300 rounded-sm px-8 py-3.5 font-bold text-base hover:bg-zinc-50 transition-colors">
                See Features
              </button>
            </div>
            <div className="flex items-center gap-6 mt-8 text-sm text-zinc-500">
              <span className="flex items-center gap-1.5"><Shield size={14} className="text-green-600" /> 256-bit Encryption</span>
              <span className="flex items-center gap-1.5"><Clock size={14} className="text-blue-600" /> 2-min Setup</span>
              <span className="flex items-center gap-1.5"><Zap size={14} className="text-amber-600" /> No Data on Cloud*</span>
            </div>
          </div>
          <div className="hidden lg:block">
            {/* Animated Dashboard Mockup */}
            <div className="bg-white border border-zinc-200 rounded-sm shadow-2xl shadow-zinc-900/10 overflow-hidden">
              <div className="bg-zinc-900 px-4 py-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <span className="text-[10px] text-zinc-400 font-mono">flowralive.in/dashboard</span>
                <div className="w-12" />
              </div>
              <div className="flex">
                <div className="w-40 bg-zinc-50 border-r border-zinc-100 py-3 px-2">
                  {[{n:'Dashboard',a:true},{n:'Sales',a:false},{n:'CRM',a:false},{n:'Inventory',a:false},{n:'Analytics',a:false},{n:'AI Reports',a:false}].map(m => (
                    <div key={m.n} className={`text-[10px] px-3 py-1.5 rounded mb-0.5 ${m.a ? 'bg-[#0052FF] text-white font-semibold' : 'text-zinc-500'}`}>{m.n}</div>
                  ))}
                </div>
                <div className="flex-1 p-4 bg-white">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-zinc-900">Business Overview</p>
                    <span className="text-[9px] text-zinc-400 border border-zinc-200 rounded px-1.5 py-0.5">FY 2025-26</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {[{l:'Total Sales',v:'Rs.52.3L',c:'text-blue-600'},{l:'Items',v:'156',c:'text-purple-600'},{l:'Low Stock',v:'23',c:'text-red-500'}].map(s => (
                      <div key={s.l} className="bg-zinc-50 border border-zinc-100 rounded p-2">
                        <p className="text-[8px] text-zinc-400">{s.l}</p>
                        <p className={`text-sm font-bold ${s.c}`}>{s.v}</p>
                      </div>
                    ))}
                  </div>
                  <div className="bg-zinc-50 border border-zinc-100 rounded p-2 mb-2">
                    <p className="text-[8px] font-semibold text-zinc-600 mb-1">Recent Sales</p>
                    {['ABC Motors ‑ Rs.1.2L','Shree Krishna ‑ Rs.98K','National Auto ‑ Rs.75K','Mahalaxmi ‑ Rs.62K'].map(t => (
                      <div key={t} className="flex justify-between text-[8px] py-0.5 border-b border-zinc-50 last:border-0">
                        <span className="text-zinc-600">{t.split(' ‑ ')[0]}</span>
                        <span className="text-[#0052FF] font-semibold">{t.split(' ‑ ')[1]}</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-[7px] text-zinc-400 text-right">Last sync: 10/04/2026, 14:30 IST</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 bg-zinc-50" data-testid="features-section">
        <div className="max-w-7xl mx-auto px-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">Platform Features</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-zinc-950 tracking-tight mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
            Everything you need to run your business smarter
          </h2>
          <p className="text-zinc-600 text-lg mb-12 max-w-2xl">From inventory A/B/C/D categorisation to AI-powered purchase orders, FLOWRA brings enterprise-grade analytics to every Tally* and Busy* user.</p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <div key={i} className="bg-white border border-zinc-200 rounded-sm p-8 hover:-translate-y-1 hover:border-zinc-300 transition-all relative" data-testid={`feature-card-${i}`}>
                {f.isNew && <span className="absolute top-3 right-3 text-[9px] font-bold bg-blue-600 text-white px-2 py-0.5 rounded-full">NEW</span>}
                <div className="w-11 h-11 bg-zinc-950 rounded-sm flex items-center justify-center mb-5">
                  <f.icon size={20} className="text-white" />
                </div>
                <h3 className="text-lg font-bold text-zinc-950 mb-2">{f.title}</h3>
                <p className="text-sm text-zinc-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Security */}
      <section id="security" className="py-24 bg-zinc-950 text-white" data-testid="security-section">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">Enterprise Security</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-6" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Your data stays yours. Period.
            </h2>
            <p className="text-zinc-400 text-lg leading-relaxed mb-8">
              FLOWRA is built with security-first architecture. Your Tally* or Busy* data is synced through an encrypted local agent — your accounting software is never exposed to the internet.
            </p>
            <div className="space-y-5">
              {[
                { icon: Lock, text: 'AES-256 field-level encryption for all PII data' },
                { icon: Database, text: 'Multi-tenant isolation — your data is invisible to others' },
                { icon: Shield, text: 'Bcrypt password hashing with per-user salt' },
                { icon: Eye, text: 'Complete audit trail of every action' },
                { icon: Globe, text: 'HTTPS/TLS, HSTS, CSP, XSS protection headers' },
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-[#0052FF]/20 rounded-sm flex items-center justify-center flex-shrink-0 mt-0.5">
                    <item.icon size={16} className="text-[#0052FF]" />
                  </div>
                  <p className="text-zinc-300 text-sm">{item.text}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="hidden lg:block">
            <img src="https://static.prod-images.emergentagent.com/jobs/e93f8a38-4ad0-4d0c-b41a-81b9cd3b283f/images/79d800c4ff059a91b2cbe505090dd05a64aa55b94e6fcabc1044f3c0734b6697.png" alt="Security" className="w-full rounded-sm opacity-80" />
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 bg-white" data-testid="pricing-section">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-12">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">Pricing Plans</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-zinc-950 tracking-tight mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Simple, transparent pricing
            </h2>
            <p className="text-zinc-600 text-lg mb-8">Choose the plan that fits your business. All plans include Tally* and Busy* sync, and secure cloud analytics.</p>

            <div className="inline-flex bg-zinc-100 rounded-sm p-1">
              <button onClick={() => setBillingCycle('monthly')} className={`px-5 py-2 text-sm font-bold rounded-sm transition-colors ${billingCycle === 'monthly' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'}`}>Monthly</button>
              <button onClick={() => setBillingCycle('annual')} className={`px-5 py-2 text-sm font-bold rounded-sm transition-colors ${billingCycle === 'annual' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'}`}>
                Annual <span className="text-xs text-green-600 ml-1">Save 17%</span>
              </button>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {PLANS.map((plan) => (
              <div key={plan.id} className={`border rounded-sm p-8 relative ${plan.popular ? 'border-[#0052FF] border-2 scale-[1.02]' : 'border-zinc-200'}`} data-testid={`plan-${plan.id}`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#0052FF] text-white text-xs font-bold px-4 py-1 rounded-sm">
                    Most Popular
                  </div>
                )}
                <h3 className="text-xl font-bold text-zinc-950 mb-1">{plan.name}</h3>
                <p className="text-sm text-zinc-500 mb-5">{plan.desc}</p>
                <div className="mb-6">
                  <span className="text-4xl font-black text-zinc-950" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
                    {billingCycle === 'annual' ? `₹${Math.round(plan.annual / 12).toLocaleString('en-IN')}` : `₹${plan.monthly.toLocaleString('en-IN')}`}
                  </span>
                  <span className="text-zinc-500 text-sm">/month</span>
                  {billingCycle === 'annual' && <p className="text-xs text-green-600 mt-1">Billed ₹{plan.annual.toLocaleString('en-IN')}/year</p>}
                </div>
                <button onClick={onNavigateToSignup} className={`w-full py-3 font-bold rounded-sm transition-colors mb-6 ${plan.popular ? 'bg-[#0052FF] text-white hover:bg-[#0039B3]' : 'bg-zinc-950 text-white hover:bg-zinc-800'}`}>
                  Get Started
                </button>
                <div className="space-y-3">
                  {plan.features.map((f, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <Check size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                      <span className="text-sm text-zinc-600">{f}</span>
                    </div>
                  ))}
                  <p className="text-xs text-zinc-400 pt-2">Up to {plan.maxCompanies} companies, {plan.maxEmployees} employees</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="py-24 bg-zinc-50" data-testid="testimonials-section">
        <div className="max-w-7xl mx-auto px-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">What Our Customers Say</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-zinc-950 tracking-tight mb-12" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
            Trusted by 500+ Indian businesses
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t, i) => (
              <div key={i} className="bg-white border border-zinc-200 rounded-sm p-8" data-testid={`testimonial-${i}`}>
                <div className="flex items-center gap-1 mb-4">
                  {[1,2,3,4,5].map(s => <Star key={s} size={14} className="text-amber-400 fill-amber-400" />)}
                </div>
                <p className="text-zinc-700 text-sm leading-relaxed mb-6">"{t.text}"</p>
                <div className="flex items-center gap-3">
                  <img src={t.img} alt={t.name} className="w-10 h-10 rounded-full object-cover" />
                  <div>
                    <p className="text-sm font-bold text-zinc-950">{t.name}</p>
                    <p className="text-xs text-zinc-500">{t.company}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-[#0052FF]" data-testid="cta-section">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
            Ready to transform your business?
          </h2>
          <p className="text-blue-100 text-lg mb-8">Join 500+ businesses already using FLOWRA. Start your free trial today.</p>
          <button onClick={onNavigateToSignup} data-testid="cta-signup-btn" className="bg-white text-[#0052FF] rounded-sm px-10 py-4 font-bold text-lg hover:bg-zinc-100 transition-colors">
            Sign Up Free <ChevronRight size={20} className="inline ml-1" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 bg-zinc-950 text-zinc-400" data-testid="footer">
        <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-4 gap-12">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <img src="/flowra-logo.png" alt="FLOWRA" className="h-8 object-contain brightness-200" />
              <span className="text-white font-bold">FLOWRA</span>
            </div>
            <p className="text-sm leading-relaxed">Organize. Automate. Accelerate.</p>
            <p className="text-xs mt-3">Tally* + Busy* analytics platform for Indian SMEs.</p>
            <p className="text-xs mt-2 text-zinc-500">A product by <strong className="text-zinc-300">JODIDAR INDIA</strong></p>
          </div>
          <div>
            <h4 className="text-white font-bold text-sm mb-4">Product</h4>
            <div className="space-y-2 text-sm">
              <button onClick={() => scrollTo('features')} className="block hover:text-white transition-colors">Features</button>
              <button onClick={() => scrollTo('pricing')} className="block hover:text-white transition-colors">Pricing</button>
              <button onClick={() => scrollTo('security')} className="block hover:text-white transition-colors">Security</button>
              <button onClick={() => onNavigate?.('questionnaire')} className="block hover:text-white transition-colors">Needs Assessment</button>
              <a href="/FLOWRA_Presentation.pdf" target="_blank" rel="noopener noreferrer" className="block hover:text-white transition-colors">Presentation</a>
            </div>
          </div>
          <div>
            <h4 className="text-white font-bold text-sm mb-4">Legal</h4>
            <div className="space-y-2 text-sm">
              <button onClick={() => onNavigate?.('privacy')} className="block hover:text-white transition-colors">Privacy Policy</button>
              <button onClick={() => onNavigate?.('terms')} className="block hover:text-white transition-colors">Terms of Service</button>
              <button onClick={() => onNavigate?.('refund')} className="block hover:text-white transition-colors">Refund Policy</button>
              <button onClick={() => onNavigate?.('contact')} className="block hover:text-white transition-colors">Contact Us</button>
              <button onClick={() => onNavigate?.('social')} className="block hover:text-white transition-colors">Social Media</button>
            </div>
          </div>
          <div>
            <h4 className="text-white font-bold text-sm mb-4">Contact</h4>
            <div className="space-y-3 text-sm">
              <p className="flex items-center gap-2"><Mail size={14} /> support@flowralive.in</p>
              <a href="tel:+918120470018" className="flex items-center gap-2 hover:text-white transition-colors"><Phone size={14} /> +91 81204 70018</a>
              <a href="https://wa.me/918120470018?text=Hi%2C%20I%20want%20to%20know%20about%20FLOWRA" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 hover:text-white transition-colors"><MessageCircle size={14} /> WhatsApp</a>
            </div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-6 mt-12 pt-8 border-t border-zinc-800 text-xs text-zinc-500 text-center">
          &copy; {new Date().getFullYear()} JODIDAR INDIA. All rights reserved. FLOWRA is a brand owned by JODIDAR INDIA.
        </div>
        <div className="max-w-7xl mx-auto px-6 mt-4 text-[10px] text-zinc-600 text-center leading-relaxed" data-testid="tally-disclaimer">
          Tally* and Busy* are trademarks of their respective owners and are not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites. The same are used in accordance with honest practices and not used with any intention to misguide customers to take unfair advantage of the trademarks' distinct character or harm the holders' reputation.
        </div>
      </footer>

      {/* WhatsApp Floating Button */}
      <a
        href="https://wa.me/918120470018?text=Hi%2C%20I%20want%20to%20know%20more%20about%20FLOWRA"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-[#25D366] rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition-transform"
        data-testid="whatsapp-btn"
        aria-label="Chat on WhatsApp"
      >
        <MessageCircle size={26} className="text-white" fill="white" />
      </a>
    </div>
  );
};

export default LandingPage;
