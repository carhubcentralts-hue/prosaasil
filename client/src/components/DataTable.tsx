/**
 * AgentLocator v42 - Enhanced DataTable Component
 * טבלת נתונים מתקדמת עם תמיכה מלאה בעברית RTL, מיון, סינון וייצוא
 */

import React, { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  VisibilityState,
  PaginationState
} from '@tanstack/react-table';
import { ChevronDown, ChevronUp, Download, Filter, Search, Eye, EyeOff } from 'lucide-react';

interface DataTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData>[];
  searchPlaceholder?: string;
  exportFileName?: string;
  showPagination?: boolean;
  showSearch?: boolean;
  showColumnVisibility?: boolean;
  showExport?: boolean;
  rtl?: boolean;
  hebrewHeaders?: boolean;
}

export function DataTable<TData>({
  data,
  columns,
  searchPlaceholder = "חיפוש...",
  exportFileName = "data",
  showPagination = true,
  showSearch = true,
  showColumnVisibility = true,
  showExport = true,
  rtl = true,
  hebrewHeaders = true
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = useState('');
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10
  });

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      globalFilter,
      pagination
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    globalFilterFn: 'includesString'
  });

  // Export to CSV function
  const exportToCSV = () => {
    const headers = table.getAllColumns()
      .filter(col => col.getIsVisible())
      .map(col => col.id);
    
    const csvContent = [
      headers.join(','),
      ...table.getFilteredRowModel().rows.map(row => 
        headers.map(header => {
          const cellValue = row.getValue(header);
          return typeof cellValue === 'string' && cellValue.includes(',') 
            ? `"${cellValue}"` 
            : String(cellValue || '');
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([`\uFEFF${csvContent}`], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${exportFileName}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  const totalRows = table.getFilteredRowModel().rows.length;
  const currentPage = pagination.pageIndex + 1;
  const totalPages = Math.ceil(totalRows / pagination.pageSize);
  const startRow = pagination.pageIndex * pagination.pageSize + 1;
  const endRow = Math.min(startRow + pagination.pageSize - 1, totalRows);

  return (
    <div className={`w-full space-y-4 ${rtl ? 'dir-rtl' : 'dir-ltr'}`} dir={rtl ? 'rtl' : 'ltr'}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4 flex-1">
          {showSearch && (
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                dir={rtl ? 'rtl' : 'ltr'}
              />
            </div>
          )}
          
          {showColumnVisibility && (
            <div className="relative group">
              <button 
                className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                <Eye className="h-4 w-4" />
                <span>{hebrewHeaders ? 'עמודות' : 'Columns'}</span>
                <ChevronDown className="h-4 w-4" />
              </button>
              
              <div className="absolute top-full mt-1 left-0 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-48 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                <div className="p-2">
                  {table.getAllColumns()
                    .filter(column => column.getCanHide())
                    .map(column => (
                      <label key={column.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={column.getIsVisible()}
                          onChange={(e) => column.toggleVisibility(e.target.checked)}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm capitalize">{column.id}</span>
                      </label>
                    ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {showExport && (
            <button
              onClick={exportToCSV}
              className="flex items-center gap-2 px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <Download className="h-4 w-4" />
              <span>{hebrewHeaders ? 'ייצוא CSV' : 'Export CSV'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              {table.getHeaderGroups().map(headerGroup => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map(header => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                      onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                      style={{ 
                        textAlign: rtl ? 'right' : 'left',
                        direction: rtl ? 'rtl' : 'ltr' 
                      }}
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getCanSort() && (
                          <span className="ml-1">
                            {header.column.getIsSorted() === 'asc' ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : header.column.getIsSorted() === 'desc' ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <div className="h-4 w-4 opacity-0 group-hover:opacity-100">
                                <ChevronDown className="h-4 w-4" />
                              </div>
                            )}
                          </span>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td 
                    colSpan={columns.length} 
                    className="px-4 py-8 text-center text-gray-500"
                    style={{ direction: rtl ? 'rtl' : 'ltr' }}
                  >
                    {hebrewHeaders ? 'אין נתונים להצגה' : 'No data available'}
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map(row => (
                  <tr 
                    key={row.id} 
                    className="hover:bg-gray-50 transition-colors"
                  >
                    {row.getVisibleCells().map(cell => (
                      <td 
                        key={cell.id} 
                        className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap"
                        style={{ 
                          textAlign: rtl ? 'right' : 'left',
                          direction: rtl ? 'rtl' : 'ltr' 
                        }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {showPagination && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-700" style={{ direction: rtl ? 'rtl' : 'ltr' }}>
            {hebrewHeaders 
              ? `מציג ${startRow} עד ${endRow} מתוך ${totalRows} תוצאות`
              : `Showing ${startRow} to ${endRow} of ${totalRows} results`
            }
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="px-3 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              {hebrewHeaders ? (rtl ? 'הקודם' : 'Previous') : 'Previous'}
            </button>
            
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNumber;
                if (totalPages <= 5) {
                  pageNumber = i + 1;
                } else if (currentPage <= 3) {
                  pageNumber = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNumber = totalPages - 4 + i;
                } else {
                  pageNumber = currentPage - 2 + i;
                }

                return (
                  <button
                    key={pageNumber}
                    onClick={() => table.setPageIndex(pageNumber - 1)}
                    className={`px-3 py-2 text-sm border rounded-lg ${
                      currentPage === pageNumber
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {pageNumber}
                  </button>
                );
              })}
            </div>
            
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="px-3 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              {hebrewHeaders ? (rtl ? 'הבא' : 'Next') : 'Next'}
            </button>
          </div>
        </div>
      )}

      {/* Page Size Selector */}
      {showPagination && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-700">
            {hebrewHeaders ? 'פריטים בעמוד:' : 'Items per page:'}
          </span>
          <select
            value={pagination.pageSize}
            onChange={(e) => setPagination(prev => ({ ...prev, pageSize: Number(e.target.value) }))}
            className="px-2 py-1 border border-gray-300 rounded text-sm"
          >
            {[5, 10, 25, 50, 100].map(pageSize => (
              <option key={pageSize} value={pageSize}>
                {pageSize}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

// Hebrew-specific column helper
export function createHebrewColumn<TData>(
  id: string,
  hebrewHeader: string,
  accessor: keyof TData,
  cell?: (value: any) => React.ReactNode
): ColumnDef<TData> {
  return {
    id,
    header: hebrewHeader,
    accessorKey: accessor as string,
    cell: cell ? ({ getValue }) => cell(getValue()) : undefined,
    enableSorting: true,
    enableHiding: true
  };
}

// Date formatter for Hebrew locale
export function formatHebrewDate(date: string | Date): string {
  if (!date) return '';
  const d = new Date(date);
  return d.toLocaleDateString('he-IL', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    timeZone: 'Asia/Jerusalem'
  });
}

// Number formatter for Hebrew locale
export function formatHebrewNumber(num: number): string {
  return new Intl.NumberFormat('he-IL').format(num);
}

// Currency formatter for Israeli Shekel
export function formatIsraeliCurrency(amount: number): string {
  return new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS'
  }).format(amount);
}