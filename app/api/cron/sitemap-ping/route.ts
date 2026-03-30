import { NextRequest, NextResponse } from 'next/server'

// Singurul cron care rulează pe Vercel — ping Google cu sitemap-ul
// Toate celelalte cron-uri rulează via GitHub Actions

function isCronRequest(req: NextRequest): boolean {
  return req.headers.get('authorization') === `Bearer ${process.env.CRON_SECRET}`
}

export async function GET(req: NextRequest) {
  if (!isCronRequest(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const sitemapUrl = `${process.env.NEXT_PUBLIC_SITE_URL || 'https://ghidulreducerilor.ro'}/sitemap.xml`

  try {
    // Ping Google Search Console
    const googlePing = await fetch(
      `https://www.google.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
      { method: 'GET' }
    )

    // Ping Bing
    const bingPing = await fetch(
      `https://www.bing.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
      { method: 'GET' }
    ).catch(() => ({ status: 0 }))

    console.log(`[CRON sitemap-ping] Google: ${googlePing.status}, Bing: ${bingPing.status}`)

    return NextResponse.json({
      ok: true,
      sitemap: sitemapUrl,
      google: googlePing.status,
      bing: bingPing.status
    })
  } catch (error: any) {
    return NextResponse.json({ ok: false, error: error.message }, { status: 500 })
  }
}
