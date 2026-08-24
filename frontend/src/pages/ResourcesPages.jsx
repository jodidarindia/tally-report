import React from 'react';
import { ArrowLeft, Printer, Check, Cpu, Zap, Shield, TrendingUp, Users, Building2 } from 'lucide-react';

const Section = ({ eyebrow, title, children }) => (
  <section className="mb-14">
    {eyebrow && <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-2">{eyebrow}</p>}
    {title && <h2 className="text-2xl sm:text-3xl font-bold text-zinc-950 tracking-tight mb-6" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>{title}</h2>}
    <div className="text-zinc-700 text-base leading-relaxed">{children}</div>
  </section>
);

const Stat = ({ label, value }) => (
  <div className="border border-zinc-200 rounded-lg p-5">
    <div className="text-2xl sm:text-3xl font-bold text-zinc-950">{value}</div>
    <div className="text-xs text-zinc-500 mt-1 uppercase tracking-wide">{label}</div>
  </div>
);

export const ProductPresentationPage = ({ onBack }) => (
  <div className="min-h-screen bg-white text-zinc-900" data-testid="product-presentation-page">
    <div className="max-w-4xl mx-auto px-6 py-10 print:py-0 print:px-4">
      <div className="flex items-center justify-between mb-8 print:hidden">
        <button onClick={onBack} className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={() => window.print()} className="inline-flex items-center gap-2 px-3 py-1.5 border border-zinc-200 rounded-sm text-xs font-semibold text-zinc-700 hover:bg-zinc-50">
          <Printer size={14} /> Print / Save as PDF
        </button>
      </div>

      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">Product Presentation · 2026 Edition</p>
      <h1 className="text-4xl sm:text-5xl font-bold text-zinc-950 tracking-tight mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
        FLOWRA — Turn your Tally &amp; Busy data into daily decisions.
      </h1>
      <p className="text-lg text-zinc-600 mb-10 max-w-3xl">
        FLOWRA is the analytics, CRM, forecasting and dispatch layer that plugs directly into Tally* or Busy* — helping
        Indian SMEs move from monthly reports to real-time decisions, at a price point that pays for itself in a single
        recovered outstanding.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-14">
        <Stat label="Live tenants" value="500+" />
        <Stat label="Voucher volume synced" value="42M+" />
        <Stat label="Avg. cash-cycle cut" value="17 days" />
        <Stat label="Time-to-value" value="&lt; 48 hrs" />
      </div>

      <Section eyebrow="The problem" title="Tally &amp; Busy show the numbers. FLOWRA tells you what to do.">
        <ul className="space-y-2 list-disc list-inside text-zinc-700">
          <li>Reports live in a Windows desktop most owners can&apos;t log into.</li>
          <li>Ageing outstandings, slow-moving stock and salesman drop-offs are only spotted in the monthly meet.</li>
          <li>No forecasting, no CRM, no field-force ordering, no dispatch tracking.</li>
          <li>Excel exports break the moment your accountant leaves.</li>
        </ul>
      </Section>

      <Section eyebrow="What FLOWRA does" title="One SaaS. Every business surface, synced from your Tally / Busy.">
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { icon: TrendingUp, title: 'Inventory Analytics', desc: 'A/B/C/D Pareto, below-cost detection, movement × margin, festival-aware demand forecasting with confidence bands.' },
            { icon: Users, title: 'Customer CRM', desc: 'Outstanding ledger, aging buckets, payment behaviour scoring, WhatsApp-ready reminder templates, DPDP-safe data export.' },
            { icon: Cpu, title: 'AI Reports (GPT-5.2)', desc: 'Ask "Top 10 slow movers in FY26?" in plain English. Get a table, a chart and a recommended action — all in seconds.' },
            { icon: Zap, title: 'Demand Forecasting', desc: 'Per-SKU deep-dive with Holt-Winters + festival lens, one-click PO drafts, what-if sliders (Wave 3, shipping this quarter).' },
            { icon: Building2, title: 'Dispatch Terminal', desc: 'Warehouse Kanban with LR tracking, transporter and porter settlement, Close-of-Day PDF for owners.' },
            { icon: Shield, title: 'CA Corner + Audit', desc: 'GST, P&amp;L, BS parity with Tally/Busy. Every voucher signed, immutable audit trail, encrypted daily backups.' },
          ].map((f, i) => (
            <div key={i} className="border border-zinc-200 rounded-lg p-5">
              <f.icon size={18} className="text-[#0052FF] mb-2" />
              <h3 className="font-bold text-zinc-950 mb-1">{f.title}</h3>
              <p className="text-sm text-zinc-600 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="How it works" title="From install to insight in an afternoon.">
        <ol className="space-y-3 list-decimal list-inside text-zinc-700">
          <li><b>Install our desktop agent</b> next to Tally or Busy on your accountant&apos;s machine (or server). One .exe, signed and audited.</li>
          <li><b>Point it at your company</b> — the agent auto-detects your Financial Year and streams vouchers, masters, and ledgers to your private FLOWRA tenant.</li>
          <li><b>Log in on any device</b>. Dashboards, forecasts, CRM, dispatch — all live off the same sync.</li>
          <li><b>Delegate access</b> to your team with fine-grained tab permissions (employee / salesman / dispatch / accountant).</li>
        </ol>
      </Section>

      <Section eyebrow="Security &amp; Compliance" title="Built to India&apos;s DPDP Act, 2023 and audited for enterprise use.">
        <ul className="space-y-1.5">
          {[
            'AES-256 encryption at rest for PII (customers, contacts, GSTINs).',
            'TLS 1.3 in transit + JWT-signed sessions.',
            'Consent-first onboarding — every form captures explicit consent + version.',
            'Right to erasure honoured on request within 30 days.',
            'MongoDB Atlas (Mumbai region) + daily encrypted backups to your Google Drive.',
            'reCAPTCHA v3 + Razorpay-audited payment webhooks.',
          ].map(t => (
            <li key={t} className="flex items-start gap-2 text-sm"><Check size={14} className="text-emerald-600 mt-1 flex-shrink-0" /> <span>{t}</span></li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Pricing" title="One plan pays for itself in a week.">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200">
              <th className="text-left py-2 font-semibold text-zinc-500">Plan</th>
              <th className="text-right py-2 font-semibold text-zinc-500">Monthly</th>
              <th className="text-right py-2 font-semibold text-zinc-500">Annual (save 17%)</th>
              <th className="text-left py-2 font-semibold text-zinc-500 pl-6">Best for</th>
            </tr>
          </thead>
          <tbody className="text-zinc-700">
            <tr className="border-b border-zinc-100"><td className="py-3 font-semibold">Free Trial</td><td className="text-right">—</td><td className="text-right">Free · 14 days</td><td className="pl-6 text-zinc-500">Full Enterprise features</td></tr>
            <tr className="border-b border-zinc-100"><td className="py-3 font-semibold">Starter</td><td className="text-right">₹999</td><td className="text-right">₹9,990</td><td className="pl-6 text-zinc-500">Owner-only dashboard access</td></tr>
            <tr className="border-b border-zinc-100"><td className="py-3 font-semibold">Professional</td><td className="text-right">₹2,499</td><td className="text-right">₹24,990</td><td className="pl-6 text-zinc-500">Owner + salesman + CRM</td></tr>
            <tr><td className="py-3 font-semibold">Enterprise</td><td className="text-right">₹3,799</td><td className="text-right">₹37,990</td><td className="pl-6 text-zinc-500">Full suite, up to 10 users</td></tr>
          </tbody>
        </table>
      </Section>

      <Section eyebrow="Roadmap · Feb 2026" title="What&apos;s shipping in the next quarter.">
        <ul className="space-y-1.5">
          {[
            'Demand Forecast Wave 3 — what-if sliders + one-click POs pushed back into Tally/Busy',
            'Reverse-push integration — FLOWRA dispatch invoices flow INTO Tally as sales vouchers',
            'GST Portal integration — manual GSTR JSON upload + auto-recon in CA Corner',
            'WhatsApp automation for reminders and follow-ups',
            'AI Calling Bot for payment recovery',
          ].map(t => <li key={t} className="flex items-start gap-2"><Check size={14} className="text-emerald-600 mt-1 flex-shrink-0" /><span>{t}</span></li>)}
        </ul>
      </Section>

      <div className="mt-12 pt-8 border-t border-zinc-200 flex items-center justify-between print:hidden">
        <span className="text-xs text-zinc-400">© 2026 JODIDAR INDIA. FLOWRA is a JODIDAR INDIA product.</span>
        <a href="https://insights.flowralive.in" className="text-sm font-semibold text-[#0052FF]">insights.flowralive.in →</a>
      </div>
    </div>
  </div>
);

export const DeploymentGuidePage = ({ onBack }) => (
  <div className="min-h-screen bg-white text-zinc-900" data-testid="deployment-guide-page">
    <div className="max-w-4xl mx-auto px-6 py-10 print:py-0 print:px-4">
      <div className="flex items-center justify-between mb-8 print:hidden">
        <button onClick={onBack} className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-800">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={() => window.print()} className="inline-flex items-center gap-2 px-3 py-1.5 border border-zinc-200 rounded-sm text-xs font-semibold text-zinc-700 hover:bg-zinc-50">
          <Printer size={14} /> Print / Save as PDF
        </button>
      </div>

      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#0052FF] mb-3">Deployment Guide · 2026 Edition</p>
      <h1 className="text-4xl sm:text-5xl font-bold text-zinc-950 tracking-tight mb-4" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>Get FLOWRA live in one working day.</h1>
      <p className="text-lg text-zinc-600 mb-10 max-w-3xl">A step-by-step checklist your accountant and IT partner can follow to install the desktop agent, connect Tally/Busy, and roll out FLOWRA to your team — with zero downtime and no changes to your existing accounting workflow.</p>

      <Section eyebrow="Step 1" title="Provision your FLOWRA tenant">
        <ol className="list-decimal list-inside space-y-2 text-zinc-700">
          <li>Sign up at <b>insights.flowralive.in</b>. A SuperAdmin will approve your enquiry within a working day and enable your 14-day trial.</li>
          <li>Log in with the credentials that arrive by email. Complete your profile (GSTIN, industry, business size).</li>
          <li>Under Profile → Companies, add each Tally / Busy company you want to sync.</li>
        </ol>
      </Section>

      <Section eyebrow="Step 2" title="Install the desktop agent">
        <p className="mb-3">The desktop agent is a small, signed Windows service that reads directly from your Tally XML or Busy ODBC and streams changes to your FLOWRA tenant.</p>
        <ol className="list-decimal list-inside space-y-2 text-zinc-700">
          <li>Download <a href="/FlowraTallyAgent.exe" className="text-[#0052FF] underline">FlowraTallyAgent.exe</a> (or the Busy variant on request).</li>
          <li>Install on the same machine that hosts Tally / Busy. Choose &quot;Run as service&quot; when prompted.</li>
          <li>Paste the connection token from FLOWRA → Profile → Agent Setup. The agent will do a first-time sync (usually 10–20 minutes for a mid-sized business).</li>
          <li>The FLOWRA Sync Status card should now show <b>Green — Synced &lt; 1 hr</b>.</li>
        </ol>
      </Section>

      <Section eyebrow="Step 3" title="Configure Tally / Busy for read access">
        <ul className="list-disc list-inside space-y-1.5 text-zinc-700">
          <li><b>Tally</b>: Enable XML data-server on port 9000 (Gateway → F12 → Data Configuration). No changes to your books required.</li>
          <li><b>Busy</b>: Enable ODBC in Administration → Data Freeze → Configure ODBC (Busy 18+). The agent uses a dedicated read-only user.</li>
          <li>Ensure your antivirus whitelists the FLOWRA agent process (it is code-signed by JODIDAR INDIA).</li>
        </ul>
      </Section>

      <Section eyebrow="Step 4" title="Roll out to your team">
        <ol className="list-decimal list-inside space-y-2 text-zinc-700">
          <li>Under Profile → Employees, invite users with the right role: <b>employee</b>, <b>salesman</b>, <b>dispatch</b>, or <b>admin</b>.</li>
          <li>SuperAdmin can further restrict which tabs each user sees under Admin Mgmt.</li>
          <li>Salesman users install the FLOWRA mobile PWA from <b>insights.flowralive.in</b> — no App Store friction.</li>
          <li>Enable Google Drive backup under Profile → Data &amp; Backups for a daily encrypted mirror to your own Drive.</li>
        </ol>
      </Section>

      <Section eyebrow="Step 5" title="Go-live checklist">
        <ul className="space-y-1.5">
          {[
            'Sync Health card is green and last-sync &lt; 60 minutes.',
            'Dashboard shows current-day sales that match your Tally / Busy DayBook.',
            'CRM Outstanding matches the Tally / Busy party ledger closing balance.',
            'At least one salesman has logged in on the mobile PWA and can place an order.',
            'Daily encrypted backup to Google Drive is scheduled.',
            'DPDP consent + Terms have been accepted in Profile → Compliance.',
          ].map(t => (
            <li key={t} className="flex items-start gap-2 text-sm"><Check size={14} className="text-emerald-600 mt-1 flex-shrink-0" /> <span>{t}</span></li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Support &amp; SLA" title="We are one email away.">
        <p>Reach the FLOWRA team at <a href="mailto:support@flowralive.in" className="text-[#0052FF] underline">support@flowralive.in</a>. Enterprise plans include priority support with a 4-hour response SLA during business hours (10:00–19:00 IST, Mon–Sat). File a ticket in-app under the Support widget and it is routed instantly to the right specialist via Resend inbound routing.</p>
      </Section>

      <div className="mt-12 pt-8 border-t border-zinc-200 flex items-center justify-between print:hidden">
        <span className="text-xs text-zinc-400">© 2026 JODIDAR INDIA. FLOWRA is a JODIDAR INDIA product.</span>
        <a href="https://insights.flowralive.in" className="text-sm font-semibold text-[#0052FF]">insights.flowralive.in →</a>
      </div>
    </div>
  </div>
);

export default ProductPresentationPage;
