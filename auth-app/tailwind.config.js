/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'heebo': ['Heebo', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Brand colors עדכני
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617'
        },
        // Accent - סגול טורקיז
        purple: {
          400: '#a855f7',
          500: '#9333ea',
          600: '#7c3aed'
        },
        cyan: {
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2'
        }
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #9333ea 0%, #06b6d4 100%)',
        'gradient-secondary': 'linear-gradient(135deg, #a855f7 0%, #22d3ee 100%)',
        'gradient-brand': 'linear-gradient(135deg, #334155 0%, #1e293b 50%, #0f172a 100%)'
      },
      backdropBlur: {
        'glass': '20px'
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'float': 'float 20s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        float: {
          '0%, 100%': { transform: 'translate(0px, 0px) rotate(0deg)' },
          '33%': { transform: 'translate(30px, -30px) rotate(1deg)' },
          '66%': { transform: 'translate(-20px, 20px) rotate(-1deg)' }
        }
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.2)',
        'glass-lg': '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
        'purple': '0 10px 25px -5px rgba(147, 51, 234, 0.3)',
        'cyan': '0 10px 25px -5px rgba(6, 182, 212, 0.3)',
      }
    },
  },
  plugins: [],
}