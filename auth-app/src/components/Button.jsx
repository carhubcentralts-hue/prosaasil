import { motion } from 'framer-motion'
import { forwardRef } from 'react'

const Button = forwardRef(({ 
  children, 
  variant = 'primary', 
  loading = false,
  disabled = false,
  className = '',
  ...props 
}, ref) => {
  const variants = {
    primary: `
      bg-gradient-to-l from-blue-500 to-blue-600 
      text-white 
      hover:from-blue-600 hover:to-blue-700 
      shadow-lg
      hover:shadow-xl
      focus:ring-blue-500
    `,
    secondary: `
      bg-white/70 backdrop-blur-sm
      text-blue-700 
      border border-blue-200
      hover:bg-white/90 
      hover:border-blue-300
      focus:ring-blue-500
    `
  }

  const isDisabled = disabled || loading

  return (
    <motion.button
      ref={ref}
      whileHover={!isDisabled ? { scale: 1.02 } : {}}
      whileTap={!isDisabled ? { scale: 0.98 } : {}}
      disabled={isDisabled}
      className={`
        relative inline-flex items-center justify-center gap-2
        font-semibold rounded-xl px-6 py-3
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-offset-2
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variants[variant]}
        ${className}
      `}
      {...props}
    >
      {loading && (
        <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      )}
      
      <span className={loading ? 'opacity-0' : ''}>{children}</span>
      
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center">
          מתחבר...
        </span>
      )}
    </motion.button>
  )
})

Button.displayName = 'Button'

export default Button