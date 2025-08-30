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

  const validateField = (name, value) => {
    switch (name) {
      case 'email':
        if (!value) return 'שדה זה הוא חובה'
        if (!value.includes('@') || !value.includes('.')) return 'כתובת אימייל לא תקינה'
        return ''
      case 'password':
        if (!value) return 'שדה זה הוא חובה'
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
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      // Real authentication would happen here
      showSuccess('התחברת בהצלחה')
      
      if (formData.remember) {
        localStorage.setItem('remembered_email', formData.email)
      } else {
        localStorage.removeItem('remembered_email')
      }

      setTimeout(() => {
        window.location.href = '/app/admin'
      }, 1000)

    } catch (error) {
      showError('שגיאה בהתחברות - אנא נסה שוב')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="glass-card rounded-3xl p-8 space-y-6">
      <motion.div 
        className="text-center space-y-2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold text-brand-800">התחברות למערכת</h1>
        <p className="text-brand-600">הכנס את פרטי ההתחברות שלך</p>
      </motion.div>

      <motion.form 
        onSubmit={handleSubmit}
        className="space-y-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
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
            autoComplete="email"
          />
        </FormField>

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

        <div className="flex items-center justify-between">
          <Link
            to="/forgot"
            className="text-sm text-brand-600 hover:text-brand-700 transition-colors font-medium"
          >
            שכחתי סיסמה
          </Link>
          
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-brand-700">זכור אותי</span>
            <input
              type="checkbox"
              name="remember"
              checked={formData.remember}
              onChange={handleChange}
              className="w-4 h-4 text-brand-600 rounded border-brand-300 focus:ring-brand-500"
            />
          </label>
        </div>

        <Button
          type="submit"
          loading={loading}
          disabled={loading}
          className="w-full"
        >
          התחבר למערכת
        </Button>
      </motion.form>
    </div>
  )
}

export default Login