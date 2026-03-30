import { NextResponse } from 'next/server'
import deals from '@/data/deals.json'
import codes from '@/data/codes.json'

export async function GET(
  req: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params

  // Cauta in deals
  const deal = (deals as any[]).find((d) => d.id === id)
  if (deal?.link_afiliat) {
    logClick(req, id, 'deal', deal.magazin, deal.titlu)
    return NextResponse.redirect(deal.link_afiliat, { status: 302 })
  }

  // Cauta in coduri promo
  const code = (codes as any[]).find((c) => c.id === id)
  if (code?.link_afiliat) {
    logClick(req, id, 'code', code.magazin, code.cod)
    return NextResponse.redirect(code.link_afiliat, { status: 302 })
  }

  // Fallback la homepage
  console.log(`[REDIRECT] 404 — ID inexistent: ${id}`)
  return NextResponse.redirect(
    process.env.NEXT_PUBLIC_SITE_URL || 'https://ghidulreducerilor.ro',
    { status: 302 }
  )
}

/**
 * Logheaza click-ul pe link afiliat (server-side).
 * Util pentru debugging, rapoarte, si ca backup la GA4 client-side.
 */
function logClick(req: Request, id: string, type: string, magazin: string, label: string) {
  const ua = req.headers.get('user-agent') || ''
  const referer = req.headers.get('referer') || ''
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown'
  const isMobile = /Mobile|Android|iPhone/i.test(ua)

  console.log(
    `[CLICK] ${new Date().toISOString()} | ${type}:${id} | ${magazin} | "${label}" | ${isMobile ? 'mobile' : 'desktop'} | ref:${referer}`
  )
}
