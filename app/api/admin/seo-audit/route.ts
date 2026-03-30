import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token') || req.nextUrl.searchParams.get('token')
  return token === process.env.ADMIN_SECRET_TOKEN
}

/**
 * GET /api/admin/seo-audit
 * Returnează ultimul raport SEO
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const fs = await import('fs/promises')
    const logsDir = path.join(ROOT, 'logs')

    const files = await fs.readdir(logsDir).catch(() => [])
    const seoFiles = files
      .filter(f => f.startsWith('seo_audit_'))
      .sort()
      .reverse()

    if (seoFiles.length === 0) {
      return NextResponse.json({ status: 'no_reports', message: 'Nu există rapoarte SEO' })
    }

    const latestFile = path.join(logsDir, seoFiles[0])
    const content = await fs.readFile(latestFile, 'utf-8')
    const report = JSON.parse(content)

    // Returnează un rezumat (nu tot raportul care poate fi mare)
    return NextResponse.json({
      status: 'ok',
      latest_report: seoFiles[0],
      summary: {
        generated_at: report.generated_at,
        pages_audited: report.pages_audited,
        avg_score: report.avg_score,
        total_issues: report.total_issues,
        total_warnings: report.total_warnings,
        sitemap_ok: report.sitemap?.accessible,
        sitemap_urls: report.sitemap?.url_count,
        robots_ok: report.robots_txt?.accessible,
        page_scores: report.page_results?.map((p: any) => ({
          url: p.url,
          score: p.score,
          issues_count: p.issues?.length || 0
        })),
        critical_pages: report.critical_pages
      }
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Eroare citire raport SEO',
      details: error.message?.slice(0, 200)
    }, { status: 500 })
  }
}

/**
 * POST /api/admin/seo-audit
 * Lansează auditul SEO
 * Body: { mode: 'full' | 'quick', url?: string }
 */
export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const mode = body.mode || 'quick'
  const url = body.url || null

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'seo_audit.py')
    const args = [
      url ? `--url "${url}"` : `--mode ${mode}`
    ].join(' ')

    const command = `python "${scriptPath}" ${args}`

    const startTime = Date.now()
    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 120000,
      env: { ...process.env }
    })

    const elapsed = Date.now() - startTime

    // Extrage score mediu din output
    const scoreMatch = stdout.match(/Scor mediu: ([\d.]+)/)
    const issuesMatch = stdout.match(/Total issues: (\d+)/)

    return NextResponse.json({
      status: 'ok',
      mode,
      url,
      elapsed_ms: elapsed,
      summary: {
        avg_score: scoreMatch ? parseFloat(scoreMatch[1]) : null,
        total_issues: issuesMatch ? parseInt(issuesMatch[1]) : null
      },
      output: stdout.slice(0, 800),
      errors: stderr ? stderr.slice(0, 200) : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'SEO audit error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}
