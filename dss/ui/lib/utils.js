/**
 * Purpose: Utility helper for merging Tailwind class names using clsx and tailwind-merge.
 * Responsibilities: Export the cn() helper consumed by all shadcn/ui components.
 * Dependencies: clsx, tailwind-merge
 */

import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
