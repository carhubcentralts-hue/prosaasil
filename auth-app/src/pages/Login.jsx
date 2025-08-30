import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, Input, PasswordInput } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'

const Login = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const { showError, showSuccess } = useToast()

  // ולידציה לפי NN/g - לא מוקדם מדי, inline, ברורה
  const validateField = (name, value) => {
    switch (name) {
      case 'email':
        if (!value) return 'נדרש למלא שדה זה'
        if (!value.includes('@') || !value.includes('.')) return 'כתובת אימייל לא חוקית'
        return ''
      case 'password':
        if (!value) return 'נדרש למלא שדה זה'
        if (value.length < 6) return 'הסיסמה חייבת להכיל לפחות 6 תווים'
        return ''
      default:
        return ''
    }
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    const fieldValue = type === 'checkbox' ? checked : value
    
    setFormData(prev => ({ ...prev, [name]: fieldValue }))
    
    // Clear error on change - מיידי אחרי תיקון
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }))
    }
  }

  // ולידציה רק onBlur - לא מוקדם מדי
  const handleBlur = (e) => {
    const { name, value } = e.target
    const error = validateField(name, value)
    setErrors(prev => ({ ...prev, [name]: error }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    // Validate all fields
    const newErrors = {}
    Object.keys(formData).forEach(key => {
      if (key !== 'remember') {
        const error = validateField(key, formData[key])
        if (error) newErrors[key] = error
      }
    })

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setLoading(true)

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      // Success
      showSuccess('התחברת בהצלחה! מעביר לדשבורד...')
      
      // Save remember me
      if (formData.remember) {
        localStorage.setItem('remembered_email', formData.email)
      } else {
        localStorage.removeItem('remembered_email')
      }

      // Navigate based on role - אינטגרציה לדשבורדים הקיימים
      setTimeout(() => {
        // כאן נקבע את ה-role לפי הלוגיקה הקיימת
        window.location.href = '/app/admin' // או /app/biz לפי role
      }, 1000)

    } catch (error) {
      showError('שגיאה בהתחברות - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass-card rounded-3xl p-8 space-y-8 shadow-2xl">
      {/* Header - היררכיה ברורה */}
      <motion.div 
        className="text-center space-y-3"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        <h1 className="text-4xl font-bold text-brand-800 animate-stagger-1">
          התחברות למערכת
        </h1>
        <p className="text-lg text-brand-600 animate-stagger-2">
          הכנס אימייל וסיסמה כדי להמשיך
        </p>
      </motion.div>

      {/* Form */}
      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        {/* Email Field */}
        <motion.div
          className="animate-stagger-3"
          style={{ animationFillMode: 'both' }}
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
              value={formData.email}
              onChange={handleChange}
              onBlur={handleBlur}
              error={!!errors.email}
              icon={() => (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
              )}
              autoComplete="email"
            />
          </FormField>
        </motion.div>

        {/* Password Field */}
        <motion.div
          className="animate-stagger-4"
          style={{ animationFillMode: 'both' }}
        >
          <FormField
            label="סיסמה"
            error={errors.password}
            required
          >
            <PasswordInput
              name="password"
              placeholder="הזן סיסמה"
              value={formData.password}
              onChange={handleChange}
              onBlur={handleBlur}
              error={!!errors.password}
              autoComplete="current-password"
            />
          </FormField>
        </motion.div>

        {/* Options Row */}
        <motion.div 
          className="flex items-center justify-between pt-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.8 }}
        >
          <Link
            to="/forgot"
            className="text-base text-accent-start hover:text-accent-middle transition-colors font-medium hover:underline"
          >
            שכחתי סיסמה
          </Link>
          
          <label className="flex items-center gap-3 cursor-pointer">
            <span className="text-base text-brand-700 font-medium">זכור אותי</span>
            <motion.input
              type="checkbox"
              name="remember"
              checked={formData.remember}
              onChange={handleChange}
              whileTap={{ scale: 0.9 }}
              className="w-5 h-5 text-accent-start rounded border-2 border-brand-300 focus:ring-4 focus:ring-accent-start/20 transition-all"
            />
          </label>
        </motion.div>

        {/* Submit Button - CTA גרדיאנט */}
        <motion.div
          className="pt-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 1.0 }}
        >
          <Button
            type="submit"
            loading={loading}
            disabled={loading || !formData.email || !formData.password}
            className="w-full"
          >
            התחבר למערכת
          </Button>
        </motion.div>
      </motion.form>
    </div>
  )
}

export default Login