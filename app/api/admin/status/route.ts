import { NextRequest, NextResponse } from 'next/server'
import path from 'path'
import fs from 'fs/promises'

const ROOT = path.join(process.cwd())

function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token') || req.nextUrl.searchParams.get('token')
  return token === process.env.ADMIN_SECRET_TOKEN
}

/**
 * GET /api/admin/status
 * Dashboard status complet al sistemului
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const status: Record<string, any> = {
    timestamp: new Date().toISOString(),
    system: 'GhidulReducerilor.ro'
  }

  // ===== Deals Stats =====
  try {
    const dealsPath = path.join(ROOT, 'data', 'deals.json')
    const deals = JSON.parse(await fs.readFile(dealsPath, 'utf-8'))
    const active = deals.filter((d: any) => d.is_active !== false)
    const discounts = active.map((d: any) => d.discount_percent || 0).filter((d: number) => d > 0)
    const brokenLinks = deals.filter((d: any) => d.link_status === 'not_found' || d.link_status === 'server_error')

    status.deals = {
      total: deals.length,
      active: active.length,
      broken_links: brokenLinks.length,
      avg_discount: discounts.length > 0
        ? Math.round(discounts.reduce((a: number, b: number) => a + b, 0) / discounts.length * 10) / 10
        : 0,
      max_discount: Math.max(...discounts, 0)
    }
  } catch {
    status.deals = { error: 'Nu s-a putut citi deals.json' }
  }

  // ===== Codes Stats =====
  try {
    const codesPath = path.join(ROOT, 'data', 'codes.json')
    const codes = JSON.parse(await fs.readFile(codesPath, 'utf-8'))
    const now = new Date()
    const activeCodes = codes.filter((c: any) => {
      if (!c.active && c.active !== undefined) return false
      if (c.validUntil) {
        try {
          return new Date(c.validUntil) > now
        } catch { return true }
      }
      return true
    })

    status.codes = {
      total: codes.length,
      active: activeCodes.length
    }
  } catch {
    status.codes = { error: 'Nu s-a putut citi codes.json' }
  }

  // ===== Logs Status =====
  try {
    const logsDir = path.join(ROOT, 'logs')
    const logFiles = await fs.readdir(logsDir).catch(() => [])

    const today = new Date().toISOString().split('T')[0].replace(/-/g, '')

    status.logs = {
      pipeline_today: logFiles.includes(`pipeline_stats_${today}.json`),
      link_check_today: logFiles.some(f => f.startsWith(`link_check_${today}`)),
      seo_audit_recent: logFiles.filter(f => f.startsWith('seo_audit_')).length > 0,
      report_today: logFiles.includes(`daily_report_${today}.html`)
    }
  } catch {
    status.logs = { error: 'Nu s-au putut citi log-urile' }
  }

  // ===== Config Status =====
  const configFiles = ['magazines.json', 'schedule.json', 'email_templates.json', 'social_media.json', 'seo_keywords.json']
  const configStatus: Record<string, boolean> = {}

  for (const configFile of configFiles) {
    try {
      await fs.access(path.join(ROOT, 'config', configFile))
      configStatus[configFile] = true
    } catch {
      configStatus[configFile] = false
    }
  }

  status.config = configStatus

  // ===== Scripts Status =====
  const scriptFiles = ['scraper.py', 'daily_pipeline.py', 'newsletter.py', 'social_media_poster.py', 'link_checker.py', 'report_daily.py', 'email_support.py', 'seo_audit.py']
  const scriptsStatus: Record<string, boolean> = {}

  for (const script of scriptFiles) {
    try {
      await fs.access(path.join(ROOT, 'scripts', script))
      scriptsStatus[script] = true
    } catch {
      scriptsStatus[script] = false
    }
  }

  status.scripts = scriptsStatus

  // ===== ENV Variables Check =====
  status.env = {
    BREVO_API_KEY: !!process.env.BREVO_API_KEY,
    BREVO_LIST_ID: !!process.env.BREVO_LIST_ID,
    FB_PAGE_ID: !!process.env.FB_PAGE_ID,
    FB_ACCESS_TOKEN: !!process.env.FB_ACCESS_TOKEN,
    IG_USER_ID: !!process.env.IG_USER_ID,
    IG_ACCESS_TOKEN: !!process.env.IG_ACCESS_TOKEN,
    ADMIN_SECRET_TOKEN: !!process.env.ADMIN_SECRET_TOKEN
  }

  return NextResponse.json(status)
}
