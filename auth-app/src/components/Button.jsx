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
      bg-gradient-primary
      text-white font-bold
      hover:scale-105 hover:shadow-purple
      shadow-lg hover:shadow-xl
      border-0
      focus:ring-4 focus:ring-purple-500/30
      disabled:opacity-60 disabled:cursor-not-allowed
      disabled:hover:scale-100 disabled:hover:shadow-lg
    `,
    secondary: `
      bg-white/90 backdrop-blur-sm
      text-brand-700 font-semibold
      border-2 border-brand-200
      hover:bg-white hover:border-purple-300 hover:scale-105
      shadow-lg hover:shadow-xl
      focus:ring-4 focus:ring-purple-500/20
    `
  }

  const isDisabled = disabled || loading

  return (
    <motion.button
      ref={ref}
      whileHover={!isDisabled ? { scale: 1.02 } : {}}
      whileTap={!isDisabled ? { scale: 0.98 } : {}}
      transition={{ duration: 0.2, type: "spring", stiffness: 300 }}
      disabled={isDisabled}
      className={`
        relative inline-flex items-center justify-center gap-3
        rounded-2xl px-8 py-4 text-lg
        transition-all duration-300 ease-out
        focus:outline-none
        min-h-[56px] min-w-[140px]
        font-heebo
        ${variants[variant]}
        ${className}
      `}
      {...props}
    >
      {/* Loading spinner מקצועי */}
      {loading && (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-6 h-6 border-3 border-current border-t-transparent rounded-full"
          style={{ borderWidth: '3px' }}
          aria-hidden="true"
        />
      )}
      
      {/* Button content */}
      <motion.span 
        className={loading ? 'opacity-0' : 'opacity-100'}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.span>
      
      {/* Loading text */}
      {loading && (
        <motion.span 
          className="absolute inset-0 flex items-center justify-center font-bold"
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