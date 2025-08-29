import { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, ArrowRight, ArrowLeft } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import AuthLayout from '../components/Layout';

const forgotSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה')
});

const Toast = ({ message, type, onClose }) => (
  <motion.div
    className={`fixed top-4 right-4 p-4 rounded-2xl shadow-lg z-50 ${
      type === 'error' ? 'bg-red-500 text-white' : 'bg-green-500 text-white'
    }`}
    initial={{ opacity: 0, x: 100 }}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: 100 }}
    data-testid={`toast-${type}`}
  >
    <div className="flex items-center justify-between gap-3">
      <span>{message}</span>
      <button onClick={onClose} className="text-white/80 hover:text-white">
        ×
      </button>
    </div>
  </motion.div>
);

const ForgotPassword = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(forgotSchema),
    defaultValues: {
      email: ''
    }
  });

  const showToast = (message, type = 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const onSubmit = async (data) => {
    setIsLoading(true);
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/auth/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(data),
      });

      // Always show success message for security
      setIsSubmitted(true);
      showToast('אם האימייל קיים במערכת, נשלח אליך קישור לאיפוס הסיסמה', 'success');
      
    } catch (error) {
      showToast('שגיאת רשת - אנא נסה שוב');
    } finally {
      setIsLoading(false);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        duration: 0.3
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  if (isSubmitted) {
    return (
      <AuthLayout>
        {toast && <Toast {...toast} onClose={() => setToast(null)} />}
        
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-6 text-center"
        >
          <motion.div variants={itemVariants}>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2" data-testid="heading-success">
              אימייל נשלח
            </h2>
            <p className="text-gray-600 mb-6" data-testid="text-success-message">
              אם האימייל קיים במערכת, נשלח אליך קישור לאיפוס הסיסמה בדקות הקרובות.
            </p>
          </motion.div>

          <motion.div variants={itemVariants}>
            <a
              href="/auth/login"
              className="inline-flex items-center gap-2 text-accent-600 hover:text-accent-700 transition-colors"
              data-testid="link-back-to-login"
            >
              <ArrowLeft size={18} />
              <span>חזרה להתחברות</span>
            </a>
          </motion.div>
        </motion.div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
      
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={itemVariants} className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-2" data-testid="heading-forgot">
            שכחתי סיסמה
          </h2>
          <p className="text-gray-600" data-testid="text-instructions">
            הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס הסיסמה
          </p>
        </motion.div>

        <motion.form 
          variants={itemVariants}
          onSubmit={handleSubmit(onSubmit)} 
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <div className="relative">
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                <Mail size={20} />
              </div>
              <input
                type="email"
                dir="ltr"
                autoComplete="email"
                className={`input-field pr-12 ${errors.email ? 'ring-red-500 border-red-500' : ''}`}
                placeholder="כתובת אימייל"
                data-testid="input-email"
                {...register('email')}
              />
            </div>
            {errors.email && (
              <motion.p
                className="text-sm text-red-500 text-right"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                role="alert"
                aria-live="polite"
                data-testid="error-email"
              >
                {errors.email.message}
              </motion.p>
            )}
          </div>

          <motion.button
            variants={itemVariants}
            type="submit"
            disabled={isLoading}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            data-testid="button-submit"
            whileTap={{ scale: 0.98 }}
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>שלח קישור איפוס</span>
                <ArrowRight size={18} />
              </>
            )}
          </motion.button>
        </motion.form>

        <motion.div variants={itemVariants} className="text-center pt-4">
          <a
            href="/auth/login"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            data-testid="link-back-to-login"
          >
            <ArrowLeft size={16} />
            <span>חזרה להתחברות</span>
          </a>
        </motion.div>
      </motion.div>
    </AuthLayout>
  );
};

export default ForgotPassword;