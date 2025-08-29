import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react'
import { api } from '../lib/api'

function Forgot() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    if (!email) {
      setError('נא הזן כתובת אימייל')
      setIsLoading(false)
      return
    }

    try {
      await api.forgot(email)
      setIsSuccess(true)
    } catch (err) {
      setError(err.message || 'שגיאה בשליחת קישור איפוס')
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
            קישור נשלח!
          </h2>
          
          <p className="text-brand-500 mb-6">
            אם כתובת האימייל קיימת במערכת, נשלח אליך קישור לאיפוס סיסמה.
            בדוק את תיבת הדואר שלך (כולל תיקיית הספאם).
          </p>
          
          <Link
            to="/login"
            className="inline-flex items-center text-accent-500 hover:text-accent-600 transition-colors"
          >
            <ArrowLeft size={16} className="ml-1" />
            חזור להתחברות
          </Link>
        </motion.div>
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
            איפוס סיסמה
          </h1>
          <p className="text-brand-500">
            הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס הסיסמה
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
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <motion.button
            type="submit"
            disabled={isLoading}
            className="w-full min-h-[44px] btn-primary text-white font-semibold py-3 px-4 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isLoading ? 'שולח...' : 'שלח קישור איפוס'}
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

export default Forgot