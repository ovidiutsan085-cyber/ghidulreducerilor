import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'
import fs from 'fs/promises'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token')
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
    const htmlReportPath = path.join(logsDir, `daily_report_${dateStr}.html`)
    const jsonReportPath = path.join(logsDir, `pipeline_stats_${dateStr}.json`)

    if (format === 'html') {
      try {
        const html = await fs.readFile(htmlReportPath, 'utf-8')
        return new NextResponse(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } })
      } catch {
        return NextResponse.json({ error: `Raport HTML pentru ${date} nu există` }, { status: 404 })
      }
    }

    const reportData: Record<string, any> = { date, generated_at: new Date().toISOString() }
    try { reportData.pipeline = JSON.parse(await fs.readFile(jsonReportPath, 'utf-8')) } catch {}

    const linkCheckFiles = (await fs.readdir(path.join(ROOT, 'logs')).catch(() => []))
      .filter(f => f.startsWith(`link_check_${dateStr}`)).sort().reverse()
    if (linkCheckFiles.length > 0) {
      try { reportData.link_check = JSON.parse(await fs.readFile(path.join(path.join(ROOT, 'logs'), linkCheckFiles[0]), 'utf-8')) } catch {}
    }

    try {
      const deals = JSON.parse(await fs.readFile(path.join(ROOT, 'data', 'deals.json'), 'utf-8'))
      const active = deals.filter((d: any) => d.is_active !== false)
      const disc = active.map((d: any) => d.discount_percent || 0).filter((d: number) => d > 0)
      reportData.deals = { total: deals.length, active: active.length, avg_discount: disc.length > 0 ? Math.round(disc.reduce((a: number, b: number) => a + b, 0) / disc.length * 10) / 10 : 0, max_discount: Math.max(...disc, 0) }
    } catch {}

    return NextResponse.json({ status: 'ok', ...reportData })
  } catch (error: any) {
    return NextResponse.json({ error: 'Report error', details: error.message?.slice(0, 200) }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const date = body.date || new Date().toISOString().split('T')[0]
  const sendEmail = body.send_email || false

  try {
    const args = [`--date ${date}`, sendEmail ? '--send-email' : ''].filter(Boolean).join(' ')
    const { stdout, stderr } = await execAsync(`python "${path.join(ROOT, 'scripts', 'report_daily.py')}" ${args}`, { cwd: ROOT, timeout: 30000, env: { ...process.env } })
    return NextResponse.json({ status: 'ok', date, send_email: sendEmail, output: stdout.slice(0, 800), errors: stderr ? stderr.slice(0, 200) : null })
  } catch (error: any) {
    return NextResponse.json({ error: 'Report generation error', details: error.message?.slice(0, 300) }, { status: 500 })
  }
}
