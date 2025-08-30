/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  // Tailwind 4.1 - רוב הקונפיגורציה עברה ל-@theme ב-CSS
  theme: {
    extend: {
      // רק דברים שלא ניתן לעשות ב-@theme
      fontFamily: {
        'heebo': ['Heebo', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}