import { useState, forwardRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// Base input component with glass morphism
const Input = forwardRef(({ 
  className = '', 
  error = false, 
  icon: Icon, 
  rightAction,
  ...props 
}, ref) => {
  return (
    <div className="relative">
      {/* Icon */}
      {Icon && (
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-brand-400 pointer-events-none z-10">
          <Icon className="w-5 h-5" />
        </div>
      )}
      
      {/* Input */}
      <input
        ref={ref}
        className={`
          w-full px-4 py-3 
          ${Icon ? 'pr-12' : ''}
          ${rightAction ? 'pl-12' : ''}
          bg-white/70 backdrop-blur-sm
          border border-brand-200/50
          rounded-2xl
          text-brand-900 placeholder-brand-400
          focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
          transition-all duration-200
          font-heebo
          ${error ? 'border-red-300 focus:ring-red-500' : ''}
          ${className}
        `}
        {...props}
      />
      
      {/* Right action (e.g., password toggle) */}
      {rightAction && (
        <div className="absolute left-3 top-1/2 transform -translate-y-1/2 z-10">
          {rightAction}
        </div>
      )}
    </div>
  )
})

Input.displayName = 'Input'

// Form field with label and error message
const FormField = ({ 
  label, 
  error, 
  children, 
  required = false,
  className = '',
  ...props 
}) => {
  return (
    <motion.div 
      className={`space-y-2 ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Label */}
      {label && (
        <label className="block text-sm font-semibold text-brand-700 text-right">
          {label}
          {required && <span className="text-red-500 mr-1">*</span>}
        </label>
      )}
      
      {/* Input field */}
      {children}
      
      {/* Error message */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="text-right"
          >
            <p className="text-sm text-red-600 font-medium" role="alert">
              {error}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// Password input with toggle visibility
const PasswordInput = forwardRef(({ error, ...props }, ref) => {
  const [showPassword, setShowPassword] = useState(false)

  const togglePassword = () => setShowPassword(!showPassword)

  return (
    <Input
      ref={ref}
      type={showPassword ? 'text' : 'password'}
      error={error}
      icon={() => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      )}
      rightAction={
        <button
          type="button"
          onClick={togglePassword}
          className="text-brand-400 hover:text-brand-600 transition-colors p-1"
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
      }
      {...props}
    />
  )
})

PasswordInput.displayName = 'PasswordInput'

export { FormField, Input, PasswordInput }