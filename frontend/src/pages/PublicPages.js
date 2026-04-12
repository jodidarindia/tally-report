import React from 'react';
import { ArrowLeft, Mail, Phone, MessageCircle } from 'lucide-react';

const PUBLIC_FOOTER = ({ onNavigate }) => (
  <footer className="py-12 bg-zinc-950 text-zinc-400">
    <div className="max-w-5xl mx-auto px-6 grid sm:grid-cols-3 gap-10">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <img src="/flowra-logo.png" alt="FLOWRA" className="h-7 object-contain brightness-200" />
          <span className="text-white font-bold">FLOWRA</span>
        </div>
        <p className="text-xs leading-relaxed">Organize. Automate. Accelerate.</p>
        <p className="text-xs mt-2 text-zinc-500">A product by <strong className="text-zinc-300">JODIDAR INDIA</strong></p>
      </div>
      <div>
        <h4 className="text-white font-bold text-sm mb-3">Legal</h4>
        <div className="space-y-2 text-sm">
          <button onClick={() => onNavigate('privacy')} className="block hover:text-white transition-colors">Privacy Policy</button>
          <button onClick={() => onNavigate('terms')} className="block hover:text-white transition-colors">Terms of Service</button>
          <button onClick={() => onNavigate('refund')} className="block hover:text-white transition-colors">Refund Policy</button>
          <button onClick={() => onNavigate('contact')} className="block hover:text-white transition-colors">Contact Us</button>
        </div>
      </div>
      <div>
        <h4 className="text-white font-bold text-sm mb-3">Connect</h4>
        <div className="space-y-2 text-sm">
          <p className="flex items-center gap-2"><Mail size={13} /> support@flowralive.in</p>
          <p className="flex items-center gap-2"><Phone size={13} /> +91 81204 70018</p>
          <button onClick={() => onNavigate('social')} className="block hover:text-white transition-colors">Social Media</button>
        </div>
      </div>
    </div>
    <div className="max-w-5xl mx-auto px-6 mt-10 pt-6 border-t border-zinc-800 text-[11px] text-zinc-500 text-center">
      &copy; {new Date().getFullYear()} JODIDAR INDIA. All rights reserved. FLOWRA is a brand owned by JODIDAR INDIA.
    </div>
  </footer>
);

const WhatsAppButton = () => (
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
);

const PageShell = ({ title, onNavigate, onBack, children }) => (
  <div className="min-h-screen bg-white flex flex-col">
    <nav className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <div className="max-w-5xl mx-auto px-6 flex items-center justify-between h-14">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm font-medium" data-testid="back-btn">
          <ArrowLeft size={18} /> Back to Home
        </button>
        <div className="flex items-center gap-2">
          <img src="/flowra-logo.png" alt="FLOWRA" className="h-6 object-contain" />
          <span className="font-bold text-slate-900 text-sm">FLOWRA</span>
        </div>
      </div>
    </nav>
    <main className="flex-1 max-w-4xl mx-auto px-6 py-12 w-full">
      <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-2 tracking-tight" style={{ fontFamily: 'Outfit, sans-serif' }}>{title}</h1>
      <div className="h-1 w-16 bg-[#2563EB] rounded mb-8"></div>
      <div className="prose prose-slate max-w-none text-[15px] leading-relaxed">
        {children}
      </div>
    </main>
    <PUBLIC_FOOTER onNavigate={onNavigate} />
    <WhatsAppButton />
  </div>
);

