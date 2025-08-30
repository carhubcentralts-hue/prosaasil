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
        // Brand colors - כהה לטקסט וכפתור ראשי
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155', // כהה לטקסט
          800: '#1e293b', // כהה יותר לכפתור ראשי
          900: '#0f172a',
          950: '#020617'
        },
        // Accent - גרדיאנט סגול→טורקיז
        accent: {
          start: '#8b5cf6', // סגול
          middle: '#06b6d4', // טורקיז
          end: '#0891b2'    // טורקיז כהה
        },
        // Glass מיוחד
        glass: {
          light: 'rgba(255, 255, 255, 0.8)',
          medium: 'rgba(255, 255, 255, 0.9)',
          border: 'rgba(255, 255, 255, 0.2)'
        }
      },
      backdropBlur: {
        'glass': '20px'
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'stagger-1': 'fadeIn 0.6s ease-out 0.1s both',
        'stagger-2': 'fadeIn 0.6s ease-out 0.2s both',
        'stagger-3': 'fadeIn 0.6s ease-out 0.3s both',
        'stagger-4': 'fadeIn 0.6s ease-out 0.4s both',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        }
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.2)',
        'glass-lg': '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
        'brand': '0 10px 25px -5px rgba(139, 92, 246, 0.3)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      }
    },
  },
  plugins: [],
}