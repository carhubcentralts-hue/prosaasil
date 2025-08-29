import { motion } from 'framer-motion';

const GradientBlob = ({ className, delay = 0 }) => (
  <motion.div
    className={`absolute rounded-full mix-blend-multiply filter blur-3xl opacity-70 ${className}`}
    animate={{
      scale: [1, 1.2, 1],
      rotate: [0, 180, 360],
    }}
    transition={{
      duration: 20,
      repeat: Infinity,
      delay,
      ease: "linear"
    }}
  />
);

const BrandPanel = () => (
  <motion.div
    className="hidden lg:flex lg:flex-1 lg:flex-col lg:justify-center brand-panel"
    initial={{ opacity: 0, x: -50 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.8, delay: 0.2 }}
  >
    <div className="mx-auto max-w-md text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4 }}
      >
        <h1 className="text-4xl font-bold tracking-tight mb-6">
          שי דירות ומשרדים
        </h1>
        <p className="text-xl text-blue-100 mb-8">
          מערכת CRM מתקדמת לניהול קריאות בעברית עם בינה מלאכותית
        </p>
      </motion.div>
      
      <motion.div
        className="space-y-4 text-right"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.6 }}
      >
        <div className="flex items-center justify-end gap-3">
          <span className="text-blue-100">תיעוד אוטומטי של שיחות</span>
          <div className="w-2 h-2 bg-cyan-400 rounded-full"></div>
        </div>
        <div className="flex items-center justify-end gap-3">
          <span className="text-blue-100">ניתוח בינה מלאכותית</span>
          <div className="w-2 h-2 bg-cyan-400 rounded-full"></div>
        </div>
        <div className="flex items-center justify-end gap-3">
          <span className="text-blue-100">ניהול לקוחות מתקדם</span>
          <div className="w-2 h-2 bg-cyan-400 rounded-full"></div>
        </div>
      </motion.div>
    </div>
  </motion.div>
);

const AuthLayout = ({ children }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50 relative overflow-hidden">
      {/* Animated Background Blobs */}
      <GradientBlob
        className="top-0 left-1/4 w-72 h-72 bg-gradient-to-r from-purple-400 to-pink-400"
        delay={0}
      />
      <GradientBlob
        className="top-1/3 right-1/4 w-96 h-96 bg-gradient-to-r from-cyan-400 to-blue-500"
        delay={5}
      />
      <GradientBlob
        className="bottom-1/4 left-1/3 w-80 h-80 bg-gradient-to-r from-indigo-400 to-purple-500"
        delay={10}
      />

      <div className="relative z-10 min-h-screen">
        <div className="lg:grid lg:grid-cols-2 lg:min-h-screen">
          <BrandPanel />
          
          {/* Auth Panel */}
          <div className="flex flex-1 flex-col justify-center px-4 py-12 sm:px-6 lg:px-8">
            <motion.div
              className="mx-auto w-full max-w-md"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <motion.div
                className="glass-card p-8"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.3 }}
              >
                {children}
              </motion.div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;