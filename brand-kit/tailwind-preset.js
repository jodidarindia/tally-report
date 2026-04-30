/**
 * @flowra/brand-kit — Tailwind preset
 *
 * Usage in any FLOWRA app's tailwind.config.js:
 *
 *   module.exports = {
 *     presets: [require('@flowra/brand-kit/tailwind-preset')],
 *     content: ['./src/**\/*.{js,jsx,ts,tsx,html}'],
 *   };
 */

module.exports = {
  theme: {
    extend: {
      colors: {
        flowra: {
          // Brand
          primary:  '#2563EB',
          'primary-dark':  '#1D4ED8',
          'primary-light': '#DBEAFE',
          accent:   '#7C3AED',
          success:  '#10B981',
          warning:  '#F59E0B',
          danger:   '#EF4444',

          // Light surface
          bg:        '#FFFFFF',
          'bg-subtle': '#F8FAFC',
          'bg-muted':  '#F1F5F9',
          border:      '#E2E8F0',
          'border-strong': '#CBD5E1',
          text:        '#0F172A',
          'text-muted':'#475569',
          'text-subtle':'#94A3B8',

          // Dark surface (marketing landing, premium dashboards)
          'dark-bg':    '#0A0E1A',
          'dark-bg-2':  '#0F1729',
          'dark-bg-3':  '#1A2238',
          'dark-border':'#1E293B',
          'dark-text':  '#E2E8F0',
          'dark-text-muted':'#94A3B8',
        },
      },
      fontFamily: {
        sans:    ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', '"Courier New"', 'monospace'],
      },
      borderRadius: {
        'flowra': '0.625rem',
        'flowra-lg': '1rem',
        'flowra-xl': '1.5rem',
      },
      boxShadow: {
        'flowra':       '0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 2px 6px -2px rgba(15, 23, 42, 0.04)',
        'flowra-lg':    '0 24px 48px -12px rgba(15, 23, 42, 0.18)',
        'glow-blue':    '0 0 40px rgba(37, 99, 235, 0.4)',
        'glow-violet':  '0 0 40px rgba(124, 58, 237, 0.35)',
      },
      transitionTimingFunction: {
        'flowra': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      animation: {
        'flowra-rise':  'flowra-rise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both',
        'flowra-fade':  'flowra-fade 0.4s ease both',
        'flowra-shine': 'flowra-shine 2.5s ease-in-out infinite',
      },
      keyframes: {
        'flowra-rise': {
          '0%':   { opacity: 0, transform: 'translateY(16px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'flowra-fade': {
          '0%':   { opacity: 0 },
          '100%': { opacity: 1 },
        },
        'flowra-shine': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%':      { backgroundPosition: '100% 50%' },
        },
      },
    },
  },
  plugins: [],
};
