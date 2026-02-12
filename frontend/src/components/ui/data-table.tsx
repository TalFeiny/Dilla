"use client"

import * as React from "react"
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  Row,
  Column,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { useVirtualizer } from "@tanstack/react-virtual"
import { 
  ChevronDown, 
  ChevronUp, 
  ArrowUpDown, 
  Eye, 
  EyeOff, 
  Download, 
  Filter, 
  Copy, 
  Edit, 
  Trash2, 
  FileSpreadsheet,
  Plus,
  MoreVertical,
  Calculator,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ChevronRight
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import * as ContextMenu from "@radix-ui/react-context-menu"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/ui/empty-state"
import { cn } from "@/lib/utils"

// Helper to get column id from ColumnDef (TanStack v8: accessorKey or id)
function getColumnId<TData, TValue>(col: ColumnDef<TData, TValue>): string {
  if (typeof col.id === 'string') return col.id;
  const accessor = (col as { accessorKey?: string }).accessorKey;
  return accessor ?? '';
}

// Types for services and formulas
export interface ColumnService {
  id: string
  name: string
  description?: string
  icon?: React.ReactNode
  category?: string
}

export interface ColumnFormula {
  id: string
  name: string
  syntax: string
  description?: string
  category: "Math" | "Financial" | "Text" | "Date" | "Statistical" | "Logical"
}

export type CellType = "text" | "badge" | "link" | "status" | "number"

export interface CellStatus {
  state: "idle" | "loading" | "success" | "error"
  message?: string
}

interface EnhancedDataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  searchable?: boolean
  searchPlaceholder?: string
  searchColumn?: string
  enablePagination?: boolean
  pageSize?: number
  virtualized?: boolean
  exportable?: boolean
  exportFileName?: string
  className?: string
  onRowClick?: (row: TData) => void
  onRowEdit?: (row: TData) => void
  onRowDelete?: (row: TData) => void
  editable?: boolean
  // New enhanced props
  enableRowSelection?: boolean
  enableHeaderDropdowns?: boolean
  cellEditable?: boolean
  onCellEdit?: (rowId: string, columnId: string, value: any) => void
  onServiceExecute?: (columnId: string, serviceId: string, rowIds?: string[]) => void
  onFormulaApply?: (columnId: string, formulaId: string) => void
  columnServices?: Record<string, ColumnService[]>
  columnFormulas?: Record<string, ColumnFormula[]>
  cellRenderers?: Record<string, (value: any, row: TData) => React.ReactNode>
  cellStatuses?: Record<string, CellStatus>
  onAddRow?: () => void
  getRowId?: (row: TData) => string
}

// Loading indicator component
const LoadingDots = () => (
  <div className="flex items-center gap-1 text-xs text-muted-foreground">
    <span>Reading</span>
    <div className="flex gap-0.5">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-1 w-1 rounded-full bg-current opacity-70"
        />
      ))}
    </div>
  </div>
)

// Cell status indicator
const CellStatusIndicator = ({ status }: { status: CellStatus }) => {
  if (status.state === "loading") {
    return <LoadingDots />
  }
  if (status.state === "success") {
    return (
      <div className="flex items-center gap-1 text-xs text-green-600">
        <CheckCircle2 className="h-3 w-3" />
        {status.message || "Done"}
      </div>
    )
  }
  if (status.state === "error") {
    return (
      <div className="flex items-center gap-1 text-xs text-red-600">
        <AlertCircle className="h-3 w-3" />
        {status.message || "Error"}
      </div>
    )
  }
  return null
}

