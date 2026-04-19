import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import './globals.css';

const inter = Inter({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'LexGH Legal Research Assistant',
  description:
    'AI-powered research for Ghanaian case law and legal precedents.',
  keywords: ['Ghana Law', 'Constitution', 'Supreme Court', 'AI Legal Assistant', 'LexGH', 'Lawyer AI'],
  authors: [{ name: 'LexGH Team' }],
  openGraph: {
    title: 'LexGH Legal Research Assistant',
    description: 'AI-powered research for Ghanaian case law and legal precedents.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
