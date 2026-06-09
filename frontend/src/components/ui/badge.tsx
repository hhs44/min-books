import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "destructive" | "outline";

const variantClasses: Record<Variant, string> = {
  default: "bg-blue-600 text-white",
  secondary: "bg-gray-100 text-gray-900",
  destructive: "bg-red-100 text-red-700",
  outline: "border border-gray-300 text-gray-700",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLDivElement> & { variant?: Variant }) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
