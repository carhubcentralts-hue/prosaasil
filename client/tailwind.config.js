export default {
  content: ["./index.html","./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem'
      },
      colors: { 
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9', 
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a'
        }, 
        accent: {
          50: '#eef2ff',
          100: '#e0e7ff',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca'
        }
      },
      boxShadow: { 
        'soft': '0 8px 28px rgba(0,0,0,.08)',
        'glass': '0 8px 32px rgba(31, 38, 135, 0.37)',
        'elegant': '0 20px 60px rgba(0,0,0,.1)',
        'button': '0 4px 14px 0 rgba(99, 102, 241, 0.3)'
      },
      backgroundImage: {
        'gradient-elegant': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'gradient-card': 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)'
      },
      backdropBlur: {
        'xs': '2px'
      }
    }
  },
  plugins:[]
}