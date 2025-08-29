import { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, Lock, Eye, EyeOff, ArrowRight, Home } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import AuthLayout from '../components/Layout';

const loginSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה'),
  password: z.string().min(8, 'הסיסמה חייבת להכיל לפחות 8 תווים'),
  remember: z.boolean().optional()
});

const InputField = ({ icon: Icon, type = "text", placeholder, error, register, name, dir = "rtl", autoComplete, ...props }) => {
  const [showPassword, setShowPassword] = useState(false);
  const inputType = type === 'password' && showPassword ? 'text' : type;
  
  return (
    <div className="space-y-2">
      <div className="relative">
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400">
          <Icon size={20} />
        </div>
        <input
          type={inputType}
          dir={dir}
          autoComplete={autoComplete}
          className={`input-field pr-12 ${error ? 'ring-red-500 border-red-500' : ''} ${type === 'password' ? 'pl-12' : ''}`}
          placeholder={placeholder}
          data-testid={`input-${name}`}
          {...register(name)}
          {...props}
        />
        {type === 'password' && (
          <button
            type="button"
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
            onClick={() => setShowPassword(!showPassword)}
            data-testid="button-toggle-password"
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        )}
      </div>
      {error && (
        <motion.p
          className="text-sm text-red-500 text-right"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          role="alert"
          aria-live="polite"
          data-testid={`error-${name}`}
        >
          {error.message}
        </motion.p>
      )}
    </div>
  );
};

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

const Login = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState(null);
  
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
      remember: false
    }
  });

  const showToast = (message, type = 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const onSubmit = async (data) => {
    setIsLoading(true);
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (response.ok) {
        showToast('התחברת בהצלחה!', 'success');
        
        // Route based on user role
        setTimeout(() => {
          if (result.user?.role === 'admin' || result.user?.role === 'superadmin') {
            window.location.href = '/app/admin';
          } else {
            window.location.href = '/app/biz';
          }
        }, 1000);
      } else {
        showToast(result.message || 'שגיאה בהתחברות');
      }
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
          <h2 className="text-3xl font-bold text-gray-900 mb-2" data-testid="heading-login">
            התחברות למערכת
          </h2>
          <p className="text-gray-600" data-testid="text-subtitle">
            הזן את פרטי ההתחברות שלך
          </p>
        </motion.div>

        <motion.form 
          variants={itemVariants}
          onSubmit={handleSubmit(onSubmit)} 
          className="space-y-4"
          noValidate
        >
          <InputField
            icon={Mail}
            type="email"
            placeholder="כתובת אימייל"
            error={errors.email}
            register={register}
            name="email"
            dir="ltr"
            autoComplete="email"
          />

          <InputField
            icon={Lock}
            type="password"
            placeholder="סיסמה"
            error={errors.password}
            register={register}
            name="password"
            autoComplete="current-password"
          />

          <motion.div variants={itemVariants} className="flex items-center justify-between">
            <a
              href="/auth/forgot"
              className="text-sm text-accent-600 hover:text-accent-700 transition-colors"
              data-testid="link-forgot-password"
            >
              שכחתי סיסמה
            </a>
            
            <label className="flex items-center gap-2 cursor-pointer" data-testid="checkbox-remember">
              <span className="text-sm text-gray-600">זכור אותי</span>
              <input
                type="checkbox"
                className="w-4 h-4 text-accent-600 bg-gray-100 border-gray-300 rounded focus:ring-accent-500 focus:ring-2"
                {...register('remember')}
              />
            </label>
          </motion.div>

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
                <span>התחבר</span>
                <ArrowRight size={18} />
              </>
            )}
          </motion.button>
        </motion.form>

        <motion.div variants={itemVariants} className="text-center pt-4">
          <a
            href="/"
            className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            data-testid="link-home"
          >
            <Home size={16} />
            <span>חזרה לדף הבית</span>
          </a>
        </motion.div>
      </motion.div>
    </AuthLayout>
  );
};

export default Login;