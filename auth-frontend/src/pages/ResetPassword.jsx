import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Lock, Eye, EyeOff, ArrowRight, Check, X } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import AuthLayout from '../components/Layout';

const resetSchema = z.object({
  password: z.string().min(8, 'הסיסמה חייבת להכיל לפחות 8 תווים'),
  confirmPassword: z.string().min(8, 'אימות הסיסמה חייב')
}).refine((data) => data.password === data.confirmPassword, {
  message: "הסיסמאות אינן תואמות",
  path: ["confirmPassword"]
});

const PasswordStrengthIndicator = ({ password }) => {
  const requirements = [
    { text: 'לפחות 8 תווים', met: password.length >= 8 },
    { text: 'כולל אות גדולה', met: /[A-Z]/.test(password) },
    { text: 'כולל אות קטנה', met: /[a-z]/.test(password) },
    { text: 'כולל מספר', met: /\d/.test(password) }
  ];

  return (
    <div className="space-y-2 p-3 bg-gray-50 rounded-xl" data-testid="password-strength">
      <p className="text-sm font-medium text-gray-700 text-right">חוזק הסיסמה:</p>
      <div className="space-y-1">
        {requirements.map((req, index) => (
          <div key={index} className="flex items-center justify-end gap-2 text-sm">
            <span className={req.met ? 'text-green-600' : 'text-gray-400'}>
              {req.text}
            </span>
            {req.met ? (
              <Check size={16} className="text-green-600" />
            ) : (
              <X size={16} className="text-gray-300" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const PasswordField = ({ placeholder, error, register, name, showStrength = false, watch }) => {
  const [showPassword, setShowPassword] = useState(false);
  const password = watch && watch(name);
  
  return (
    <div className="space-y-3">
      <div className="relative">
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400">
          <Lock size={20} />
        </div>
        <input
          type={showPassword ? 'text' : 'password'}
          className={`input-field pr-12 pl-12 ${error ? 'ring-red-500 border-red-500' : ''}`}
          placeholder={placeholder}
          data-testid={`input-${name}`}
          {...register(name)}
        />
        <button
          type="button"
          className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
          onClick={() => setShowPassword(!showPassword)}
          data-testid={`button-toggle-${name}`}
        >
          {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
        </button>
      </div>
      
      {showStrength && password && password.length > 0 && (
        <PasswordStrengthIndicator password={password} />
      )}
      
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

const ResetPassword = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [token, setToken] = useState('');
  const [isValidToken, setIsValidToken] = useState(null);
  
  const { register, handleSubmit, formState: { errors }, watch } = useForm({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      password: '',
      confirmPassword: ''
    }
  });

  useEffect(() => {
    // Extract token from URL
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');
    
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
      validateToken(tokenFromUrl);
    } else {
      setIsValidToken(false);
    }
  }, []);

  const validateToken = async (tokenToValidate) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/auth/validate-reset-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: tokenToValidate }),
      });

      setIsValidToken(response.ok);
    } catch (error) {
      setIsValidToken(false);
    }
  };

  const showToast = (message, type = 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const onSubmit = async (data) => {
    setIsLoading(true);
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          token,
          password: data.password
        }),
      });

      const result = await response.json();

      if (response.ok) {
        showToast('הסיסמה עודכנה בהצלחה!', 'success');
        
        // Redirect to login after success
        setTimeout(() => {
          window.location.href = '/auth/login';
        }, 2000);
      } else {
        showToast(result.message || 'שגיאה באיפוס הסיסמה');
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

  if (isValidToken === null) {
    return (
      <AuthLayout>
        <div className="text-center py-8">
          <div className="w-8 h-8 border-2 border-accent-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600" data-testid="text-validating">מאמת קישור...</p>
        </div>
      </AuthLayout>
    );
  }

  if (isValidToken === false) {
    return (
      <AuthLayout>
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-6 text-center"
        >
          <motion.div variants={itemVariants}>
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <X className="w-8 h-8 text-red-600" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2" data-testid="heading-invalid">
              קישור לא תקין
            </h2>
            <p className="text-gray-600 mb-6" data-testid="text-invalid-message">
              הקישור לאיפוס הסיסמה אינו תקין או שפג תוקפו.
            </p>
          </motion.div>

          <motion.div variants={itemVariants}>
            <a
              href="/auth/forgot"
              className="inline-flex items-center gap-2 text-accent-600 hover:text-accent-700 transition-colors"
              data-testid="link-request-new"
            >
              <span>בקש קישור חדש</span>
              <ArrowRight size={18} />
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
          <h2 className="text-3xl font-bold text-gray-900 mb-2" data-testid="heading-reset">
            איפוס סיסמה
          </h2>
          <p className="text-gray-600" data-testid="text-reset-instructions">
            הזן סיסמה חדשה לחשבון שלך
          </p>
        </motion.div>

        <motion.form 
          variants={itemVariants}
          onSubmit={handleSubmit(onSubmit)} 
          className="space-y-6"
          noValidate
        >
          <PasswordField
            placeholder="סיסמה חדשה"
            error={errors.password}
            register={register}
            name="password"
            showStrength={true}
            watch={watch}
          />

          <PasswordField
            placeholder="אימות סיסמה"
            error={errors.confirmPassword}
            register={register}
            name="confirmPassword"
          />

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
                <span>עדכן סיסמה</span>
                <ArrowRight size={18} />
              </>
            )}
          </motion.button>
        </motion.form>

        <motion.div variants={itemVariants} className="text-center pt-4">
          <a
            href="/auth/login"
            className="text-sm text-gray-600 hover:text-gray-800 transition-colors"
            data-testid="link-back-to-login"
          >
            חזרה להתחברות
          </a>
        </motion.div>
      </motion.div>
    </AuthLayout>
  );
};

export default ResetPassword;