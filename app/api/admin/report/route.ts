import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'
import fs from 'fs/promises'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token') || req.nextUrl.searchParams.get('token')
  return token === process.env.ADMIN_SECRET_TOKEN
}

/**
 * GET /api/admin/report
 * Returnează ultimul raport zilnic sau generează unul nou
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const date = req.nextUrl.searchParams.get('date') || new Date().toISOString().split('T')[0]
  const format = req.nextUrl.searchParams.get('format') || 'json'
  const dateStr = date.replace(/-/g, '')

  try {
    const logsDir = path.join(ROOT, 'logs')

    // Caută raportul HTML pentru data dată
    const htmlReportPath = path.join(logsDir, `daily_report_${dateStr}.html`)
    const jsonReportPath = path.join(logsDir, `pipeline_stats_${dateStr}.json`)

    if (format === 'html') {
      try {
        const html = await fs.readFile(htmlReportPath, 'utf-8')
        return new NextResponse(html, {
          headers: { 'Content-Type': 'text/html; charset=utf-8' }
        })
      } catch {
        return NextResponse.json({ error: `Raport HTML pentru ${date} nu există` }, { status: 404 })
      }
    }

    // Format JSON - combină datele disponibile
    const reportData: Record<string, any> = { date, generated_at: new Date().toISOString() }

    try {
      const pipelineStats = JSON.parse(await fs.readFile(jsonReportPath, 'utf-8'))
      reportData.pipeline = pipelineStats
    } catch {}

    // Caută statistici link checker
    const linkCheckFiles = (await fs.readdir(logsDir).catch(() => []))
      .filter(f => f.startsWith(`link_check_${dateStr}`))
      .sort()
      .reverse()

    if (linkCheckFiles.length > 0) {
      try {
        const linkStats = JSON.parse(await fs.readFile(path.join(logsDir, linkCheckFiles[0]), 'utf-8'))
        reportData.link_check = linkStats
      } catch {}
    }

    // Citește deals stats din deals.json
    try {
      const dealsPath = path.join(ROOT, 'data', 'deals.json')
      const deals = JSON.parse(await fs.readFile(dealsPath, 'utf-8'))
      const activeDeals = deals.filter((d: any) => d.is_active !== false)
      const discounts = activeDeals.map((d: any) => d.discount_percent || 0).filter((d: number) => d > 0)
      const avgDiscount = discounts.length > 0 ? Math.round(discounts.reduce((a: number, b: number) => a + b, 0) / discounts.length * 10) / 10 : 0

      reportData.deals = {
        total: deals.length,
        active: activeDeals.length,
        avg_discount: avgDiscount,
        max_discount: Math.max(...discounts, 0)
      }
    } catch {}

    return NextResponse.json({ status: 'ok', ...reportData })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Report error',
      details: error.message?.slice(0, 200)
    }, { status: 500 })
  }
}

/**
 * POST /api/admin/report
 * Generează un raport nou și opțional îl trimite pe email
 * Body: { date?: string, send_email?: boolean }
 */
export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const date = body.date || new Date().toISOString().split('T')[0]
  const sendEmail = body.send_email || false

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'report_daily.py')
    const args = [`--date ${date}`, sendEmail ? '--send-email' : ''].filter(Boolean).join(' ')
    const command = `python "${scriptPath}" ${args}`

    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 30000,
      env: { ...process.env }
    })

    return NextResponse.json({
      status: 'ok',
      date,
      send_email: sendEmail,
      output: stdout.slice(0, 800),
      errors: stderr ? stderr.slice(0, 200) : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Report generation error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}
