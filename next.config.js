/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      // Placeholder images (development)
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'via.placeholder.com' },
      // eMAG CDN
      { protocol: 'https', hostname: 's13emagst.akamaized.net' },
      { protocol: 'https', hostname: 's1emagst.akamaized.net' },
      { protocol: 'https', hostname: '**.emag.ro' },
      // Fashion Days
      { protocol: 'https', hostname: '**.fashiondays.ro' },
      { protocol: 'https', hostname: 'cdn.fashiondays.ro' },
      // Notino
      { protocol: 'https', hostname: '**.notino.ro' },
      { protocol: 'https', hostname: 'cdn.notinoimg.com' },
      // Answear
      { protocol: 'https', hostname: '**.answear.ro' },
      { protocol: 'https', hostname: 'img.answear.com' },
      // Decathlon
      { protocol: 'https', hostname: '**.decathlon.ro' },
      { protocol: 'https', hostname: 'contents.mediadecathlon.com' },
      // Catena
      { protocol: 'https', hostname: '**.catena.ro' },
      // Cel.ro / PC Garage
      { protocol: 'https', hostname: '**.cel.ro' },
      { protocol: 'https', hostname: '**.pcgarage.ro' },
      // Vexio / Libris / Fornello / ForIT
      { protocol: 'https', hostname: '**.vexio.ro' },
      { protocol: 'https', hostname: '**.libris.ro' },
      { protocol: 'https', hostname: '**.fornello.ro' },
      { protocol: 'https', hostname: '**.forit.ro' },
      // Generic CDN patterns
      { protocol: 'https', hostname: '**.cloudfront.net' },
      { protocol: 'https', hostname: '**.akamaized.net' },
    ],
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com https://www.google-analytics.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "img-src 'self' data: blob: https: http:",
              "font-src 'self' https://fonts.gstatic.com",
              "connect-src 'self' https://www.google-analytics.com https://api.brevo.com https://region1.google-analytics.com",
              "frame-ancestors 'none'",
            ].join('; '),
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig
