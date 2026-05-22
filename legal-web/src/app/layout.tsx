import type { Metadata } from 'next';
import { DM_Sans, JetBrains_Mono } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import { Analytics } from '@vercel/analytics/next';
import { ThemeProvider } from '@/components/theme-provider';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import './globals.css';

const dmSans = DM_Sans({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
  weight: ['400', '500', '600', '700'],
});

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'LexGH — AI Legal Research for Ghana',
  description:
    'Professional AI-powered research for Ghanaian case law, statutes, and legal precedents. Used by lawyers, judges, and law students.',
  keywords: ['Ghana Law', 'Constitution', 'Supreme Court', 'AI Legal Assistant', 'LexGH', 'Lawyer AI', 'Ghanaian Case Law'],
  authors: [{ name: 'LexGH Team' }],
  openGraph: {
    title: 'LexGH — AI Legal Research for Ghana',
    description: 'Professional AI-powered research for Ghanaian case law, statutes, and legal precedents.',
    type: 'website',
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <body className={`${dmSans.variable} ${jetbrainsMono.variable} antialiased bg-background text-foreground`}>
          <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
            <TooltipProvider delayDuration={150}>
              {children}
              <Toaster position="top-right" richColors />
            </TooltipProvider>
          </ThemeProvider>
          <Analytics />
        </body>
      </html>
    </ClerkProvider>
  );
}
