import { motion } from 'framer-motion'

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen font-heebo bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 relative overflow-hidden" dir="rtl">
      {/* רקע אנימציה */}
      <div className="absolute inset-0 animate-float">
        <div className="absolute top-20 left-20 w-64 h-64 bg-purple-400/20 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 right-20 w-48 h-48 bg-cyan-400/15 rounded-full blur-2xl"></div>
        <div className="absolute top-1/2 left-1/2 w-32 h-32 bg-purple-300/10 rounded-full blur-xl transform -translate-x-1/2 -translate-y-1/2"></div>
      </div>
      
      <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 relative z-10">
        {/* Brand Panel */}
        <motion.div 
          className="hidden lg:flex flex-col justify-center p-12 bg-gradient-brand text-white relative overflow-hidden"
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          {/* רקע דקורטיבי */}
          <div className="absolute inset-0">
            <div className="absolute top-20 left-20 w-64 h-64 bg-purple-500/20 rounded-full blur-3xl" />
            <div className="absolute bottom-20 right-20 w-48 h-48 bg-cyan-500/15 rounded-full blur-2xl" />
          </div>
          
          <div className="relative z-10 max-w-md mx-auto text-center">
            {/* לוגו */}
            <motion.div
              className="w-20 h-20 mx-auto mb-8 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center border border-white/20 shadow-2xl"
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.8, delay: 0.3, type: "spring", stiffness: 100 }}
            >
              <span className="text-2xl font-bold text-white">שי</span>
            </motion.div>

            {/* כותרת */}
            <motion.h1 
              className="text-4xl font-bold mb-6 leading-tight"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
            >
              שי דירות ומשרדים
            </motion.h1>
            
            {/* תיאור */}
            <motion.p 
              className="text-xl text-slate-300 mb-12 leading-relaxed"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
            >
              מערכת CRM מתקדמת לניהול קריאות בעברית עם בינה מלאכותית
            </motion.p>
            
            {/* תכונות */}
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
                  <span className="text-slate-300">{feature}</span>
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-lg" />
                </motion.div>
              ))}
            </motion.div>
          </div>
        </motion.div>
        
        {/* Auth Panel */}
        <div className="flex flex-col justify-center p-4 sm:p-6 lg:p-8">
          <motion.div
            className="w-full max-w-md mx-auto"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
          >
            {children}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default Layout