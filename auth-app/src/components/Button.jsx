import { motion } from 'framer-motion'
import { forwardRef } from 'react'

const Button = forwardRef(({ 
  children, 
  variant = 'primary', 
  size = 'md',
  loading = false,
  disabled = false,
  icon: Icon,
  className = '',
  ...props 
}, ref) => {
  const variants = {
    primary: `
      bg-gradient-to-l from-brand-500 to-brand-600 
      text-white 
      hover:from-brand-600 hover:to-brand-700 
      shadow-brand
      hover:shadow-brand-lg
      focus:ring-brand-500
    `,
    secondary: `
      bg-white/70 backdrop-blur-sm
      text-brand-700 
      border border-brand-200
      hover:bg-white/90 
      hover:border-brand-300
      focus:ring-brand-500
    `,
    ghost: `
      bg-transparent 
      text-brand-600 
      hover:bg-brand-50 
      hover:text-brand-700
      focus:ring-brand-500
    `
  }

  const sizes = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base', 
    lg: 'px-8 py-4 text-lg'
  }

  const isDisabled = disabled || loading

  return (
    <motion.button
      ref={ref}
      whileHover={!isDisabled ? { scale: 1.02 } : {}}
      whileTap={!isDisabled ? { scale: 0.98 } : {}}
      transition={{ duration: 0.15 }}
      disabled={isDisabled}
      className={`
        relative inline-flex items-center justify-center gap-2
        font-semibold rounded-2xl
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-offset-2
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variants[variant]}
        ${sizes[size]}
        ${className}
      `}
      {...props}
    >
      {/* Loading spinner */}
      {loading && (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-5 h-5 border-2 border-current border-t-transparent rounded-full"
          aria-hidden="true"
        />
      )}
      
      {/* Icon */}
      {!loading && Icon && <Icon className="w-5 h-5" />}
      
      {/* Button text */}
      <span className={loading ? 'opacity-0' : ''}>{children}</span>
      
      {/* Loading text overlay */}
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