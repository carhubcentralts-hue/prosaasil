import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, Input } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'

const ForgotPassword = () => {
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const { showError, showSuccess } = useToast()

  const validateEmail = (value) => {
    if (!value) return 'שדה זה הוא חובה'
    if (!value.includes('@') || !value.includes('.')) return 'כתובת אימייל לא תקינה'
    return ''
  }

  const handleChange = (e) => {
    setEmail(e.target.value)
    if (errors.email) {
      setErrors(prev => ({ ...prev, email: '' }))
    }
  }

  const handleBlur = (e) => {
    const error = validateEmail(e.target.value)
    setErrors(prev => ({ ...prev, email: error }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    const error = validateEmail(email)
    if (error) {
      setErrors({ email: error })
      return
    }

    setLoading(true)

    try {
      // Simulate API call - always returns success for security
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Always show success message (security best practice)
      setSent(true)
      showSuccess('אם האימייל קיים במערכת, נשלח אליך קישור לאיפוס סיסמה')
      
    } catch (error) {
      showError('שגיאת רשת - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <motion.div 
        className="glass-card rounded-3xl p-8 space-y-6 text-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        {/* Success Icon */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.5, delay: 0.2, type: "spring" }}
          className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center"
        >
          <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </motion.div>

        {/* Success Message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="space-y-4"
        >
          <h1 className="text-2xl font-bold text-brand-800">נשלח בהצלחה!</h1>
          <p className="text-brand-600 leading-relaxed">
            אם האימייל <span className="font-medium">{email}</span> קיים במערכת שלנו,
            <br />
            נשלח אליך קישור לאיפוס סיסמה תוך מספר דקות.
          </p>
          <p className="text-sm text-brand-500">
            אנא בדוק גם את תיקיית הספאם
          </p>
        </motion.div>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="space-y-3"
        >
          <Link to="/" className="block">
            <Button variant="primary" className="w-full">
              חזרה להתחברות
            </Button>
          </Link>
          
          <button
            onClick={() => {
              setSent(false)
              setEmail('')
            }}
            className="w-full text-sm text-brand-600 hover:text-brand-700 transition-colors"
          >
            שלח שוב לכתובת אחרת
          </button>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <div className="glass-card rounded-3xl p-8 space-y-6">
      {/* Header */}
      <motion.div 
        className="text-center space-y-2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold text-brand-800">שכחתי סיסמה</h1>
        <p className="text-brand-600">הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס</p>
      </motion.div>

      {/* Form */}
      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        {/* Email Field */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <FormField
            label="כתובת אימייל"
            error={errors.email}
            required
          >
            <Input
              type="email"
              name="email"
              dir="ltr"
              placeholder="user@example.com"
              value={email}
              onChange={handleChange}
              onBlur={handleBlur}
              error={!!errors.email}
              icon={() => (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
              )}
              autoComplete="email"
              data-testid="forgot-email-input"
            />
          </FormField>
        </motion.div>

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          <Button
            type="submit"
            loading={loading}
            disabled={loading}
            className="w-full"
            icon={() => (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
            data-testid="forgot-submit"
          >
            שלח קישור איפוס
          </Button>
        </motion.div>
      </motion.form>

      {/* Footer */}
      <motion.div
        className="text-center pt-4 border-t border-brand-200/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.5 }}
      >
        <p className="text-sm text-brand-600 mb-3">
          זכרת את הסיסמה?
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 transition-colors font-medium"
          data-testid="back-to-login"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span>חזרה להתחברות</span>
        </Link>
      </motion.div>
    </div>
  )
}

export default ForgotPassword