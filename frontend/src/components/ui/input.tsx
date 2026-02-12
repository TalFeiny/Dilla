import * as React from "react"
import { CheckCircle2, XCircle, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
  success?: boolean
  warning?: boolean
  helperText?: string
  showCharacterCount?: boolean
  maxLength?: number
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ 
    className, 
    type, 
    error,
    success,
    warning,
    helperText,
    showCharacterCount,
    maxLength,
    leftIcon,
    rightIcon,
    value,
    ...props 
  }, ref) => {
    const [currentLength, setCurrentLength] = React.useState(
      typeof value === "string" ? value.length : 0
    )

    React.useEffect(() => {
      if (typeof value === "string") {
        setCurrentLength(value.length)
      }
    }, [value])

    const hasIcon = error || success || warning || leftIcon || rightIcon

    return (
      <div className="w-full space-y-1.5">
        <div className="relative">
          {leftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {leftIcon}
            </div>
          )}
          <input
            type={type}
            className={cn(
              "flex h-10 w-full rounded-lg border bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
              leftIcon && "pl-10",
              (rightIcon || error || success || warning) && "pr-10",
              error && "border-destructive focus-visible:ring-destructive focus-visible:border-destructive",
              success && "border-green-500 focus-visible:ring-green-500 focus-visible:border-green-500",
              warning && "border-yellow-500 focus-visible:ring-yellow-500 focus-visible:border-yellow-500",
              !error && !success && !warning && "border-input focus-visible:ring-ring focus-visible:border-ring",
              className
            )}
            ref={ref}
            value={value}
            maxLength={maxLength}
            onChange={(e) => {
              if (showCharacterCount) {
                setCurrentLength(e.target.value.length)
              }
              props.onChange?.(e)
            }}
            {...props}
          />
          {rightIcon && !error && !success && !warning && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {rightIcon}
            </div>
          )}
          {error && (
            <XCircle className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-destructive" />
          )}
          {success && !error && (
            <CheckCircle2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-green-500" />
          )}
          {warning && !error && !success && (
            <AlertCircle className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-yellow-500" />
          )}
        </div>
        {(helperText || (showCharacterCount && maxLength)) && (
          <div className="flex items-center justify-between text-xs">
            {helperText && (
              <span
                className={cn(
                  error && "text-destructive",
                  success && "text-green-500",
                  warning && "text-yellow-500",
                  !error && !success && !warning && "text-muted-foreground"
                )}
              >
                {helperText}
              </span>
            )}
            {showCharacterCount && maxLength && (
              <span
                className={cn(
                  "ml-auto",
                  currentLength > maxLength * 0.9 && "text-yellow-500",
                  currentLength >= maxLength && "text-destructive"
                )}
              >
                {currentLength}/{maxLength}
              </span>
            )}
          </div>
        )}
      </div>
    )
  }
)
Input.displayName = "Input"

export { Input } 