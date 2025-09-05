import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '../utils/cn';

interface SidebarItemProps {
  to?: string;
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}

export function SidebarItem({ 
  to, 
  icon, 
  label, 
  isActive, 
  onClick, 
  disabled = false 
}: SidebarItemProps) {
  const location = useLocation();
  const active = isActive ?? (to ? location.pathname === to : false);
  
  const baseStyles = cn(
    'flex items-center px-4 py-3 text-sm font-medium transition-colors rounded-xl',
    'hover:bg-gray-100 hover:text-gray-900',
    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
    active && 'bg-blue-50 text-blue-700 border-r-4 border-blue-600',
    disabled && 'opacity-50 cursor-not-allowed'
  );

  const content = (
    <>
      <span className="ml-3 flex-shrink-0">{icon}</span>
      <span className="mr-3 flex-1">{label}</span>
    </>
  );

  if (!to) {
    return (
      <button
        className={baseStyles}
        onClick={onClick}
        data-testid={`sidebar-${label.toLowerCase().replace(/\s+/g, '-')}`}
      >
        {content}
      </button>
    );
  }

  return (
    <Link
      to={to}
      className={baseStyles}
      data-testid={`sidebar-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {content}
    </Link>
  );
}