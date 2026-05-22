import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border border-transparent bg-primary text-primary-foreground",
        secondary: "border border-transparent bg-secondary text-secondary-foreground",
        destructive: "border border-transparent bg-destructive text-destructive-foreground",
        outline: "border border-border text-foreground",
        success: "border border-transparent bg-[color:color-mix(in_oklch,var(--ghana-green)_18%,transparent)] text-[var(--ghana-green)]",
        warning: "border border-transparent bg-[color:color-mix(in_oklch,var(--ghana-gold)_18%,transparent)] text-[var(--ghana-gold)]",
        info: "border border-transparent bg-[color:color-mix(in_oklch,var(--info)_18%,transparent)] text-[var(--info)]",
        gold: "border border-[color:color-mix(in_oklch,var(--ghana-gold)_30%,transparent)] bg-[color:color-mix(in_oklch,var(--ghana-gold)_10%,transparent)] text-[var(--ghana-gold)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
