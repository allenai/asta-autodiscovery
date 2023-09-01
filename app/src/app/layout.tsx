import './shellac.v0.1.21.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Skiff NextJS Template',
  description: 'A Skiff Template that uses NextJS',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
      <script src="https://stats.allenai.org/init.min.js" async></script>
    </html>
  )
}
