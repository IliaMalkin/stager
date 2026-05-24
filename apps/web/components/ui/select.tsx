import { SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/cn';

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-10 rounded-md border border-border bg-bg px-3 text-sm',
        'focus:outline-none focus:ring-2 focus:ring-accent',
        className,
      )}
      {...props}
    />
  ),
);
Select.displayName = 'Select';
