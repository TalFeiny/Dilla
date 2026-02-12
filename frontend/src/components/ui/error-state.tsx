"use client"

import { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { AlertCircle, RefreshCw, Home, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  title?: string
  description?: string
  error?: Error | string
  onRetry?: () => void
  onGoHome?: () => void
  onGoBack?: () => void
  className?: string
  illustration?: ReactNode
  actions?: ReactNode
}

export function ErrorState({
  title = "Something went wrong",
  description,
  error,
  onRetry,
  onGoHome,
  onGoBack,
  className,
  illustration,
  actions,
}: ErrorStateProps) {
  const errorMessage = error instanceof Error ? error.message : error

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
        <div className="mb-4 rounded-full bg-destructive/10 p-4">
          <AlertCircle className="h-12 w-12 text-destructive" />
        </div>
      )}

      <h3 className="text-xl font-semibold text-foreground mb-2">
        {title}
      </h3>

      {(description || errorMessage) && (
        <p className="text-sm text-muted-foreground max-w-md mb-6">
          {description || errorMessage}
        </p>
      )}

      {(onRetry || onGoHome || onGoBack || actions) && (
        <div className="flex items-center gap-2">
          {actions || (
            <>
              {onRetry && (
                <Button onClick={onRetry} variant="default">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Try Again
                </Button>
              )}
              {onGoBack && (
                <Button onClick={onGoBack} variant="outline">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Go Back
                </Button>
              )}
              {onGoHome && (
                <Button onClick={onGoHome} variant="outline">
                  <Home className="mr-2 h-4 w-4" />
                  Go Home
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
