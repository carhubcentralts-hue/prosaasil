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
      bg-gradient-to-l from-accent-start to-accent-middle
      text-white font-semibold
      hover:from-accent-middle hover:to-accent-end
      shadow-2xl hover:shadow-brand
      focus:ring-4 focus:ring-accent-start/30
      disabled:from-gray-400 disabled:to-gray-500
    `,
    secondary: `
      bg-white/80 backdrop-blur-sm
      text-brand-700 font-semibold
      border-2 border-brand-200
      hover:bg-white/95 hover:border-brand-300
      focus:ring-4 focus:ring-brand-200
      shadow-lg hover:shadow-xl
    `
  }

  const isDisabled = disabled || loading

  return (
    <motion.button
      ref={ref}
      whileHover={!isDisabled ? { scale: 1.02, y: -2 } : {}}
      whileTap={!isDisabled ? { scale: 0.98 } : {}}
      transition={{ duration: 0.2, ease: "easeOut" }}
      disabled={isDisabled}
      className={`
        relative inline-flex items-center justify-center gap-3
        rounded-2xl px-8 py-4 text-base
        transition-all duration-200
        focus:outline-none
        disabled:opacity-60 disabled:cursor-not-allowed
        min-h-[56px] min-w-[120px]
        font-heebo
        ${variants[variant]}
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
      
      {/* Button content */}
      <span className={loading ? 'opacity-0' : 'transition-opacity duration-200'}>
        {children}
      </span>
      
      {/* Loading text overlay */}
      {loading && (
        <motion.span 
          className="absolute inset-0 flex items-center justify-center font-medium"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          מתחבר...
        </motion.span>
      )}
    </motion.button>
  )
})

Button.displayName = 'Button'

export default Button