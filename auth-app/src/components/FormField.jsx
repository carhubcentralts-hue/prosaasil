import { useState, forwardRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// Input עם focus ring ואנימציות
const Input = forwardRef(({ 
  className = '', 
  error = false, 
  icon: Icon,
  rightAction,
  ...props 
}, ref) => {
  const [focused, setFocused] = useState(false)

  return (
    <div className="relative">
      {/* Icon */}
      {Icon && (
        <div className="absolute right-4 top-1/2 transform -translate-y-1/2 text-brand-500 z-10">
          <Icon className="w-5 h-5" />
        </div>
      )}
      
      {/* Input */}
      <motion.input
        ref={ref}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`
          w-full px-4 py-4 text-base
          ${Icon ? 'pr-12' : ''}
          ${rightAction ? 'pl-12' : ''}
          bg-white/80 backdrop-blur-sm
          border-2 transition-all duration-200
          rounded-2xl
          text-brand-800 placeholder-brand-400
          font-heebo font-medium
          focus:outline-none focus:bg-white/95
          min-h-[48px]
          ${error 
            ? 'border-red-400 focus:border-red-500 focus:ring-4 focus:ring-red-100' 
            : focused 
              ? 'border-accent-start focus:ring-4 focus:ring-accent-start/20' 
              : 'border-gray-200 hover:border-brand-300'
          }
          ${className}
        `}
        {...props}
      />
      
      {/* Right action */}
      {rightAction && (
        <div className="absolute left-4 top-1/2 transform -translate-y-1/2 z-10">
          {rightAction}
        </div>
      )}
    </div>
  )
})

Input.displayName = 'Input'

// FormField עם ולידציה inline לפי NN/g
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
      className={`space-y-3 ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Label */}
      {label && (
        <label className="block text-base font-semibold text-brand-700 text-right">
          {label}
          {required && <span className="text-red-500 mr-2 text-lg">*</span>}
        </label>
      )}
      
      {children}
      
      {/* Error message - inline צמוד לשדה */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0, y: -10 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={{ opacity: 0, height: 0, y: -10 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="text-right"
          >
            <div className="flex items-center gap-2 text-red-600">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <p className="text-sm font-medium">{error}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// PasswordInput עם הצג/הסתר
const PasswordInput = forwardRef(({ error, ...props }, ref) => {
  const [showPassword, setShowPassword] = useState(false)

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
        <motion.button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          whileTap={{ scale: 0.95 }}
          className="text-brand-500 hover:text-brand-700 transition-colors p-1 rounded-lg hover:bg-brand-50 min-w-[44px] min-h-[44px] flex items-center justify-center"
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
        </motion.button>
      }
      {...props}
    />
  )
})

PasswordInput.displayName = 'PasswordInput'

export { FormField, Input, PasswordInput }