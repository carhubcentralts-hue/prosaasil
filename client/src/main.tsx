import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// Simple test app
function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8" dir="rtl">
      <div className="max-w-4xl mx-auto">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 text-white rounded-full mb-4">
            <span className="text-2xl font-bold">ש</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            שי דירות ומשרדים בע״מ
          </h1>
          <p className="text-gray-600">
            מערכת CRM חכמה עם AI לנדל״ן
          </p>
        </div>

        {/* Test Components */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-2">✅ React פועל</h3>
            <p className="text-gray-600 text-sm">React app נטען בהצלחה</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-2">✅ Tailwind פועל</h3>
            <p className="text-gray-600 text-sm">CSS מעוצב נכון</p>
          </div>
          
          <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-2">✅ RTL פועל</h3>
            <p className="text-gray-600 text-sm">כיוון עברית נכון</p>
          </div>
        </div>

        {/* Login Form */}
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-8">
          <h2 className="text-2xl font-bold text-center text-gray-900 mb-6">
            התחברות למערכת
          </h2>
          
          <form className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                כתובת אימייל
              </label>
              <input
                type="email"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="manager@shai-realestate.co.il"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                סיסמה
              </label>
              <input
                type="password"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="הזן סיסמה"
              />
            </div>
            
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              התחבר למערכת
            </button>
          </form>
          
          <div className="mt-4 text-center">
            <button className="text-blue-600 hover:text-blue-800 text-sm">
              שכחת סיסמה?
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)