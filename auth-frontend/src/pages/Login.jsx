import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { Eye, EyeOff, Mail, Lock, ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'

function Login() {
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    // Basic validation
    if (!formData.email || !formData.password) {
      setError('נא למלא את כל השדות')
      setIsLoading(false)
      return
    }

    if (formData.password.length < 8) {
      setError('הסיסמה חייבת להכיל לפחות 8 תווים')
      setIsLoading(false)
      return
    }

    try {
      const response = await api.login(formData.email, formData.password)
      
      // Route based on user role
      if (response.user?.role === 'admin' || response.user?.role === 'superadmin') {
        window.location.href = '/app/admin'
      } else {
        window.location.href = '/app/biz'
      }
    } catch (err) {
      setError(err.message || 'שגיאה בהתחברות')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="w-full max-w-6xl mx-auto">
      <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center min-h-[600px]">
        
        {/* Brand Panel - Desktop Only */}
        <motion.div
          className="hidden lg:block"
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <div className="space-y-8">
            {/* Logo */}
            <motion.div
              className="text-6xl font-bold text-brand-900"
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.5, delay: 0.4 }}
            >
              שי
            </motion.div>
            
            {/* Company Name */}
            <div>
              <h1 className="text-4xl font-bold text-brand-900 mb-2">
                שי דירות ומשרדים
              </h1>
              <p className="text-xl text-brand-500">
                פתרונות נדל"ן מתקדמים
              </p>
            </div>

            {/* Benefits */}
            <motion.div
              className="space-y-6"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.6 }}
            >
              <div className="flex items-center space-x-4 space-x-reverse">
                <div className="w-12 h-12 bg-gradient-to-br from-accent-500 to-accent-400 rounded-xl flex items-center justify-center">
                  <span className="text-white text-xl">🏠</span>
                </div>
                <div>
                  <h3 className="font-semibold text-brand-900">ניהול נכסים מתקדם</h3>
                  <p className="text-brand-500">מערכת CRM חכמה לניהול לקוחות ונכסים</p>
                </div>
              </div>

              <div className="flex items-center space-x-4 space-x-reverse">
                <div className="w-12 h-12 bg-gradient-to-br from-accent-500 to-accent-400 rounded-xl flex items-center justify-center">
                  <span className="text-white text-xl">🤖</span>
                </div>
                <div>
                  <h3 className="font-semibold text-brand-900">בינה מלאכותית</h3>
                  <p className="text-brand-500">מזכירה חכמה לטיפול בפניות לקוחות</p>
                </div>
              </div>

              <div className="flex items-center space-x-4 space-x-reverse">
                <div className="w-12 h-12 bg-gradient-to-br from-accent-500 to-accent-400 rounded-xl flex items-center justify-center">
                  <span className="text-white text-xl">📊</span>
                </div>
                <div>
                  <h3 className="font-semibold text-brand-900">דוחות ואנליטיקה</h3>
                  <p className="text-brand-500">מעקב וניתוח ביצועים בזמן אמת</p>
                </div>
              </div>
            </motion.div>
          </div>
        </motion.div>

        {/* Login Form */}
        <motion.div
          className="w-full"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="glass rounded-3xl shadow-2xl p-8 lg:p-10 backdrop-blur-xl border border-white/20">
            
            {/* Mobile Logo */}
            <div className="lg:hidden text-center mb-8">
              <div className="text-4xl font-bold text-brand-900 mb-2">שי</div>
              <h1 className="text-2xl font-bold text-brand-900">שי דירות ומשרדים</h1>
              <p className="text-brand-500">פתרונות נדל"ן מתקדמים</p>
            </div>

            <div className="space-y-6">
              <div className="text-center lg:text-right">
                <h2 className="text-2xl lg:text-3xl font-bold text-brand-900 mb-2">
                  התחבר למערכת
                </h2>
                <p className="text-brand-500">
                  הכנס את פרטיך כדי לגשת לחשבון שלך
                </p>
              </div>

              {error && (
                <motion.div
                  className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-200"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  role="alert"
                  aria-live="polite"
                >
                  {error}
                </motion.div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email Field */}
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-brand-900 mb-2">
                    כתובת אימייל
                  </label>
                  <div className="relative">
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-brand-500">
                      <Mail size={20} />
                    </div>
                    <input
                      id="email"
                      type="email"
                      required
                      autoComplete="email"
                      dir="ltr"
                      className="w-full min-h-[44px] pl-4 pr-12 py-3 rounded-xl border border-gray-200 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 transition-colors bg-white/50 backdrop-blur-sm"
                      placeholder="name@example.com"
                      value={formData.email}
                      onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    />
                  </div>
                </div>

                {/* Password Field */}
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-brand-900 mb-2">
                    סיסמה
                  </label>
                  <div className="relative">
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-brand-500">
                      <Lock size={20} />
                    </div>
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="current-password"
                      className="w-full min-h-[44px] pl-12 pr-12 py-3 rounded-xl border border-gray-200 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 transition-colors bg-white/50 backdrop-blur-sm"
                      placeholder="הזן סיסמה"
                      value={formData.password}
                      onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                    />
                    <button
                      type="button"
                      className="absolute left-3 top-1/2 transform -translate-y-1/2 text-brand-500 hover:text-brand-700 transition-colors"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
                    >
                      {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                    </button>
                  </div>
                </div>

                {/* Remember Me */}
                <div className="flex items-center justify-between">
                  <label className="flex items-center space-x-2 space-x-reverse">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300 text-accent-500 focus:ring-accent-500"
                      checked={formData.remember}
                      onChange={(e) => setFormData(prev => ({ ...prev, remember: e.target.checked }))}
                    />
                    <span className="text-sm text-brand-700">זכור אותי</span>
                  </label>
                  
                  <Link
                    to="/forgot"
                    className="text-sm text-accent-500 hover:text-accent-600 transition-colors"
                  >
                    שכחתי סיסמה
                  </Link>
                </div>

                {/* Submit Button */}
                <motion.button
                  type="submit"
                  disabled={isLoading}
                  className="w-full min-h-[44px] btn-primary text-white font-semibold py-3 px-4 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {isLoading ? 'מתחבר...' : 'התחבר'}
                </motion.button>
              </form>

              {/* Footer Links */}
              <div className="pt-6 border-t border-gray-200/50 text-center space-y-2">
                <Link
                  to="/"
                  className="inline-flex items-center text-sm text-brand-500 hover:text-brand-700 transition-colors"
                >
                  <ArrowLeft size={16} className="ml-1" />
                  חזור לדף הבית
                </Link>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default Login