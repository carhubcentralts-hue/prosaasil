import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, Input } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'

const ForgotPassword = () => {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const { showError, showSuccess } = useToast()

  const validateEmail = (email) => {
    if (!email) return 'נדרש למלא שדה זה'
    if (!email.includes('@') || !email.includes('.')) return 'כתובת אימייל לא חוקית'
    return ''
  }

  const handleChange = (e) => {
    setEmail(e.target.value)
    if (error) setError('')
  }

  const handleBlur = (e) => {
    const emailError = validateEmail(e.target.value)
    setError(emailError)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    const emailError = validateEmail(email)
    if (emailError) {
      setError(emailError)
      return
    }

    setLoading(true)
    setError('')

    try {
      await new Promise(resolve => setTimeout(resolve, 2000))
      setSent(true)
      showSuccess('נשלח קישור לאיפוס סיסמה לכתובת המייל שלך')
    } catch (error) {
      showError('שגיאה בשליחת המייל - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <motion.div 
        className="bg-white/95 backdrop-blur-xl rounded-3xl p-10 space-y-8 shadow-2xl border border-white/20 text-center"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        {/* Success Icon */}
        <motion.div
          className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.5, delay: 0.2, type: "spring", stiffness: 150 }}
        >
          <svg className="w-10 h-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </motion.div>

        <motion.div
          className="space-y-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
        >
          <h1 className="text-4xl font-bold text-slate-800">
            הקישור נשלח!
          </h1>
          <p className="text-xl text-slate-600 leading-relaxed">
            שלחנו לך קישור לאיפוס סיסמה לכתובת:
          </p>
          <p className="text-lg font-bold text-purple-600 dir-ltr" dir="ltr">
            {email}
          </p>
        </motion.div>

        <motion.div
          className="space-y-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
        >
          <p className="text-base text-slate-500">
            בדוק את תיבת הדוא״ל שלך ולחץ על הקישור כדי לאפס את הסיסמה
          </p>
          
          <div className="flex gap-4 justify-center pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setSent(false)
                setEmail('')
              }}
            >
              שלח שוב
            </Button>
            <Link to="/login">
              <Button>
                חזור להתחברות
              </Button>
            </Link>
          </div>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <div className="bg-white/95 backdrop-blur-xl rounded-3xl p-10 space-y-8 shadow-2xl border border-white/20">
      {/* Header */}
      <motion.div 
        className="text-center space-y-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        <motion.div
          className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto"
          initial={{ scale: 0, rotate: -90 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ duration: 0.6, delay: 0.1, type: "spring", stiffness: 100 }}
        >
          <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </motion.div>

        <motion.h1 
          className="text-4xl font-bold text-slate-800"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          שכחתי סיסמה
        </motion.h1>
        
        <motion.p 
          className="text-xl text-slate-600 font-medium leading-relaxed"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס הסיסמה
        </motion.p>
      </motion.div>

      {/* Form */}
      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.4 }}
      >
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <FormField
            label="כתובת אימייל"
            error={error}
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
              error={!!error}
              icon={() => (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
              )}
              autoComplete="email"
              autoFocus
            />
          </FormField>
        </motion.div>

        {/* Submit Button */}
        <motion.div
          className="pt-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
        >
          <Button
            type="submit"
            loading={loading}
            disabled={loading || !email}
            className="w-full"
          >
            שלח קישור לאיפוס
          </Button>
        </motion.div>
      </motion.form>

      {/* Back to Login */}
      <motion.div 
        className="text-center pt-4 border-t border-slate-200"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.7 }}
      >
        <p className="text-base text-slate-600">
          זכרת את הסיסמה?{' '}
          <Link
            to="/login"
            className="text-purple-600 hover:text-purple-700 font-semibold hover:underline transition-colors"
          >
            חזור להתחברות
          </Link>
        </p>
      </motion.div>
    </div>
  )
}

export default ForgotPassword