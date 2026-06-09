import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-gray-200",
        className,
      )}
    >
      <div
        className="h-full bg-blue-600 transition-all"
        style={{ width: `${v}%` }}
      />
    </div>
  );
}
