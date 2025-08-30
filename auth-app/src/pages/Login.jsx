import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FormField, Input, PasswordInput } from '@/components/FormField'
import Button from '@/components/Button'
import { useToast } from '@/components/Toast'
import { useAuth } from '@/contexts/AuthContext'

const Login = () => {
  const navigate = useNavigate()
  const { login, user, loading: authLoading } = useAuth()
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const { showError, showSuccess } = useToast()

  // Redirect if already authenticated
  useEffect(() => {
    if (user && !authLoading) {
      const redirectPath = user.role === 'superadmin' || user.role === 'admin' 
        ? '/app/admin/overview' 
        : '/app/biz/overview'
      navigate(redirectPath, { replace: true })
    }
  }, [user, authLoading, navigate])

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
      const result = await login(formData.email, formData.password)
      
      if (result.success) {
        showSuccess('התחברת בהצלחה! מעביר אותך למערכת...')
        
        if (formData.remember) {
          localStorage.setItem('remembered_email', formData.email)
        } else {
          localStorage.removeItem('remembered_email')
        }
      } else {
        showError(result.error || 'שגיאה בהתחברות')
      }

    } catch (error) {
      showError('שגיאה בהתחברות - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
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
        <motion.h1 
          className="text-5xl font-bold text-slate-800"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          התחברות למערכת
        </motion.h1>
        <motion.p 
          className="text-xl text-slate-600 font-medium"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          הכנס אימייל וסיסמה כדי להמשיך
        </motion.p>
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
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
              )}
              autoComplete="email"
            />
          </FormField>
        </motion.div>

        {/* Password Field */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
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

        {/* Options */}
        <motion.div 
          className="flex items-center justify-between pt-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
        >
          <Link
            to="/forgot"
            className="text-lg text-purple-600 hover:text-purple-700 transition-colors font-semibold hover:underline"
          >
            שכחתי סיסמה
          </Link>
          
          <label className="flex items-center gap-3 cursor-pointer group">
            <span className="text-lg text-slate-700 font-semibold">זכור אותי</span>
            <motion.input
              type="checkbox"
              name="remember"
              checked={formData.remember}
              onChange={handleChange}
              whileTap={{ scale: 0.9 }}
              className="w-6 h-6 text-purple-600 rounded-lg border-2 border-slate-300 focus:ring-4 focus:ring-purple-100 transition-all group-hover:border-purple-400"
            />
          </label>
        </motion.div>

        {/* Submit Button */}
        <motion.div
          className="pt-6"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.7 }}
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