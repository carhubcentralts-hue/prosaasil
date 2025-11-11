import React from 'react'; // ✅ Classic JSX runtime
import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '../../utils/cn';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export function Input({ 
  label, 
  error, 
  helperText, 
  className, 
  type,
  ...props 
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === 'password';
  const actualType = isPassword && showPassword ? 'text' : type;

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-slate-700 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          type={actualType}
          className={cn(
            'w-full rounded-xl border px-4 py-3 text-base transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-[var(--ring)]',
            'placeholder:text-slate-400',
            error 
              ? 'border-[var(--danger)] text-[var(--danger)]' 
              : 'border-slate-300 focus:border-[var(--brand)]',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            className
          )}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${props.id}-error` : helperText ? `${props.id}-help` : undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            onClick={() => setShowPassword(!showPassword)}
            aria-pressed={showPassword}
            aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
          >
            {showPassword ? (
              <EyeOff className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        )}
      </div>
      {error && (
        <p 
          id={`${props.id}-error`}
          className="mt-2 text-sm text-[var(--danger)]"
          role="alert"
        >
          {error}
        </p>
      )}
      {helperText && !error && (
        <p 
          id={`${props.id}-help`}
          className="mt-2 text-sm text-slate-500"
        >
          {helperText}
        </p>
      )}
    </div>
  );
}