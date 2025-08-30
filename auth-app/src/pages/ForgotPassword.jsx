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
      await new Promise(resolve => setTimeout(resolve, 2000))
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
      >
        <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <div className="space-y-4">
          <h1 className="text-2xl font-bold text-gray-800">נשלח בהצלחה!</h1>
          <p className="text-gray-600 leading-relaxed">
            אם האימייל <span className="font-medium">{email}</span> קיים במערכת,
            <br />
            נשלח אליך קישור לאיפוס סיסמה.
          </p>
        </div>

        <Link to="/" className="block">
          <Button variant="primary" className="w-full">
            חזרה להתחברות
          </Button>
        </Link>
      </motion.div>
    )
  }

  return (
    <div className="glass-card rounded-3xl p-8 space-y-6">
      <motion.div 
        className="text-center space-y-2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-3xl font-bold text-gray-800">שכחתי סיסמה</h1>
        <p className="text-gray-600">הזן את כתובת האימייל שלך</p>
      </motion.div>

      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
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
            autoComplete="email"
          />
        </FormField>

        <Button
          type="submit"
          loading={loading}
          disabled={loading}
          className="w-full"
        >
          שלח קישור איפוס
        </Button>
      </motion.form>

      <div className="text-center pt-4 border-t border-gray-200">
        <Link
          to="/"
          className="text-sm text-blue-600 hover:text-blue-700 transition-colors font-medium"
        >
          חזרה להתחברות
        </Link>
      </div>
    </div>
  )
}

export default ForgotPassword