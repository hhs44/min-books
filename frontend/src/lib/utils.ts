// frontend/src/lib/utils.ts
// Tailwind class merge helper (no shadcn dep, minimal impl)
export function cn(...classes: Array<string | undefined | false | null>): string {
  return classes.filter(Boolean).join(" ");
}
