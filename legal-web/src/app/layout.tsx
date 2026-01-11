import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
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
  title: 'Ghana Legal AI - Your Constitutional & Legal Assistant',
  description:
    'An AI-powered legal assistant for Ghana. Chat with experts on the 1992 Constitution, case law, and legal history. Get accurate, cited information on your rights and the law.',
  keywords: ['Ghana Law', 'Constitution', 'Supreme Court', 'AI Legal Assistant', 'Ghana Legal AI', 'Lawyer AI'],
  authors: [{ name: 'Ghana Legal AI Team' }],
  openGraph: {
    title: 'Ghana Legal AI - Your Constitutional & Legal Assistant',
    description: 'Expert AI legal guidance on Ghana\'s Constitution and case law.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
