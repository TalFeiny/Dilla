"use client"

import { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { LucideIcon, FileX, Search, Inbox, Package } from "lucide-react"

type EmptyStateVariant = "default" | "no-results" | "empty" | "error" | "loading"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
  variant?: EmptyStateVariant
  illustration?: ReactNode
}

const variantIcons: Record<EmptyStateVariant, LucideIcon> = {
  default: Inbox,
  "no-results": Search,
  empty: Package,
  error: FileX,
  loading: Inbox,
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  variant = "default",
  illustration,
}: EmptyStateProps) {
  const VariantIcon = Icon || variantIcons[variant]

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-4 text-center",
        className
      )}
    >
      {illustration ? (
        <div className="mb-6">
          {illustration}
        </div>
      ) : (
        <div
          className={cn(
            "mb-4 rounded-full p-4",
            variant === "error" && "bg-destructive/10",
            variant === "no-results" && "bg-muted",
            variant !== "error" && variant !== "no-results" && "bg-muted"
          )}
        >
          <VariantIcon
            className={cn(
              "h-8 w-8",
              variant === "error" && "text-destructive",
              variant !== "error" && "text-muted-foreground"
            )}
          />
        </div>
      )}
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-md mb-6">
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  )
}
