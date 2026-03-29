/**
 * DSS UI root layout.
 *
 * Purpose: Apply global styles, fonts, and the shadcn/ui theme to all DSS dashboard pages.
 * Responsibilities:
 *   - Set document metadata (title: DSS).
 *   - Wrap all children in a theme-aware container.
 * Dependencies: Next.js App Router, shadcn/ui Neutral theme
 */

import "./globals.css";

export const metadata = {
  title: "DSS",
  description: "DSS (Distributed Storage System)",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
