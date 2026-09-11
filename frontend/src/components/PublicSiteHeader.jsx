import React from 'react';
import { ArrowLeft } from 'lucide-react';

/*  Shared site header for PUBLIC pages (blog, resources, etc.). Keeps
 *  the marketing look consistent between the landing page and any
 *  standalone article page. Accepts an `onNavigate(key)` callback so
 *  the parent controls the actual routing. */
export const PublicSiteHeader = ({ onNavigate, showBackToBlog = false, onBack }) => (
  <header
    className="bg-white/95 backdrop-blur-xl border-b border-zinc-100 sticky top-0 z-40"
    data-testid="public-site-header"
    style={{ fontFamily: 'Outfit, sans-serif' }}>
    <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
      <button
        type="button"
        onClick={() => onNavigate?.('landing')}
        className="flex items-center gap-3 hover:opacity-80"
        data-testid="public-header-logo">
        <img src="/flowra-logo.png" alt="FLOWRA" className="h-8 object-contain" />
        <span
          className="text-lg font-bold text-zinc-950 tracking-tight"
          style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
          FLOWRA
        </span>
      </button>

      <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-zinc-600">
        <button onClick={() => onNavigate?.('landing')}      className="hover:text-zinc-950 transition-colors" data-testid="public-nav-home">Home</button>
        <button onClick={() => { try { sessionStorage.setItem('flowra_scroll_to', 'features'); } catch {} ; onNavigate?.('landing'); }} className="hover:text-zinc-950 transition-colors" data-testid="public-nav-features">Features</button>
        <button onClick={() => { try { sessionStorage.setItem('flowra_scroll_to', 'pricing');  } catch {} ; onNavigate?.('landing'); }} className="hover:text-zinc-950 transition-colors" data-testid="public-nav-pricing">Pricing</button>
        <button onClick={() => onNavigate?.('blog')}         className="hover:text-zinc-950 transition-colors text-[#0052FF]" data-testid="public-nav-blog">Blog</button>
        <button onClick={() => { try { sessionStorage.setItem('flowra_scroll_to', 'security'); } catch {} ; onNavigate?.('landing'); }} className="hover:text-zinc-950 transition-colors" data-testid="public-nav-security">Security</button>
      </nav>

      <div className="flex items-center gap-3">
        {showBackToBlog && (
          <button
            type="button"
            onClick={onBack}
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-600 hover:text-zinc-950 hover:bg-zinc-50 rounded-lg border border-zinc-200"
            data-testid="public-header-back-btn">
            <ArrowLeft size={12} /> All posts
          </button>
        )}
        <button
          onClick={() => onNavigate?.('login')}
          className="text-sm font-medium text-zinc-700 hover:text-zinc-950 px-3 py-1.5"
          data-testid="public-nav-login">
          Sign in
        </button>
        <button
          onClick={() => onNavigate?.('signup')}
          className="text-sm font-bold text-white bg-[#0052FF] hover:bg-[#0040CC] px-4 py-2 rounded-lg"
          data-testid="public-nav-signup">
          Start free trial
        </button>
      </div>
    </div>
  </header>
);

export default PublicSiteHeader;
