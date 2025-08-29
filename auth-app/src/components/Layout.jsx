import { motion } from 'framer-motion'

// Animated background blobs
const AnimatedBlob = ({ className, delay = 0 }) => (
  <motion.div
    className={`absolute rounded-full filter blur-3xl opacity-30 ${className}`}
    animate={{
      x: [0, 30, -20, 0],
      y: [0, -50, 20, 0],
      scale: [1, 1.1, 0.9, 1],
    }}
    transition={{
      duration: 20,
      repeat: Infinity,
      delay,
      ease: "easeInOut"
    }}
  />
)

// Brand panel for desktop  
const BrandPanel = () => (
  <motion.div 
    className="hidden lg:flex flex-col justify-center p-12 bg-gradient-to-br from-brand-600 to-brand-800 text-white relative overflow-hidden"
    initial={{ opacity: 0, x: -50 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.8, ease: "easeOut" }}
  >
    {/* Background decoration */}
    <div className="absolute inset-0 bg-gradient-to-br from-brand-500/20 to-brand-900/20" />
    <div className="absolute top-10 left-10 w-32 h-32 bg-white/10 rounded-full blur-2xl" />
    <div className="absolute bottom-10 right-10 w-24 h-24 bg-brand-300/20 rounded-full blur-xl" />
    
    <div className="relative z-10 max-w-md mx-auto text-center">
      {/* Logo */}
      <motion.div
        className="w-20 h-20 mx-auto mb-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center border border-white/30"
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ duration: 0.8, delay: 0.3, type: "spring" }}
      >
        <span className="text-2xl font-bold text-white">שי</span>
      </motion.div>

      {/* Brand name */}
      <motion.h1 
        className="text-4xl font-bold mb-6 leading-tight"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5 }}
      >
        שי דירות ומשרדים
      </motion.h1>
      
      {/* Description */}
      <motion.p 
        className="text-xl text-brand-100 mb-12 leading-relaxed"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.7 }}
      >
        מערכת CRM מתקדמת לניהול קריאות בעברית עם בינה מלאכותית
      </motion.p>
      
      {/* Features list */}
      <motion.div 
        className="space-y-4 text-right"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.9 }}
      >
        {[
          'תיעוד אוטומטי של שיחות',
          'ניתוח בינה מלאכותית', 
          'ניהול לקוחות מתקדם'
        ].map((feature, index) => (
          <motion.div
            key={feature}
            className="flex items-center justify-end gap-3"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 1.1 + index * 0.1 }}
          >
            <span className="text-brand-100">{feature}</span>
            <motion.div 
              className="w-2 h-2 bg-brand-300 rounded-full"
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity, delay: index * 0.3 }}
            />
          </motion.div>
        ))}
      </motion.div>
    </div>
  </motion.div>
)

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-white relative overflow-hidden font-heebo" dir="rtl">
      {/* Animated background blobs */}
      <AnimatedBlob 
        className="top-0 left-1/4 w-96 h-96 bg-gradient-to-r from-brand-300 to-brand-400" 
        delay={0} 
      />
      <AnimatedBlob 
        className="top-1/3 right-1/4 w-128 h-128 bg-gradient-to-r from-brand-200 to-brand-300" 
        delay={5} 
      />
      <AnimatedBlob 
        className="bottom-1/4 left-1/3 w-80 h-80 bg-gradient-to-r from-brand-400 to-brand-500" 
        delay={10} 
      />

      <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 relative z-10">
        {/* Brand Panel (Desktop Only) */}
        <BrandPanel />
        
        {/* Auth Panel */}
        <div className="flex flex-col justify-center p-4 sm:p-6 lg:p-8">
          <motion.div
            className="w-full max-w-md mx-auto"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          >
            {children}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default Layout