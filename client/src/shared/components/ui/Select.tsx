import { ReactNode, SelectHTMLAttributes } from 'react';
import { cn } from '../../utils/cn';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  children: ReactNode;
  className?: string;
  'data-testid'?: string;
}

interface SelectOptionProps {
  value: string;
  children: ReactNode;
  disabled?: boolean;
}

export function Select({ children, className = '', ...props }: SelectProps) {
  return (
    <select
      className={cn(
        'flex h-9 w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 dark:placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50 text-right',
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function SelectOption({ value, children, disabled = false }: SelectOptionProps) {
  return (
    <option value={value} disabled={disabled}>
      {children}
    </option>
  );
}