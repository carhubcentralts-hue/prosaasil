import React from 'react'; // ✅ Classic JSX runtime
import { ReactNode } from 'react';
import { cn } from '../../utils/cn';

interface TableProps {
  children: ReactNode;
  className?: string;
  'data-testid'?: string;
}

interface TableHeaderProps {
  children: ReactNode;
  className?: string;
}

interface TableBodyProps {
  children: ReactNode;
  className?: string;
}

interface TableRowProps {
  children: ReactNode;
  className?: string;
  'data-testid'?: string;
  onClick?: () => void;
}

interface TableHeadProps {
  children: ReactNode;
  className?: string;
  sortable?: boolean;
  onClick?: () => void;
}

interface TableCellProps {
  children: ReactNode;
  className?: string;
  'data-testid'?: string;
}

export function Table({ children, className = '', ...props }: TableProps) {
  return (
    <div className="w-full overflow-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table 
        className={cn('w-full table-fixed border-collapse bg-white dark:bg-gray-900', className)} 
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ children, className = '' }: TableHeaderProps) {
  return (
    <thead className={cn('bg-gray-50 dark:bg-gray-800', className)}>
      {children}
    </thead>
  );
}

export function TableBody({ children, className = '' }: TableBodyProps) {
  return (
    <tbody className={cn('divide-y divide-gray-200 dark:divide-gray-700', className)}>
      {children}
    </tbody>
  );
}

export function TableRow({ children, className = '', onClick, ...props }: TableRowProps) {
  return (
    <tr 
      className={cn(
        'transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      {...props}
    >
      {children}
    </tr>
  );
}

export function TableHead({ children, className = '', sortable = false, onClick }: TableHeadProps) {
  return (
    <th
      className={cn(
        'px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider',
        sortable && 'cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none',
        className
      )}
      onClick={sortable ? onClick : undefined}
    >
      <div className="flex items-center justify-end gap-1">
        {children}
      </div>
    </th>
  );
}

export function TableCell({ children, className = '', ...props }: TableCellProps) {
  return (
    <td 
      className={cn('px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right', className)}
      {...props}
    >
      {children}
    </td>
  );
}