'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export interface InputGroupProps extends Omit<React.ComponentProps<typeof Input>, 'className' | 'size' | 'prefix'> {
  /** Text or element before the input */
  prefix?: React.ReactNode;
  /** Text or element after the input */
  suffix?: React.ReactNode;
  /** Button attached to the end (e.g. "Search", "Submit") */
  addonButton?: React.ReactNode;
  /** Button click handler when using addonButton */
  onAddonClick?: () => void;
  /** Additional class for the wrapper */
  className?: string;
  /** Input wrapper class */
  inputClassName?: string;
  /** Size variant - affects heights */
  size?: 'sm' | 'default' | 'lg';
}

const sizeClasses = {
  sm: 'h-9 text-xs',
  default: 'h-10 text-sm',
  lg: 'h-12 text-base',
};

const addonSizeClasses = {
  sm: 'h-9 px-3 text-xs',
  default: 'h-10 px-4 text-sm',
  lg: 'h-12 px-5 text-base',
};

const InputGroup = React.forwardRef<HTMLInputElement, InputGroupProps>(
  (
    {
      prefix,
      suffix,
      addonButton,
      onAddonClick,
      className,
      inputClassName,
      size = 'default',
      disabled,
      ...props
    },
    ref
  ) => {
    const hasPrefix = !!prefix;
    const hasSuffix = !!suffix;
    const hasAddon = !!addonButton;

    return (
      <div
        className={cn(
          'flex w-full items-center overflow-hidden rounded-lg border border-input bg-background transition-colors',
          'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:border-ring',
          disabled && 'cursor-not-allowed opacity-50',
          className
        )}
      >
        {hasPrefix && (
          <div
            className={cn(
              'flex shrink-0 items-center border-r border-input bg-muted/50 px-3 text-muted-foreground',
              sizeClasses[size]
            )}
          >
            {prefix}
          </div>
        )}
        <Input
          ref={ref}
          disabled={disabled}
          className={cn(
            'flex-1 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 rounded-none shadow-none',
            hasPrefix && 'pl-2',
            (hasSuffix || hasAddon) && 'pr-2',
            sizeClasses[size],
            inputClassName
          )}
          {...props}
        />
        {hasSuffix && !hasAddon && (
          <div
            className={cn(
              'flex shrink-0 items-center border-l border-input bg-muted/50 px-3 text-muted-foreground',
              sizeClasses[size]
            )}
          >
            {suffix}
          </div>
        )}
        {hasAddon && (
          <div className="flex shrink-0 border-l border-input">
            {typeof addonButton === 'string' ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onAddonClick}
                disabled={disabled}
                className={cn('rounded-none border-0 h-full', addonSizeClasses[size])}
              >
                {addonButton}
              </Button>
            ) : (
              addonButton
            )}
          </div>
        )}
      </div>
    );
  }
);
InputGroup.displayName = 'InputGroup';

export { InputGroup };
