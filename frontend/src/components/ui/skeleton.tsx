import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-muted",
        "before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_2s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        className
      )}
      {...props}
    />
  )
}

function SkeletonCard({ 
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'>) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-6 shadow-sm",
        className
      )}
      {...props}
    >
      <Skeleton className="h-4 w-1/4 mb-4" />
      <Skeleton className="h-8 w-3/4 mb-2" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  )
}

function SkeletonTable({ 
  rows = 5, 
  columns = 4,
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'> & { 
  rows?: number
  columns?: number
}) {
  return (
    <div className={cn("space-y-2", className)} {...props}>
      {/* Header row */}
      <div className="flex gap-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={`header-${i}`} className="h-4 flex-1" />
        ))}
      </div>
      {/* Data rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={`${rowIndex}-${colIndex}`}
              className={cn(
                "h-4",
                colIndex === 0 ? "flex-1" : colIndex === columns - 1 ? "w-24" : "w-32"
              )}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

function SkeletonForm({ 
  fields = 3,
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'> & { 
  fields?: number
}) {
  return (
    <div className={cn("space-y-4", className)} {...props}>
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
    </div>
  )
}

function SkeletonChart({ 
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'>) {
  return (
    <div
      className={cn("space-y-4", className)}
      {...props}
    >
      <Skeleton className="h-6 w-48" />
      <div className="h-[300px] w-full rounded-lg border bg-card p-4">
        <div className="h-full flex items-end justify-between gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton
              key={i}
              className="w-full"
              style={{ height: `${Math.random() * 60 + 20}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function SkeletonList({ 
  items = 5,
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'> & { 
  items?: number
}) {
  return (
    <div className={cn("space-y-3", className)} {...props}>
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

function SkeletonText({ 
  lines = 3, 
  className, 
  ...props 
}: Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrag' | 'onDragStart' | 'onDragEnd'> & { 
  lines?: number 
}) {
  return (
    <div className={cn("space-y-2", className)} {...props}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i}>
          <Skeleton
            className={cn(
              "h-4",
              i === lines - 1 ? "w-3/4" : "w-full"
            )}
          />
        </div>
      ))}
    </div>
  )
}

export { 
  Skeleton, 
  SkeletonCard, 
  SkeletonTable, 
  SkeletonForm,
  SkeletonChart,
  SkeletonList,
  SkeletonText 
}
