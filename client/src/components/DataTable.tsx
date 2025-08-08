/**
 * DataTable Component with TanStack Table
 * AgentLocator v40 - Professional table implementation
 * Support Hebrew RTL, sorting, filtering, and CSV export
 */

import React, { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type SortingState,
  type ColumnFiltersState,
  type PaginationState,
} from '@tanstack/react-table';
import { 
  ChevronUp, 
  ChevronDown, 
  Search, 
  Download, 
  Settings2,
  Eye,
  EyeOff 
} from 'lucide-react';

interface DataTableProps<T> {
  data: T[];
  columns: any[];
  searchPlaceholder?: string;
  enableSearch?: boolean;
  enableExport?: boolean;
  enableColumnToggle?: boolean;
  title?: string;
  className?: string;
}

export function DataTable<T>({ 
  data, 
  columns, 
  searchPlaceholder = "חיפוש...",
  enableSearch = true,
  enableExport = true,
  enableColumnToggle = true,
  title,
  className = ""
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState([]);
  const [columnFilters, setColumnFilters] = useState([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [columnVisibility, setColumnVisibility] = useState({});
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  });

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
    state: {
      sorting,
      columnFilters,
      globalFilter,
      columnVisibility,
      pagination,
    },
  });

  const exportToCsv = () => {
    const headers = table.getVisibleFlatColumns().map(column => 
      column.columnDef.header as string
    );
    
    const csvData = table.getFilteredRowModel().rows.map(row => 
      table.getVisibleFlatColumns().map(column => {
        const cell = row.getVisibleCells().find(cell => cell.column.id === column.id);
        return cell ? flexRender(column.columnDef.cell, cell.getContext()) : '';
      })
    );

    const csvContent = [
      headers.join(','),
      ...csvData.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${title || 'data'}_export.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 ${className}`} dir="rtl">
      {/* Header Section */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between gap-4">
          {title && (
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {title}
            </h2>
          )}
          
          <div className="flex items-center gap-2">
            {/* Global Search */}
            {enableSearch && (
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <input
                  type="text"
                  placeholder={searchPlaceholder}
                  value={globalFilter ?? ''}
                  onChange={(e) => setGlobalFilter(e.target.value)}
                  className="pr-10 pl-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
              </div>
            )}

            {/* Column Toggle */}
            {enableColumnToggle && (
              <div className="relative group">
                <button className="p-2 border border-gray-300 rounded-md hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700">
                  <Settings2 className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                </button>
                <div className="absolute left-0 mt-2 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-10 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                  <div className="p-2">
                    {table.getAllColumns()
                      .filter(column => column.getCanHide())
                      .map(column => (
                        <label key={column.id} className="flex items-center gap-2 p-1 hover:bg-gray-50 dark:hover:bg-gray-700 rounded text-sm">
                          <input
                            type="checkbox"
                            checked={column.getIsVisible()}
                            onChange={column.getToggleVisibilityHandler()}
                            className="rounded"
                          />
                          <span className="text-gray-700 dark:text-gray-300">
                            {column.columnDef.header as string}
                          </span>
                        </label>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* Export Button */}
            {enableExport && (
              <button
                onClick={exportToCsv}
                className="p-2 border border-gray-300 rounded-md hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700 flex items-center gap-2"
              >
                <Download className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                <span className="text-sm text-gray-700 dark:text-gray-300">יצוא</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th key={header.id} className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    <div
                      className={`flex items-center gap-1 ${
                        header.column.getCanSort() ? 'cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-100' : ''
                      }`}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() && (
                        <span className="flex flex-col">
                          <ChevronUp 
                            className={`h-3 w-3 ${
                              header.column.getIsSorted() === 'asc' ? 'text-blue-600' : 'text-gray-300'
                            }`} 
                          />
                          <ChevronDown 
                            className={`h-3 w-3 ${
                              header.column.getIsSorted() === 'desc' ? 'text-blue-600' : 'text-gray-300'
                            }`} 
                          />
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-700 dark:text-gray-300">
            מציג {table.getRowModel().rows.length} מתוך {table.getCoreRowModel().rows.length} תוצאות
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
          >
            הקודם
          </button>
          
          <span className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300">
            עמוד {table.getState().pagination.pageIndex + 1} מתוך {table.getPageCount()}
          </span>
          
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
          >
            הבא
          </button>
        </div>
      </div>
    </div>
  );
}

export default DataTable;