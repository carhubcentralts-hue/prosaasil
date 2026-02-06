import React from 'react'; // ✅ Classic JSX runtime
import { cn } from '../utils/cn';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'default' | 'secondary' | 'outline';
  size?: 'sm' | 'md';
  children: React.ReactNode;
}

export function Badge({ 
  variant = 'neutral', 
  size = 'md', 
  className, 
  children, 
  ...props 
}: BadgeProps) {
  const baseStyles = 'inline-flex items-center font-medium rounded-full';
  
  const variants: Record<string, string> = {
    success: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    warning: 'bg-yellow-100 text-yellow-800',
    info: 'bg-blue-100 text-blue-800',
    neutral: 'bg-gray-100 text-gray-800',
    default: 'bg-gray-100 text-gray-800',
    secondary: 'bg-slate-100 text-slate-700',
    outline: 'border border-gray-300 text-gray-700 bg-transparent',
  };
  
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  };

  return (
    <span
      className={cn(
        baseStyles,
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}