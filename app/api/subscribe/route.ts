import { NextRequest, NextResponse } from 'next/server'

// Rate limiter simplu in-memory (per IP, 5 cereri/minut)
const rateLimit = new Map<string, { count: number; resetAt: number }>()
const RATE_LIMIT = 5
const RATE_WINDOW = 60 * 1000 // 1 minut

function isRateLimited(ip: string): boolean {
  const now = Date.now()
  const entry = rateLimit.get(ip)

  if (!entry || now > entry.resetAt) {
    rateLimit.set(ip, { count: 1, resetAt: now + RATE_WINDOW })
    return false
  }

  entry.count++
  if (entry.count > RATE_LIMIT) return true
  return false
}

// Cleanup periodic (la fiecare 100 cereri, sterge intrari expirate)
let requestCount = 0
function cleanupRateLimit() {
  requestCount++
  if (requestCount % 100 !== 0) return
  const now = Date.now()
  rateLimit.forEach((entry, ip) => {
    if (now > entry.resetAt) rateLimit.delete(ip)
  })
}

// POST /api/subscribe — adaugă contact în Brevo (Sendinblue)
export async function POST(request: NextRequest) {
  try {
    cleanupRateLimit()

    // Rate limiting
    const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown'
    if (isRateLimited(ip)) {
      return NextResponse.json(
        { error: 'Prea multe cereri. Încearcă din nou peste un minut.' },
        { status: 429 }
      )
    }

    const body = await request.json()
    const { nume, email, magazin, gdpr_consent, consented_at } = body

    if (!email || !nume) {
      return NextResponse.json(
        { error: 'Numele și emailul sunt obligatorii' },
        { status: 400 }
      )
    }

    // Validare email format (server-side)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      return NextResponse.json(
        { error: 'Format email invalid' },
        { status: 400 }
      )
    }

    const apiKey = process.env.BREVO_API_KEY
    const listId = Number(process.env.BREVO_LIST_ID) || 2

    // Dacă nu avem cheie Brevo, logăm și returnăm succes (pentru development)
    if (!apiKey || apiKey === 'your-brevo-api-key-here') {
      console.log('[DEV] Abonare email:', { nume, email, magazin })
      return NextResponse.json({ success: true, dev: true })
    }

    // Trimite contactul la Brevo API
    const brevoRes = await fetch('https://api.brevo.com/v3/contacts', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-key': apiKey,
      },
      body: JSON.stringify({
        email,
        attributes: {
          FIRSTNAME: nume,
          MAGAZIN_PREFERAT: magazin || 'toate',
          GDPR_CONSENT: gdpr_consent ? 'yes' : 'no',
          CONSENT_DATE: consented_at || new Date().toISOString(),
        },
        listIds: [listId],
        updateEnabled: true,
      }),
    })

    if (!brevoRes.ok) {
      const errData = await brevoRes.json()
      // Contact deja existent — tratăm ca succes
      if (errData.code === 'duplicate_parameter') {
        return NextResponse.json({ success: true, existing: true })
      }
      console.error('Brevo error:', errData)
      return NextResponse.json(
        { error: 'Eroare la procesarea abonării. Încearcă din nou.' },
        { status: 500 }
      )
    }

    console.log(`[SUBSCRIBE] ${new Date().toISOString()} | ${email} | magazin: ${magazin || 'toate'} | gdpr: ${gdpr_consent}`)
    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Subscribe error:', error)
    return NextResponse.json(
      { error: 'Eroare server. Încearcă din nou.' },
      { status: 500 }
    )
  }
}
