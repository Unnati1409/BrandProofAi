/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontSize: {
        '2xs': ['11px', { lineHeight: '14px' }],
        'xs': ['12px', { lineHeight: '16px' }],
        'sm': ['13px', { lineHeight: '18px' }],
        'base': ['14px', { lineHeight: '20px' }],
        'md': ['16px', { lineHeight: '24px' }],
        'lg': ['20px', { lineHeight: '28px' }],
        'xl': ['24px', { lineHeight: '32px' }],
        '2xl': ['30px', { lineHeight: '38px' }],
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      colors: {
        // Restrained neutral palette
        surface: {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
          950: '#020617',
        },
        // ONE deliberate accent for focus & primary buttons
        brand: {
          50: '#F0F9FF',
          100: '#E0F2FE',
          500: '#0284C7',
          600: '#0369A1',
          700: '#075985',
          800: '#0C4A6E',
          900: '#0F172A', // Slate/Navy authority
        },
        // Separate semantic status tokens (never rely on color alone)
        severity: {
          low: '#D97706',      // Amber 600
          medium: '#EA580C',   // Orange 600
          high: '#DC2626',     // Red 600
        },
        verdict: {
          supported: '#16A34A',      // Green 600
          contradicted: '#DC2626',   // Red 600
          unsupported: '#CA8A04',    // Yellow 600
          needs_review: '#4F46E5',   // Indigo 600
        },
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '3px',
        md: '6px',
        lg: '8px',
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        popover: '0 4px 12px 0 rgba(0, 0, 0, 0.08), 0 1px 3px 0 rgba(0, 0, 0, 0.04)',
      },
      transitionDuration: {
        DEFAULT: '150ms',
      },
    },
  },
  plugins: [],
}
