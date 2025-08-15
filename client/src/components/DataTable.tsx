/**
 * Professional DataTable with TanStack - Hebrew RTL support
 */
import { useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  VisibilityState,
} from "@tanstack/react-table";
import { ChevronDown, Download, Search, Settings } from "lucide-react";

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  searchPlaceholder?: string;
  onRowClick?: (row: T) => void;
  isLoading?: boolean;
}

export function DataTable<T>({ 
  columns, 
  data, 
  searchPlaceholder = "חיפוש...", 
  onRowClick,
  isLoading = false 
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [density, setDensity] = useState<"compact" | "normal" | "comfortable">("normal");

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      globalFilter,
    },
  });

  const exportCSV = () => {
    const headers = columns.map(col => (col as any).header).join(",");
    const rows = data.map(row => 
      columns.map(col => {
        const accessor = (col as any).accessorKey;
        return `"${(row as any)[accessor] || ""}"`;
      }).join(",")
    ).join("\n");
    
    const csv = `${headers}\n${rows}`;
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const densityClasses = {
    compact: "py-1 px-2 text-sm",
    normal: "py-2 px-3",
    comfortable: "py-3 px-4 text-lg"
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 rtl:space-x-reverse">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative">
            <Search className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              value={globalFilter ?? ""}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder={searchPlaceholder}
              className="pl-8 pr-3 py-2 border rounded-md bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
              dir="rtl"
            />
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            className="flex items-center gap-2 px-3 py-2 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-700"
            data-testid="button-export-csv"
          >
            <Download className="w-4 h-4" />
            ייצוא CSV
          </button>
          
          <div className="relative group">
            <button className="flex items-center gap-2 px-3 py-2 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-700">
              <Settings className="w-4 h-4" />
              <ChevronDown className="w-4 h-4" />
            </button>
            
            <div className="absolute left-0 mt-1 w-48 bg-white dark:bg-gray-800 border rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
              <div className="p-2 space-y-1">
                <div className="text-sm font-medium p-2">צפיפות:</div>
                {(["compact", "normal", "comfortable"] as const).map(d => (
                  <button
                    key={d}
                    onClick={() => setDensity(d)}
                    className={`w-full text-right px-3 py-1 text-sm rounded hover:bg-gray-100 dark:hover:bg-gray-700 ${
                      density === d ? "bg-blue-50 dark:bg-blue-900" : ""
                    }`}
                  >
                    {d === "compact" ? "צפוף" : d === "normal" ? "רגיל" : "נוח"}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="border rounded-md overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={`text-right font-medium text-gray-900 dark:text-gray-100 border-b ${densityClasses[density]}`}
                    onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                    style={{ cursor: header.column.getCanSort() ? "pointer" : "default" }}
                  >
                    {header.isPlaceholder ? null : (
                      <div className="flex items-center gap-2">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{
                          asc: " ↑",
                          desc: " ↓",
                        }[header.column.getIsSorted() as string] ?? null}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800 border-b cursor-pointer"
                  onClick={() => onRowClick?.(row.original)}
                  data-testid={`row-customer-${row.id}`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className={`text-gray-900 dark:text-gray-100 ${densityClasses[density]}`}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="text-center py-10 text-gray-500">
                  <div className="flex flex-col items-center gap-2">
                    <Search className="w-8 h-8 text-gray-300" />
                    <div>לא נמצאו תוצאות</div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          מציג {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} עד{" "}
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            table.getFilteredRowModel().rows.length
          )}{" "}
          מתוך {table.getFilteredRowModel().rows.length} תוצאות
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 border rounded disabled:opacity-50"
            data-testid="button-previous-page"
          >
            הקודם
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 border rounded disabled:opacity-50"
            data-testid="button-next-page"
          >
            הבא
          </button>
        </div>
      </div>
    </div>
  );
}