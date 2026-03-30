import type { Metadata } from 'next'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import CookieConsent from '@/components/CookieConsent'
import SocialProofWidget from '@/components/SocialProofWidget'
import './globals.css'

const SITE_URL = 'https://ghidulreducerilor.ro'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'GhidulReducerilor.ro — Reduceri și Coduri Promoționale România',
    template: '%s | GhidulReducerilor.ro',
  },
  description: 'Cele mai bune reduceri, oferte si coduri promotionale din Romania. eMAG, Fashion Days, Notino, Catena, Decathlon — verificate zilnic.',
  openGraph: {
    type: 'website',
    locale: 'ro_RO',
    siteName: 'GhidulReducerilor.ro',
    title: 'GhidulReducerilor.ro — Reduceri și Coduri Promoționale România',
    description: 'Cele mai bune reduceri, oferte și coduri promoționale din România. Verificate zilnic.',
    url: SITE_URL,
    images: [{ url: `${SITE_URL}/api/og`, width: 1200, height: 630, alt: 'GhidulReducerilor.ro' }],
  },
  twitter: {
    card: 'summary_large_image',
    images: [`${SITE_URL}/api/og`],
  },
  robots: { index: true, follow: true },
  alternates: { canonical: '/' },
}

// Organization Schema JSON-LD
const organizationSchema = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'GhidulReducerilor.ro',
  url: SITE_URL,
  logo: `${SITE_URL}/logo.png`,
  description: 'Site de reduceri și coduri promoționale din România',
  sameAs: ['https://www.tiktok.com/@catalinovidiu'],
  contactPoint: { '@type': 'ContactPoint', email: 'hello@ghidulreducerilor.ro', contactType: 'customer support' },
}

// Google Analytics 4 — loaded with consent mode default denied
// GA4 se incarca cu consent denied by default, CookieConsent updateaza la granted
function Analytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID
  if (!gaId || gaId === 'G-XXXXXXXXXX') return null
  return (
    <>
      <script dangerouslySetInnerHTML={{
        __html: `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied'});`,
      }} />
      <script async src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`} />
      <script dangerouslySetInnerHTML={{
        __html: `gtag('js',new Date());gtag('config','${gaId}',{cookie_flags:'SameSite=None;Secure'});`,
      }} />
    </>
  )
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#E8262A" />
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
        <meta name="profitshareid" content="2fbe74572bd296845e920501e42623f6" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }}
        />
        <Analytics />
      </head>
      <body className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1">{children}</main>
        <Footer />
        <CookieConsent />
        <SocialProofWidget />
      </body>
    </html>
  )
}
