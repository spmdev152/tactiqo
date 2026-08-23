import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges class names and resolves conflicting Tailwind utilities.
 *
 * @remarks
 * `clsx` flattens conditionals and falsy values, then `tailwind-merge` keeps only
 * the last utility of each conflicting group, so a caller can override a base
 * class by passing a later one instead of fighting CSS specificity.
 *
 * @param inputs - Class values, including conditionals and nested arrays.
 * @returns The merged class attribute.
 *
 * @example
 * ```ts
 * cn("px-2 py-1", isActive && "bg-primary", "px-4");
 * // -> "py-1 bg-primary px-4"
 * ```
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
