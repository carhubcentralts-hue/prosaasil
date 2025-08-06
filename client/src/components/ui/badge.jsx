import React from 'react';

export const Badge = ({ 
  children, 
  variant = 'default',
  size = 'default',
  className = '', 
  ...props 
}) => {
  const baseClasses = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2';
  
  const variants = {
    default: 'bg-blue-100 text-blue-800 border border-blue-200',
    secondary: 'bg-gray-100 text-gray-800 border border-gray-200',
    success: 'bg-green-100 text-green-800 border border-green-200',
    destructive: 'bg-red-100 text-red-800 border border-red-200',
    warning: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
    outline: 'text-gray-600 border border-gray-300'
  };
  
  const sizes = {
    sm: 'px-1.5 py-0.5 text-xs',
    default: 'px-2.5 py-0.5 text-xs',
    lg: 'px-3 py-1 text-sm'
  };

  const classes = [
    baseClasses,
    variants[variant] || variants.default,
    sizes[size] || sizes.default,
    className
  ].join(' ');

  return (
    <span className={classes} {...props}>
      {children}
    </span>
  );
};