/* ─── Privacy Policy ────────────────────────────────────── */
export const PrivacyPolicy = ({ onNavigate, onBack }) => (
  <PageShell title="Privacy Policy" onNavigate={onNavigate} onBack={onBack}>
    <p className="text-slate-500 text-sm mb-8">Last updated: April 2026</p>

    <p>This Privacy Policy describes how <strong>JODIDAR INDIA</strong> ("we", "us", "our"), the owner and operator of <strong>FLOWRA</strong> (accessible at <strong>www.flowralive.in</strong>), collects, uses, and protects your personal data in compliance with the <strong>Digital Personal Data Protection Act, 2023 (DPDP Act)</strong> and the <strong>Information Technology Act, 2000</strong> of India.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">1. Data We Collect</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li><strong>Account Information:</strong> Name, email address, phone number, business name provided during registration.</li>
      <li><strong>Business Data:</strong> Inventory, sales, purchase, and customer records synced from your Tally Prime software via the FLOWRA Desktop Agent.</li>
      <li><strong>Usage Data:</strong> Login timestamps, feature access logs, browser type, and IP address collected automatically.</li>
      <li><strong>Payment Data:</strong> Billing details processed through our third-party payment gateway. We do not store card or bank account details.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">2. Purpose of Data Collection</h2>
    <p>We process your data for the following purposes:</p>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Providing and maintaining the FLOWRA platform and its features.</li>
      <li>Syncing and displaying your Tally Prime business data.</li>
      <li>Generating analytics, reports, and AI-powered insights.</li>
      <li>Customer support and communication.</li>
      <li>Ensuring platform security and preventing unauthorized access.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">3. Legal Basis</h2>
    <p>We process your personal data based on:</p>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li><strong>Consent:</strong> You provide explicit consent during account creation.</li>
      <li><strong>Contractual Necessity:</strong> Processing required to deliver the SaaS service you subscribed to.</li>
      <li><strong>Legitimate Interest:</strong> Platform security, analytics, and service improvement.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">4. Data Storage & Security</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Your data is stored on secure cloud servers with encryption at rest and in transit.</li>
      <li>Access is restricted to authorized personnel only.</li>
      <li>We implement industry-standard security measures including JWT-based authentication and role-based access control.</li>
      <li>Data is retained for the duration of your active subscription plus 90 days post-cancellation, after which it is permanently deleted upon request.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">5. Data Sharing</h2>
    <p>We do <strong>not</strong> sell, trade, or rent your personal data. Data may be shared with:</p>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Cloud infrastructure providers for hosting purposes.</li>
      <li>Payment gateway providers for subscription processing.</li>
      <li>Government or law enforcement agencies if required under applicable Indian law.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">6. Your Rights (Under DPDP Act, 2023)</h2>
    <p>As a data principal, you have the right to:</p>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Access the personal data we hold about you.</li>
      <li>Request correction of inaccurate data.</li>
      <li>Request erasure of your data (subject to legal obligations).</li>
      <li>Withdraw consent at any time by contacting us.</li>
      <li>Nominate a person to exercise rights on your behalf.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">7. Cookies</h2>
    <p>FLOWRA uses essential cookies and local storage for authentication and session management. We do not use third-party tracking cookies.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">8. Grievance Officer</h2>
    <p>In accordance with the IT Act 2000 and DPDP Act 2023, grievances may be addressed to:</p>
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mt-2 text-sm">
      <p><strong>Grievance Officer</strong></p>
      <p>JODIDAR INDIA</p>
      <p>Email: <a href="mailto:support@flowralive.in" className="text-[#2563EB]">support@flowralive.in</a></p>
      <p>Phone: <a href="tel:+918120470018" className="text-[#2563EB]">+91 81204 70018</a></p>
      <p>Address: KK Road, Raipur, Chhattisgarh, India</p>
    </div>
  </PageShell>
);

