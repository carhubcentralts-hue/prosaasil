import React from 'react';
import { cn } from '../../utils/cn';

interface CardProps {
  className?: string;
  children: React.ReactNode;
  hover?: boolean;
}

export function Card({ className, children, hover = false }: CardProps) {
  return (
    <div 
      className={cn(
        'card',
        hover && 'card-hover',
        className
      )}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number | React.ReactNode;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: string;
  className?: string;
}

export function StatCard({ title, value, subtitle, icon, trend, className }: StatCardProps) {
  return (
    <Card className={cn('p-6', className)} hover>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-slate-500 mb-1">{title}</p>
          <p className="text-3xl md:text-4xl font-semibold tabular-nums mb-2">
            {value}
          </p>
          {subtitle && (
            <p className="text-sm text-slate-500">{subtitle}</p>
          )}
          {trend && (
            <div className="mt-2">
              <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs bg-green-50 text-green-700 ring-1 ring-green-200">
                ▲ {trend}
              </span>
            </div>
          )}
        </div>
        {icon && (
          <div className="text-slate-400">
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
}

export function Badge({ children, variant = 'neutral', className }: BadgeProps) {
  const variantStyles = {
    success: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    warning: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200', 
    danger: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    neutral: 'bg-slate-100 text-slate-700 ring-1 ring-slate-300'
  };

  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs',
      variantStyles[variant],
      className
    )}>
      {children}
    </span>
  );
}