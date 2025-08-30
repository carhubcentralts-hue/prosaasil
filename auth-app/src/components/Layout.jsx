import { motion } from 'framer-motion'

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-blue-50 to-blue-100 font-heebo" dir="rtl">
      <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2">
        {/* Brand Panel */}
        <motion.div 
          className="hidden lg:flex flex-col justify-center p-12 bg-gradient-to-br from-blue-600 to-blue-800 text-white"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
        >
          <div className="max-w-md mx-auto text-center">
            <div className="w-16 h-16 mx-auto mb-8 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-2xl font-bold text-white">שי</span>
            </div>

            <h1 className="text-4xl font-bold mb-6">
              שי דירות ומשרדים
            </h1>
            
            <p className="text-xl text-blue-100 mb-8 leading-relaxed">
              מערכת CRM מתקדמת לניהול קריאות בעברית עם בינה מלאכותית
            </p>
            
            <div className="space-y-3 text-right">
              <div className="flex items-center justify-end gap-2">
                <span className="text-blue-100">תיעוד אוטומטי של שיחות</span>
                <div className="w-2 h-2 bg-blue-300 rounded-full" />
              </div>
              <div className="flex items-center justify-end gap-2">
                <span className="text-blue-100">ניתוח בינה מלאכותית</span>
                <div className="w-2 h-2 bg-blue-300 rounded-full" />
              </div>
              <div className="flex items-center justify-end gap-2">
                <span className="text-blue-100">ניהול לקוחות מתקדם</span>
                <div className="w-2 h-2 bg-blue-300 rounded-full" />
              </div>
            </div>
          </div>
        </motion.div>
        
        {/* Auth Panel */}
        <div className="flex flex-col justify-center p-8">
          <div className="w-full max-w-md mx-auto">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Layout