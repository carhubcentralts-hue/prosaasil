import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, Input, PasswordInput } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'

// Mock users for demo
const MOCK_USERS = {
  'admin@shai.co.il': { password: 'admin123', role: 'admin', name: 'מנהל המערכת' },
  'business@shai.co.il': { password: 'business123', role: 'business', name: 'משתמש עסקי' }
}

const Login = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const { showError, showSuccess } = useToast()
  const navigate = useNavigate()

  // Real-time validation
  const validateField = (name, value) => {
    switch (name) {
      case 'email':
        if (!value) return 'שדה זה הוא חובה'
        if (!value.includes('@') || !value.includes('.')) return 'כתובת אימייל לא תקינה'
        return ''
      case 'password':
        if (!value) return 'שדה זה הוא חובה'
        if (value.length < 8) return 'הסיסמה חייבת להכיל לפחות 8 תווים'
        return ''
      default:
        return ''
    }
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    const fieldValue = type === 'checkbox' ? checked : value
    
    setFormData(prev => ({ ...prev, [name]: fieldValue }))
    
    // Clear error on change
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }))
    }
  }

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
      
      const user = MOCK_USERS[formData.email]
      
      if (!user || user.password !== formData.password) {
        showError('כתובת אימייל או סיסמה שגויים')
        return
      }

      // Success
      showSuccess(`ברוך הבא, ${user.name}!`)
      
      // Save to localStorage if remember me is checked
      if (formData.remember) {
        localStorage.setItem('remembered_email', formData.email)
      } else {
        localStorage.removeItem('remembered_email')
      }

      // Navigate based on role
      setTimeout(() => {
        if (user.role === 'admin' || user.role === 'superadmin') {
          window.location.href = '/app/admin'
        } else {
          window.location.href = '/app/biz'
        }
      }, 1000)

    } catch (error) {
      showError('שגיאת רשת - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
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
        <h1 className="text-3xl font-bold text-brand-800">התחברות למערכת</h1>
        <p className="text-brand-600">הכנס את פרטי ההתחברות שלך</p>
      </motion.div>

      {/* Form */}
      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-4"
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
              data-testid="email-input"
            />
          </FormField>
        </motion.div>

        {/* Password Field */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
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
              data-testid="password-input"
            />
          </FormField>
        </motion.div>

        {/* Options Row */}
        <motion.div 
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          <Link
            to="/forgot"
            className="text-sm text-brand-600 hover:text-brand-700 transition-colors font-medium"
            data-testid="forgot-password-link"
          >
            שכחתי סיסמה
          </Link>
          
          <label className="flex items-center gap-2 cursor-pointer" data-testid="remember-checkbox">
            <span className="text-sm text-brand-700">זכור אותי</span>
            <input
              type="checkbox"
              name="remember"
              checked={formData.remember}
              onChange={handleChange}
              className="w-4 h-4 text-brand-600 rounded border-brand-300 focus:ring-brand-500"
            />
          </label>
        </motion.div>

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
        >
          <Button
            type="submit"
            loading={loading}
            disabled={loading}
            className="w-full"
            icon={() => (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            )}
            data-testid="login-submit"
          >
            התחבר למערכת
          </Button>
        </motion.div>
      </motion.form>

      {/* Footer */}
      <motion.div
        className="text-center pt-4 border-t border-brand-200/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.7 }}
      >
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 transition-colors"
          onClick={(e) => {
            e.preventDefault()
            showSuccess('עמוד הבית יזמין בקרוב')
          }}
          data-testid="home-link"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>חזרה לדף הבית</span>
        </Link>
      </motion.div>

      {/* Demo users info */}
      <motion.div
        className="text-center pt-2 space-y-1"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.8 }}
      >
        <p className="text-xs text-brand-500">משתמשי דמו לבדיקה:</p>
        <p className="text-xs text-brand-400">admin@shai.co.il / admin123</p>
        <p className="text-xs text-brand-400">business@shai.co.il / business123</p>
      </motion.div>
    </div>
  )
}

export default Login