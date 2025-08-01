/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'assistant': ['Assistant', 'Segoe UI', 'Tahoma', 'Geneva', 'Verdana', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe', 
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#0073ea', // Monday.com blue
          700: '#005bb5',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#00c875', // Monday.com green
          600: '#00b96b',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#fdcc0d', // Monday.com orange
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        danger: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#e2445c', // Monday.com red
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        },
        gray: {
          50: '#f8f9fb',
          100: '#f5f6fa',
          200: '#e4e7ec',
          300: '#d0d4e4',
          400: '#9ba3af',
          500: '#676879', // Monday.com text secondary
          600: '#4f5b67',
          700: '#374151',
          800: '#323338', // Monday.com text primary
          900: '#1f2937',
        }
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '100': '25rem',
        '112': '28rem',
        '128': '32rem',
      },
      animation: {
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
        'bounce-slow': 'bounce 2s infinite',
        'pulse-slow': 'pulse 3s infinite',
      },
      keyframes: {
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        }
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'modal': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
      },
      borderRadius: {
        'xl': '0.875rem',
        '2xl': '1.25rem',
        '3xl': '1.875rem',
      }
    },
  },
  plugins: [
    // RTL support plugin
    function({ addUtilities }) {
      const newUtilities = {
        '.rtl': {
          direction: 'rtl',
        },
        '.ltr': {
          direction: 'ltr',
        },
        '.text-start-rtl': {
          'text-align': 'right',
        },
        '.text-end-rtl': {
          'text-align': 'left',
        },
        '.float-start-rtl': {
          'float': 'right',
        },
        '.float-end-rtl': {
          'float': 'left',
        },
        '.mr-auto-rtl': {
          'margin-left': 'auto',
        },
        '.ml-auto-rtl': {
          'margin-right': 'auto',
        },
        '.pr-rtl': {
          'padding-right': '1rem',
        },
        '.pl-rtl': {
          'padding-left': '1rem',
        },
        '.space-x-reverse-rtl > :not([hidden]) ~ :not([hidden])': {
          '--tw-space-x-reverse': '1',
        },
      }
      addUtilities(newUtilities)
    }
  ],
}