import { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, PasswordInput } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'

const ResetPassword = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  
  const [formData, setFormData] = useState({
    password: '',
    confirmPassword: ''
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [tokenValid, setTokenValid] = useState(true)
  const { showError, showSuccess } = useToast()

  // Check token validity on mount
  useEffect(() => {
    if (!token) {
      setTokenValid(false)
      showError('קישור לא תקין או פג תוקף')
    }
  }, [token, showError])

  const validateField = (name, value) => {
    switch (name) {
      case 'password':
        if (!value) return 'שדה זה הוא חובה'
        if (value.length < 8) return 'הסיסמה חייבת להכיל לפחות 8 תווים'
        if (!/(?=.*[a-zA-Z])(?=.*\d)/.test(value)) return 'הסיסמה חייבת להכיל לפחות אות ומספר'
        return ''
      case 'confirmPassword':
        if (!value) return 'שדה זה הוא חובה'
        if (value !== formData.password) return 'הסיסמאות לא תואמות'
        return ''
      default:
        return ''
    }
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
    
    // Clear error on change
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }))
    }
    
    // Real-time password matching validation
    if (name === 'password' && formData.confirmPassword) {
      const confirmError = formData.confirmPassword !== value ? 'הסיסמאות לא תואמות' : ''
      setErrors(prev => ({ ...prev, confirmPassword: confirmError }))
    }
    if (name === 'confirmPassword') {
      const confirmError = value !== formData.password ? 'הסיסמאות לא תואמות' : ''
      setErrors(prev => ({ ...prev, confirmPassword: confirmError }))
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
      const error = validateField(key, formData[key])
      if (error) newErrors[key] = error
    })

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setLoading(true)

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Simulate token validation
      if (Math.random() > 0.8) { // 20% chance of expired token for demo
        showError('הקישור פג תוקף - אנא בקש קישור חדש')
        setTokenValid(false)
        return
      }

      // Success
      showSuccess('הסיסמה שונתה בהצלחה!')
      
      // Redirect to login after success
      setTimeout(() => {
        navigate('/')
      }, 2000)

    } catch (error) {
      showError('שגיאת רשת - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  // Password strength indicator
  const getPasswordStrength = (password) => {
    if (!password) return { level: 0, text: '' }
    
    let score = 0
    if (password.length >= 8) score += 1
    if (/(?=.*[a-z])/.test(password)) score += 1
    if (/(?=.*[A-Z])/.test(password)) score += 1
    if (/(?=.*\d)/.test(password)) score += 1
    if (/(?=.*[!@#$%^&*])/.test(password)) score += 1

    const levels = [
      { level: 0, text: '', color: '' },
      { level: 1, text: 'חלשה', color: 'text-red-500' },
      { level: 2, text: 'בינונית', color: 'text-yellow-500' },
      { level: 3, text: 'חזקה', color: 'text-green-500' },
      { level: 4, text: 'חזקה מאוד', color: 'text-green-600' },
      { level: 5, text: 'מצוינת', color: 'text-green-700' }
    ]

    return levels[score] || levels[0]
  }

  const passwordStrength = getPasswordStrength(formData.password)

  if (!tokenValid) {
    return (
      <motion.div 
        className="glass-card rounded-3xl p-8 space-y-6 text-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        {/* Error Icon */}
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.5, delay: 0.2, type: "spring" }}
          className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center"
        >
          <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </motion.div>

        {/* Error Message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="space-y-4"
        >
          <h1 className="text-2xl font-bold text-brand-800">קישור לא תקין</h1>
          <p className="text-brand-600">
            הקישור לאיפוס סיסמה פג תוקף או אינו תקין.
            <br />
            אנא בקש קישור חדש.
          </p>
        </motion.div>

        {/* Action Button */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
        >
          <Link to="/forgot">
            <Button variant="primary" className="w-full">
              בקש קישור חדש
            </Button>
          </Link>
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
        <h1 className="text-3xl font-bold text-brand-800">איפוס סיסמה</h1>
        <p className="text-brand-600">הזן סיסמה חדשה לחשבון שלך</p>
      </motion.div>

      {/* Form */}
      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        {/* New Password Field */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <FormField
            label="סיסמה חדשה"
            error={errors.password}
            required
          >
            <PasswordInput
              name="password"
              placeholder="הזן סיסמה חדשה"
              value={formData.password}
              onChange={handleChange}
              onBlur={handleBlur}
              error={!!errors.password}
              autoComplete="new-password"
              data-testid="new-password-input"
            />
          </FormField>
          
          {/* Password Strength Indicator */}
          {formData.password && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-2 text-right"
            >
              <div className="flex items-center justify-end gap-2">
                <span className={`text-xs font-medium ${passwordStrength.color}`}>
                  חוזק הסיסמה: {passwordStrength.text}
                </span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map(level => (
                    <div
                      key={level}
                      className={`w-6 h-1 rounded-full ${
                        level <= passwordStrength.level
                          ? passwordStrength.level <= 2 ? 'bg-red-500' : 
                            passwordStrength.level <= 3 ? 'bg-yellow-500' : 'bg-green-500'
                          : 'bg-gray-200'
                      }`}
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </motion.div>

        {/* Confirm Password Field */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          <FormField
            label="אימות סיסמה"
            error={errors.confirmPassword}
            required
          >
            <PasswordInput
              name="confirmPassword"
              placeholder="הזן שוב את הסיסמה החדשה"
              value={formData.confirmPassword}
              onChange={handleChange}
              onBlur={handleBlur}
              error={!!errors.confirmPassword}
              autoComplete="new-password"
              data-testid="confirm-password-input"
            />
          </FormField>
        </motion.div>

        {/* Password Match Indicator */}
        {formData.password && formData.confirmPassword && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="text-right"
          >
            <div className={`text-xs font-medium ${
              formData.password === formData.confirmPassword ? 'text-green-600' : 'text-red-600'
            }`}>
              {formData.password === formData.confirmPassword ? 
                '✓ הסיסמאות תואמות' : 
                '✗ הסיסמאות לא תואמות'
              }
            </div>
          </motion.div>
        )}

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
          className="pt-2"
        >
          <Button
            type="submit"
            loading={loading}
            disabled={loading || formData.password !== formData.confirmPassword}
            className="w-full"
            icon={() => (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            data-testid="reset-submit"
          >
            עדכן סיסמה
          </Button>
        </motion.div>
      </motion.form>

      {/* Footer */}
      <motion.div
        className="text-center pt-4 border-t border-brand-200/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.6 }}
      >
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 transition-colors"
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

export default ResetPassword