/* ─── Terms of Service ──────────────────────────────────── */
export const TermsOfService = ({ onNavigate, onBack }) => (
  <PageShell title="Terms of Service" onNavigate={onNavigate} onBack={onBack}>
    <p className="text-slate-500 text-sm mb-8">Last updated: April 2026</p>

    <p>These Terms of Service ("Terms") govern your use of the FLOWRA platform operated by <strong>JODIDAR INDIA</strong>. By accessing or using FLOWRA, you agree to be bound by these Terms.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">1. Definitions</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li><strong>"Platform"</strong> refers to the FLOWRA web application at www.flowralive.in and the FLOWRA Desktop Agent.</li>
      <li><strong>"User"</strong> refers to any individual or business entity that creates an account on the Platform.</li>
      <li><strong>"Subscription"</strong> refers to the paid plan that grants access to specific features of the Platform.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">2. Eligibility</h2>
    <p>You must be at least 18 years of age and have the legal capacity to enter into binding agreements under Indian law. By using the Platform, you represent that you meet these requirements.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">3. Account Responsibilities</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>You are responsible for maintaining the confidentiality of your login credentials.</li>
      <li>You agree to provide accurate and complete information during registration.</li>
      <li>You are liable for all activity conducted under your account.</li>
      <li>You must notify us immediately of any unauthorized access to your account.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">4. Subscription & Payments</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>FLOWRA offers monthly and annual subscription plans. Pricing is displayed on the Platform.</li>
      <li>Payments are processed through authorized third-party payment gateways.</li>
      <li>All prices are in Indian Rupees (INR) and inclusive of applicable GST.</li>
      <li>Subscription renews automatically unless cancelled before the renewal date.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">5. Acceptable Use</h2>
    <p>You agree not to:</p>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Use the Platform for any unlawful purpose or in violation of Indian law.</li>
      <li>Attempt to reverse-engineer, decompile, or disassemble any part of the Platform.</li>
      <li>Share your credentials with unauthorized persons.</li>
      <li>Upload malicious code, viruses, or attempt to compromise Platform security.</li>
      <li>Use the Platform to store or transmit any content that infringes third-party rights.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">6. Data Ownership</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Your business data synced through Tally Prime remains <strong>your property</strong>.</li>
      <li>FLOWRA does not claim ownership over your data.</li>
      <li>We are granted a limited license to process your data solely for the purpose of delivering the service.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">7. Intellectual Property</h2>
    <p>The FLOWRA brand, logo, design, codebase, and all associated intellectual property are owned by <strong>JODIDAR INDIA</strong>. Unauthorized reproduction or distribution is prohibited.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">8. Service Availability</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>We aim for maximum uptime but do not guarantee uninterrupted service.</li>
      <li>Scheduled maintenance will be communicated in advance where possible.</li>
      <li>We are not liable for downtime caused by factors beyond our control.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">9. Limitation of Liability</h2>
    <p>To the fullest extent permitted by Indian law, JODIDAR INDIA shall not be liable for any indirect, incidental, consequential, or punitive damages arising from your use of the Platform. Our total liability shall not exceed the subscription fees paid by you in the preceding 12 months.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">10. Termination</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>You may cancel your subscription at any time from your account settings.</li>
      <li>We reserve the right to suspend or terminate accounts that violate these Terms.</li>
      <li>Upon termination, your data will be retained for 90 days and then permanently deleted.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">11. Governing Law & Dispute Resolution</h2>
    <p>These Terms are governed by the laws of India. Any disputes shall be subject to the exclusive jurisdiction of the courts in <strong>Raipur, Chhattisgarh</strong>. Parties agree to attempt mediation before initiating legal proceedings.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">12. Contact</h2>
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mt-2 text-sm">
      <p><strong>JODIDAR INDIA</strong></p>
      <p>Email: <a href="mailto:support@flowralive.in" className="text-[#2563EB]">support@flowralive.in</a></p>
      <p>Phone: <a href="tel:+918120470018" className="text-[#2563EB]">+91 81204 70018</a></p>
    </div>
  </PageShell>
);