// Enhanced header with dropdown
const EnhancedHeader = <TData, TValue>({
  header,
  column,
  enableHeaderDropdowns,
  columnServices,
  columnFormulas,
  onServiceExecute,
  onFormulaApply,
  selectedRowIds,
}: {
  header: any
  column: Column<TData, TValue>
  enableHeaderDropdowns?: boolean
  columnServices?: Record<string, ColumnService[]>
  columnFormulas?: Record<string, ColumnFormula[]>
  onServiceExecute?: (columnId: string, serviceId: string, rowIds?: string[]) => void
  onFormulaApply?: (columnId: string, formulaId: string) => void
  selectedRowIds?: string[]
}) => {
  const columnId = column.id
  const services = columnServices?.[columnId] || []
  const formulas = columnFormulas?.[columnId] || []
  const hasDropdown = enableHeaderDropdowns && (services.length > 0 || formulas.length > 0)

  const handleServiceClick = (serviceId: string) => {
    onServiceExecute?.(columnId, serviceId, selectedRowIds)
  }

  const handleFormulaClick = (formulaId: string) => {
    onFormulaApply?.(columnId, formulaId)
  }

  if (!hasDropdown) {
    return (
      <div
        className={cn(
          "flex items-center gap-2",
          column.getCanSort() && "hover:text-primary cursor-pointer"
        )}
        onClick={column.getToggleSortingHandler()}
      >
        {flexRender(column.columnDef.header, header.getContext())}
        {column.getCanSort() && (
          <span className="ml-1">
            {{
              asc: <ChevronUp className="h-4 w-4" />,
              desc: <ChevronDown className="h-4 w-4" />,
            }[column.getIsSorted() as string] ?? (
              <ArrowUpDown className="h-4 w-4 opacity-50" />
            )}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 w-full">
      <div
        className={cn(
          "flex items-center gap-2 flex-1",
          column.getCanSort() && "hover:text-primary cursor-pointer"
        )}
        onClick={column.getToggleSortingHandler()}
      >
        {flexRender(column.columnDef.header, header.getContext())}
        {column.getCanSort() && (
          <span className="ml-1">
            {{
              asc: <ChevronUp className="h-4 w-4" />,
              desc: <ChevronDown className="h-4 w-4" />,
            }[column.getIsSorted() as string] ?? (
              <ArrowUpDown className="h-4 w-4 opacity-50" />
            )}
          </span>
        )}
      </div>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 opacity-60 hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreVertical className="h-3.5 w-3.5" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="start" onClick={(e) => e.stopPropagation()}>
          <Command>
            <CommandInput placeholder="Search services and formulas..." />
            <CommandList>
              <CommandEmpty>No services or formulas found.</CommandEmpty>
              {services.length > 0 && (
                <>
                  <CommandGroup heading="Services">
                    {services.map((service) => (
                      <CommandItem
                        key={service.id}
                        onSelect={() => handleServiceClick(service.id)}
                        className="flex items-center gap-2"
                      >
                        {service.icon || <Sparkles className="h-4 w-4" />}
                        <div className="flex-1">
                          <div className="font-medium">{service.name}</div>
                          {service.description && (
                            <div className="text-xs text-muted-foreground">
                              {service.description}
                            </div>
                          )}
                        </div>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                  {formulas.length > 0 && <CommandSeparator />}
                </>
              )}
              {formulas.length > 0 && (
                <CommandGroup heading="Formulas">
                  {formulas.map((formula) => (
                    <CommandItem
                      key={formula.id}
                      onSelect={() => handleFormulaClick(formula.id)}
                      className="flex items-center gap-2"
                    >
                      <Calculator className="h-4 w-4" />
                      <div className="flex-1">
                        <div className="font-medium">{formula.name}</div>
                        <div className="text-xs text-muted-foreground font-mono">
                          {formula.syntax}
                        </div>
                        {formula.description && (
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {formula.description}
                          </div>
                        )}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}

// Enhanced cell renderer
const EnhancedCell = <TData,>({
  cell,
  row,
  cellRenderers,
  cellStatuses,
  cellEditable,
  onCellEdit,
  getRowId,
}: {
  cell: any
  row: Row<TData>
  cellRenderers?: Record<string, (value: any, row: TData) => React.ReactNode>
  cellStatuses?: Record<string, CellStatus>
  cellEditable?: boolean
  onCellEdit?: (rowId: string, columnId: string, value: any) => void
  getRowId?: (row: TData) => string
}) => {
  const columnId = cell.column.id
  const value = cell.getValue()
  const rowId = getRowId ? getRowId(row.original) : row.id
  const cellKey = `${rowId}-${columnId}`
  const status = cellStatuses?.[cellKey]
  const customRenderer = cellRenderers?.[columnId]
  const [isEditing, setIsEditing] = React.useState(false)
  const [editValue, setEditValue] = React.useState(value)

  const handleDoubleClick = () => {
    if (cellEditable && onCellEdit) {
      setIsEditing(true)
      setEditValue(value)
    }
  }

  const handleBlur = () => {
    if (isEditing && onCellEdit && editValue !== value) {
      onCellEdit(rowId, columnId, editValue)
    }
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleBlur()
    } else if (e.key === "Escape") {
      setIsEditing(false)
      setEditValue(value)
    }
  }

  if (isEditing) {
    return (
      <Input
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        className="h-8"
        autoFocus
      />
    )
  }

  if (status?.state === "loading") {
    return (
      <div className="flex items-center gap-2">
        {customRenderer ? customRenderer(value, row.original) : <span>{String(value ?? "")}</span>}
        <CellStatusIndicator status={status} />
      </div>
    )
  }

  if (customRenderer) {
    return (
      <div
        onDoubleClick={handleDoubleClick}
        className={cn(
          "min-h-[2rem] flex items-center",
          cellEditable && "cursor-text hover:bg-muted/50 rounded px-1"
        )}
      >
        {customRenderer(value, row.original)}
        {status && <CellStatusIndicator status={status} />}
      </div>
    )
  }

  // Default rendering with type detection
  if (typeof value === "object" && value !== null) {
    if ("type" in value && value.type === "badge") {
      return (
        <Badge variant={value.variant || "default"} className="max-w-fit">
          {value.label || String(value)}
        </Badge>
      )
    }
    if ("type" in value && value.type === "link") {
      return (
        <a
          href={value.href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline flex items-center gap-1"
        >
          {value.label || value.href}
          <ExternalLink className="h-3 w-3" />
        </a>
      )
    }
    if ("type" in value && value.type === "status") {
      return (
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-2 w-2 rounded-full",
              value.state === "success" && "bg-green-500",
              value.state === "error" && "bg-red-500",
              value.state === "warning" && "bg-yellow-500",
              value.state === "info" && "bg-blue-500"
            )}
          />
          <span>{value.label || String(value)}</span>
        </div>
      )
    }
  }

  return (
    <div
      onDoubleClick={handleDoubleClick}
      className={cn(
        "min-h-[2rem] flex items-center",
        cellEditable && "cursor-text hover:bg-muted/50 rounded px-1"
      )}
    >
      <span>{String(value ?? "")}</span>
      {status && <CellStatusIndicator status={status} />}
    </div>
  )
}

export function DataTable<TData, TValue>({
  columns,
  data,
  searchable = true,
  searchPlaceholder = "Search...",
  searchColumn,
  enablePagination = true,
  pageSize: initialPageSize = 10,
  virtualized = false,
  exportable = false,
  exportFileName = "data",
  className,
  onRowClick,
  onRowEdit,
  onRowDelete,
  editable = false,
  enableRowSelection = false,
  enableHeaderDropdowns = false,
  cellEditable = false,
  onCellEdit,
  onServiceExecute,
  onFormulaApply,
  columnServices,
  columnFormulas,
  cellRenderers,
  cellStatuses,
  onAddRow,
  getRowId,
}: EnhancedDataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = React.useState({})
  const [globalFilter, setGlobalFilter] = React.useState("")
  const [pagination, setPagination] = React.useState({
    pageIndex: 0,
    pageSize: initialPageSize,
  })

  // Add selection column if enabled
  const enhancedColumns = React.useMemo(() => {
    if (!enableRowSelection) return columns

    const selectionColumn: ColumnDef<TData, TValue> = {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
      size: 40,
    }

    return [selectionColumn, ...columns]
  }, [columns, enableRowSelection])

  const table = useReactTable({
    data,
    columns: enhancedColumns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: enablePagination ? getPaginationRowModel() : undefined,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    globalFilterFn: "includesString",
    enableRowSelection: enableRowSelection,
    getRowId: getRowId,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter,
      pagination,
    },
  })

  const selectedRowIds = React.useMemo(() => {
    return Object.keys(rowSelection).filter((key) => rowSelection[key])
  }, [rowSelection])

  // Virtual scrolling setup
  const parentRef = React.useRef<HTMLDivElement>(null)
  const rowVirtualizer = virtualized
    ? useVirtualizer({
        count: table.getRowModel().rows.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 50,
        overscan: 10,
        measureElement:
          typeof window !== "undefined" && navigator.userAgent.indexOf("Firefox") === -1
            ? (element) => element?.getBoundingClientRect().height
            : undefined,
      })
    : null

  // Export functions
  const exportToCSV = () => {
    const headers = columns
      .filter((col) => {
        const id = getColumnId(col)
        return columnVisibility[id] !== false
      })
      .map((col) => {
        const id = getColumnId(col)
        return typeof col.header === "string" ? col.header : id
      })
      .join(",")

    const visibleRows = table.getFilteredRowModel().rows
    const rows = visibleRows.map((row) =>
      columns
        .filter((col) => {
          const id = getColumnId(col)
          return columnVisibility[id] !== false
        })
        .map((col) => {
          const cellValue = row.getValue(getColumnId(col))
          const value = cellValue ?? ""
          if (typeof value === "string" && (value.includes(",") || value.includes('"'))) {
            return `"${value.replace(/"/g, '""')}"`
          }
          return value
        })
        .join(",")
    )

    const csv = [headers, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${exportFileName}-${new Date().toISOString().split("T")[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportToJSON = () => {
    const visibleRows = table.getFilteredRowModel().rows
    const json = visibleRows.map((row) => row.original)
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${exportFileName}-${new Date().toISOString().split("T")[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Context menu functions
  const copyRow = (row: Row<TData>) => {
    const rowData = row.getVisibleCells().map((cell) => {
      const value = cell.getValue()
      return value ?? ""
    })
    const text = rowData.join("\t")
    navigator.clipboard.writeText(text)
  }

  const exportRow = (row: Row<TData>) => {
    const rowData = row.original
    const json = JSON.stringify(rowData, null, 2)
    const blob = new Blob([json], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${exportFileName}-row-${new Date().toISOString().split("T")[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const renderRow = (row: Row<TData>, index?: number, virtualStyle?: React.CSSProperties) => {
    const rowContent = (
      <TableRow
        key={row.id}
        data-index={index}
        data-state={row.getIsSelected() && "selected"}
        className={cn(
          onRowClick && "cursor-pointer",
          "hover:bg-muted/30 transition-colors border-b border-border/40",
          row.getIsSelected() && "bg-muted/50"
        )}
        style={virtualStyle}
        onClick={() => onRowClick?.(row.original)}
      >
        {row.getVisibleCells().map((cell) => (
          <TableCell
            key={cell.id}
            className="py-3 px-4"
            style={virtualStyle ? { height: `${(virtualStyle as any).height}px` } : undefined}
          >
            <EnhancedCell
              cell={cell}
              row={row}
              cellRenderers={cellRenderers}
              cellStatuses={cellStatuses}
              cellEditable={cellEditable}
              onCellEdit={onCellEdit}
              getRowId={getRowId}
            />
          </TableCell>
        ))}
      </TableRow>
    )

    if (editable || onRowEdit || onRowDelete) {
      return (
        <ContextMenu.Root key={row.id}>
          <ContextMenu.Trigger asChild>{rowContent}</ContextMenu.Trigger>
          <ContextMenu.Portal>
            <ContextMenu.Content className="min-w-[180px] bg-popover border border-border rounded-md shadow-lg p-1 z-50">
              <ContextMenu.Item
                className="flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer rounded-sm hover:bg-accent focus:bg-accent outline-none"
                onSelect={() => copyRow(row)}
              >
                <Copy className="h-4 w-4" />
                Copy row
              </ContextMenu.Item>
              {editable && onRowEdit && (
                <ContextMenu.Item
                  className="flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer rounded-sm hover:bg-accent focus:bg-accent outline-none"
                  onSelect={() => onRowEdit(row.original)}
                >
                  <Edit className="h-4 w-4" />
                  Edit
                </ContextMenu.Item>
              )}
              {editable && onRowDelete && (
                <ContextMenu.Item
                  className="flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer rounded-sm hover:bg-accent focus:bg-accent outline-none text-destructive"
                  onSelect={() => onRowDelete(row.original)}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </ContextMenu.Item>
              )}
              <ContextMenu.Item
                className="flex items-center gap-2 px-2 py-1.5 text-sm cursor-pointer rounded-sm hover:bg-accent focus:bg-accent outline-none"
                onSelect={() => exportRow(row)}
              >
                <FileSpreadsheet className="h-4 w-4" />
                Export row
              </ContextMenu.Item>
            </ContextMenu.Content>
          </ContextMenu.Portal>
        </ContextMenu.Root>
      )
    }

    return rowContent
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-1">
          {searchable && (
            <div className="relative flex-1 max-w-sm">
              <Input
                placeholder={searchPlaceholder}
                value={globalFilter ?? ""}
                onChange={(event) => setGlobalFilter(String(event.target.value))}
                className="max-w-sm"
              />
            </div>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Eye className="mr-2 h-4 w-4" />
                Columns
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[200px]">
              {table
                .getAllColumns()
                .filter((column) => column.getCanHide())
                .map((column) => {
                  return (
                    <DropdownMenuCheckboxItem
                      key={column.id}
                      className="capitalize"
                      checked={column.getIsVisible()}
                      onCheckedChange={(value) => column.toggleVisibility(!!value)}
                    >
                      {column.id}
                    </DropdownMenuCheckboxItem>
                  )
                })}
            </DropdownMenuContent>
          </DropdownMenu>
          {exportable && (
            <>
              <Button variant="outline" size="sm" onClick={exportToCSV}>
                <Download className="mr-2 h-4 w-4" />
                CSV
              </Button>
              <Button variant="outline" size="sm" onClick={exportToJSON}>
                <Download className="mr-2 h-4 w-4" />
                JSON
              </Button>
            </>
          )}
        </div>
        {pagination && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {table.getFilteredRowModel().rows.length} row(s)
              {enableRowSelection && selectedRowIds.length > 0 && (
                <span className="ml-2">• {selectedRowIds.length} selected</span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card shadow-sm">
        <div
          ref={parentRef}
          className={cn(
            "relative overflow-auto",
            virtualized ? "h-[600px]" : "max-h-[600px]"
          )}
        >
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-muted/30 backdrop-blur-sm">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="border-b border-border/50">
                  {headerGroup.headers.map((header) => {
                    return (
                      <TableHead
                        key={header.id}
                        className={cn(
                          "h-12 px-4 font-semibold",
                          header.column.getCanSort() && "cursor-pointer select-none"
                        )}
                        style={{
                          width: header.getSize() !== 150 ? header.getSize() : undefined,
                        }}
                      >
                        {header.isPlaceholder ? null : (
                          <EnhancedHeader
                            header={header}
                            column={header.column}
                            enableHeaderDropdowns={enableHeaderDropdowns}
                            columnServices={columnServices}
                            columnFormulas={columnFormulas}
                            onServiceExecute={onServiceExecute}
                            onFormulaApply={onFormulaApply}
                            selectedRowIds={selectedRowIds}
                          />
                        )}
                      </TableHead>
                    )
                  })}
                </TableRow>
              ))}
            </TableHeader>
            {virtualized && rowVirtualizer ? (
              <TableBody
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  position: "relative",
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const row = table.getRowModel().rows[virtualRow.index]
                  return renderRow(row, virtualRow.index, {
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`,
                    height: `${virtualRow.size}px`,
                  })
                })}
              </TableBody>
            ) : (
              <TableBody>
                {table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row) => renderRow(row))
                ) : (
                  <TableRow>
                    <TableCell colSpan={enhancedColumns.length} className="h-24">
                      <EmptyState
                        variant="no-results"
                        title="No results found"
                        description="Try adjusting your search or filters"
                      />
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            )}
          </Table>
        </div>
      </div>

      {/* Add Row Button */}
      {onAddRow && (
        <div className="flex justify-end">
          <Button onClick={onAddRow} variant="outline" size="sm">
            <Plus className="mr-2 h-4 w-4" />
            Add Row
          </Button>
        </div>
      )}

      {/* Pagination */}
      {enablePagination && table.getPageCount() > 1 && (
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">Rows per page</p>
            <select
              value={pagination.pageSize}
              onChange={(e) => {
                const newPageSize = Number(e.target.value)
                setPagination((prev) => ({ ...prev, pageSize: newPageSize }))
                table.setPageSize(newPageSize)
              }}
              className="h-8 w-[70px] rounded-md border border-input bg-background px-2 text-sm"
            >
              {[10, 20, 30, 40, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-6 lg:gap-8">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">
                Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
