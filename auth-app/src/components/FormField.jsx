import { useState, forwardRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const Input = forwardRef(({ 
  className = '', 
  error = false, 
  ...props 
}, ref) => {
  return (
    <input
      ref={ref}
      className={`
        w-full px-4 py-3 
        bg-white/80 backdrop-blur-sm
        border border-gray-200
        rounded-xl
        text-gray-900 placeholder-gray-500
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
        transition-all duration-200
        font-heebo
        ${error ? 'border-red-300 focus:ring-red-500' : ''}
        ${className}
      `}
      {...props}
    />
  )
})

Input.displayName = 'Input'

const FormField = ({ 
  label, 
  error, 
  children, 
  required = false,
  className = '',
  ...props 
}) => {
  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label className="block text-sm font-semibold text-gray-700 text-right">
          {label}
          {required && <span className="text-red-500 mr-1">*</span>}
        </label>
      )}
      
      {children}
      
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="text-right"
          >
            <p className="text-sm text-red-600 font-medium">
              {error}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const PasswordInput = forwardRef(({ error, ...props }, ref) => {
  const [showPassword, setShowPassword] = useState(false)

  return (
    <div className="relative">
      <Input
        ref={ref}
        type={showPassword ? 'text' : 'password'}
        error={error}
        className="pl-12"
        {...props}
      />
      
      <button
        type="button"
        onClick={() => setShowPassword(!showPassword)}
        className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
        aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
      >
        {showPassword ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L12 12m7.5-7.5L12 12" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        )}
      </button>
    </div>
  )
})

PasswordInput.displayName = 'PasswordInput'

export { FormField, Input, PasswordInput }