/* ─── Refund & Cancellation Policy ──────────────────────── */
export const RefundPolicy = ({ onNavigate, onBack }) => (
  <PageShell title="Refund & Cancellation Policy" onNavigate={onNavigate} onBack={onBack}>
    <p className="text-slate-500 text-sm mb-8">Last updated: April 2026</p>

    <p>This Refund and Cancellation Policy applies to all subscription plans on the FLOWRA platform operated by <strong>JODIDAR INDIA</strong>.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">1. Cancellation</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>You may cancel your subscription at any time from your account settings or by contacting us at <a href="mailto:support@flowralive.in" className="text-[#2563EB]">support@flowralive.in</a>.</li>
      <li>Cancellation will take effect at the end of the current billing cycle.</li>
      <li>You will continue to have access to the Platform until the end of your paid period.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">2. Refund Eligibility</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li><strong>Within 7 days of purchase:</strong> Full refund if you are unsatisfied with the service, provided the refund is requested within 7 days of the initial subscription or renewal.</li>
      <li><strong>After 7 days:</strong> No refund will be issued for the current billing cycle. You may cancel to prevent future charges.</li>
      <li><strong>Annual plans:</strong> Pro-rata refund may be considered within 15 days of annual subscription purchase on a case-by-case basis.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">3. How to Request a Refund</h2>
    <p>To request a refund, contact us with your registered email, subscription details, and reason for refund:</p>
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mt-2 text-sm">
      <p>Email: <a href="mailto:support@flowralive.in" className="text-[#2563EB]">support@flowralive.in</a></p>
      <p>WhatsApp: <a href="https://wa.me/918120470018" className="text-[#2563EB]">+91 81204 70018</a></p>
    </div>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">4. Refund Processing</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Approved refunds will be processed within <strong>7-10 business days</strong>.</li>
      <li>Refunds will be credited to the original payment method.</li>
    </ul>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">5. Non-Refundable Circumstances</h2>
    <ul className="list-disc pl-6 space-y-1.5 text-slate-700">
      <li>Account suspension due to violation of Terms of Service.</li>
      <li>Failure to use the Platform during the subscription period does not entitle a refund.</li>
      <li>Downtime caused by third-party services (e.g., Tally Prime, cloud providers).</li>
    </ul>
  </PageShell>
);

/* ─── Contact Us ────────────────────────────────────────── */
export const ContactPage = ({ onNavigate, onBack }) => (
  <PageShell title="Contact Us" onNavigate={onNavigate} onBack={onBack}>
    <p className="text-slate-600 mb-8">Have a question, feedback, or need support? We'd love to hear from you.</p>

    <div className="grid sm:grid-cols-2 gap-6 mb-12">
      <a href="mailto:support@flowralive.in" className="flex items-start gap-4 p-6 bg-slate-50 border border-slate-200 rounded-xl hover:border-[#2563EB] transition-colors" data-testid="contact-email">
        <div className="w-10 h-10 bg-[#2563EB] rounded-lg flex items-center justify-center flex-shrink-0">
          <Mail size={20} className="text-white" />
        </div>
        <div>
          <h3 className="font-bold text-slate-900 mb-1">Email</h3>
          <p className="text-sm text-slate-600">support@flowralive.in</p>
          <p className="text-xs text-slate-400 mt-1">We respond within 24 hours</p>
        </div>
      </a>
      <a href="https://wa.me/918120470018?text=Hi%2C%20I%20need%20help%20with%20FLOWRA" target="_blank" rel="noopener noreferrer" className="flex items-start gap-4 p-6 bg-slate-50 border border-slate-200 rounded-xl hover:border-[#25D366] transition-colors" data-testid="contact-whatsapp">
        <div className="w-10 h-10 bg-[#25D366] rounded-lg flex items-center justify-center flex-shrink-0">
          <MessageCircle size={20} className="text-white" fill="white" />
        </div>
        <div>
          <h3 className="font-bold text-slate-900 mb-1">WhatsApp</h3>
          <p className="text-sm text-slate-600">+91 81204 70018</p>
          <p className="text-xs text-slate-400 mt-1">Chat with us instantly</p>
        </div>
      </a>
      <a href="tel:+918120470018" className="flex items-start gap-4 p-6 bg-slate-50 border border-slate-200 rounded-xl hover:border-slate-400 transition-colors" data-testid="contact-phone">
        <div className="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center flex-shrink-0">
          <Phone size={20} className="text-white" />
        </div>
        <div>
          <h3 className="font-bold text-slate-900 mb-1">Phone</h3>
          <p className="text-sm text-slate-600">+91 81204 70018</p>
          <p className="text-xs text-slate-400 mt-1">Mon - Sat, 10 AM - 7 PM IST</p>
        </div>
      </a>
    </div>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">Business Hours</h2>
    <p className="text-slate-700">Monday to Saturday: 10:00 AM - 7:00 PM IST</p>
    <p className="text-slate-500 text-sm mt-1">We aim to respond to all queries within 24 hours.</p>

    <h2 className="text-xl font-bold text-slate-900 mt-10 mb-3">Registered Office</h2>
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm">
      <p><strong>JODIDAR INDIA</strong></p>
      <p>KK Road, Raipur, Chhattisgarh, India</p>
      <p className="mt-2">Email: <a href="mailto:support@flowralive.in" className="text-[#2563EB]">support@flowralive.in</a></p>
    </div>
  </PageShell>
);

/* ─── Social Media ──────────────────────────────────────── */
const SOCIAL_CHANNELS = [
  { name: 'Instagram', handle: 'Coming Soon', url: '#', color: 'from-pink-500 to-purple-600', icon: 'M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z' },
  { name: 'Facebook', handle: 'Coming Soon', url: '#', color: 'from-blue-600 to-blue-700', icon: 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z' },
  { name: 'LinkedIn', handle: 'Coming Soon', url: '#', color: 'from-blue-700 to-blue-800', icon: 'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z' },
  { name: 'X (Twitter)', handle: 'Coming Soon', url: '#', color: 'from-slate-800 to-slate-900', icon: 'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z' },
  { name: 'YouTube', handle: 'Coming Soon', url: '#', color: 'from-red-600 to-red-700', icon: 'M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z M9.545 15.568V8.432L15.818 12z' },
];

export const SocialMediaPage = ({ onNavigate, onBack }) => (
  <PageShell title="Follow FLOWRA" onNavigate={onNavigate} onBack={onBack}>
    <p className="text-slate-600 mb-8">Stay connected with FLOWRA for updates, tips, and business insights. Our social media channels are launching soon — follow us to stay in the loop!</p>

    <div className="grid sm:grid-cols-2 gap-4">
      {SOCIAL_CHANNELS.map(ch => (
        <div key={ch.name} className="flex items-center gap-4 p-5 bg-white border border-slate-200 rounded-xl hover:shadow-md transition-shadow" data-testid={`social-${ch.name.toLowerCase().replace(/[^a-z]/g, '')}`}>
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${ch.color} flex items-center justify-center flex-shrink-0`}>
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d={ch.icon} /></svg>
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-slate-900">{ch.name}</h3>
            <p className="text-sm text-slate-400">{ch.handle}</p>
          </div>
          {ch.url !== '#' ? (
            <a href={ch.url} target="_blank" rel="noopener noreferrer" className="px-4 py-2 text-sm font-medium bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8]">Follow</a>
          ) : (
            <span className="px-4 py-2 text-sm font-medium bg-slate-100 text-slate-400 rounded-lg">Soon</span>
          )}
        </div>
      ))}
    </div>

    <div className="mt-12 p-6 bg-blue-50 border border-blue-200 rounded-xl text-center">
      <h3 className="font-bold text-slate-900 mb-2">Get notified when we launch</h3>
      <p className="text-sm text-slate-600 mb-4">Drop us a message and we'll notify you when our social channels go live.</p>
      <a href="https://wa.me/918120470018?text=Hi%2C%20notify%20me%20when%20FLOWRA%20social%20media%20is%20live" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-6 py-3 bg-[#25D366] text-white rounded-lg font-medium hover:bg-[#1da851] transition-colors" data-testid="social-notify-btn">
        <MessageCircle size={18} fill="white" /> Notify me on WhatsApp
      </a>
    </div>
  </PageShell>
);
