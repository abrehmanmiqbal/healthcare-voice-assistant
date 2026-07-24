import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  weight: ['300', '400', '500', '600', '700']
})

export const metadata: Metadata = {
  title: 'Healthcare Voice AI Assistant',
  description: 'Intelligent voice-powered healthcare assistant',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#0891b2',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-cyan-50/30">
          {children}
        </main>
      </body>
    </html>
  )
}