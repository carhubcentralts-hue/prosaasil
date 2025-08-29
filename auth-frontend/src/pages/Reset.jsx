import React, { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { Lock, Eye, EyeOff, ArrowLeft, CheckCircle } from 'lucide-react'
import { api } from '../lib/api'

function Reset() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: ''
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState('')
  const [passwordMatch, setPasswordMatch] = useState(true)

  useEffect(() => {
    if (!token) {
      setError('קישור איפוס לא תקין')
    }
  }, [token])

  useEffect(() => {
    if (formData.confirmPassword) {
      setPasswordMatch(formData.password === formData.confirmPassword)
    }
  }, [formData.password, formData.confirmPassword])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!formData.password || !formData.confirmPassword) {
      setError('נא למלא את כל השדות')
      return
    }

    if (formData.password.length < 8) {
      setError('הסיסמה חייבת להכיל לפחות 8 תווים')
      return
    }

    if (formData.password !== formData.confirmPassword) {
      setError('הסיסמאות אינן תואמות')
      return
    }

    setIsLoading(true)

    try {
      await api.reset(token, formData.password)
      setIsSuccess(true)
      
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login')
      }, 3000)
    } catch (err) {
      setError(err.message || 'שגיאה באיפוס הסיסמה')
    } finally {
      setIsLoading(false)
    }
  }

  if (isSuccess) {
    return (
      <div className="w-full max-w-md mx-auto">
        <motion.div
          className="glass rounded-3xl shadow-2xl p-8 backdrop-blur-xl border border-white/20 text-center"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <motion.div
            className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
          >
            <CheckCircle className="w-8 h-8 text-green-600" />
          </motion.div>
          
          <h2 className="text-2xl font-bold text-brand-900 mb-4">
            הסיסמה עודכנה!
          </h2>
          
          <p className="text-brand-500 mb-6">
            הסיסמה שלך עודכנה בהצלחה. אתה מועבר לדף ההתחברות...
          </p>
          
          <Link
            to="/login"
            className="inline-flex items-center text-accent-500 hover:text-accent-600 transition-colors"
          >
            <ArrowLeft size={16} className="ml-1" />
            התחבר עכשיו
          </Link>
        </motion.div>
      </div>
    )
  }

  if (!token) {
    return (
      <div className="w-full max-w-md mx-auto">
        <div className="glass rounded-3xl shadow-2xl p-8 backdrop-blur-xl border border-white/20 text-center">
          <h2 className="text-2xl font-bold text-brand-900 mb-4">
            קישור לא תקין
          </h2>
          <p className="text-brand-500 mb-6">
            קישור איפוס הסיסמה אינו תקין או פג תוקפו
          </p>
          <Link
            to="/forgot"
            className="inline-flex items-center text-accent-500 hover:text-accent-600 transition-colors"
          >
            <ArrowLeft size={16} className="ml-1" />
            בקש קישור חדש
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <motion.div
        className="glass rounded-3xl shadow-2xl p-8 backdrop-blur-xl border border-white/20"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-brand-900 mb-2">
            הגדרת סיסמה חדשה
          </h1>
          <p className="text-brand-500">
            הזן סיסמה חדשה לחשבון שלך
          </p>
        </div>

        {error && (
          <motion.div
            className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-200 mb-6"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            role="alert"
            aria-live="polite"
          >
            {error}
          </motion.div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Password Field */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-brand-900 mb-2">
              סיסמה חדשה
            </label>
            <div className="relative">
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-brand-500">
                <Lock size={20} />
              </div>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="new-password"
                className="w-full min-h-[44px] pl-12 pr-12 py-3 rounded-xl border border-gray-200 focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 transition-colors bg-white/50 backdrop-blur-sm"
                placeholder="הזן סיסמה חדשה (לפחות 8 תווים)"
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

          {/* Confirm Password Field */}
          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-brand-900 mb-2">
              אישור סיסמה
            </label>
            <div className="relative">
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-brand-500">
                <Lock size={20} />
              </div>
              <input
                id="confirmPassword"
                type={showConfirmPassword ? 'text' : 'password'}
                required
                autoComplete="new-password"
                className={`w-full min-h-[44px] pl-12 pr-12 py-3 rounded-xl border transition-colors bg-white/50 backdrop-blur-sm ${
                  formData.confirmPassword && !passwordMatch 
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
                    : 'border-gray-200 focus:border-accent-500 focus:ring-accent-500/20'
                }`}
                placeholder="הזן את הסיסמה שוב"
                value={formData.confirmPassword}
                onChange={(e) => setFormData(prev => ({ ...prev, confirmPassword: e.target.value }))}
              />
              <button
                type="button"
                className="absolute left-3 top-1/2 transform -translate-y-1/2 text-brand-500 hover:text-brand-700 transition-colors"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
              >
                {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
            {formData.confirmPassword && !passwordMatch && (
              <p className="text-red-600 text-sm mt-1">הסיסמאות אינן תואמות</p>
            )}
          </div>

          <motion.button
            type="submit"
            disabled={isLoading || !passwordMatch}
            className="w-full min-h-[44px] btn-primary text-white font-semibold py-3 px-4 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isLoading ? 'מעדכן...' : 'עדכן סיסמה'}
          </motion.button>
        </form>

        <div className="mt-6 pt-6 border-t border-gray-200/50 text-center">
          <Link
            to="/login"
            className="inline-flex items-center text-sm text-brand-500 hover:text-brand-700 transition-colors"
          >
            <ArrowLeft size={16} className="ml-1" />
            חזור להתחברות
          </Link>
        </div>
      </motion.div>
    </div>
  )
}

export default Reset