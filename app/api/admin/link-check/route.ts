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
 * GET /api/admin/link-check
 * Returnează ultimul raport de verificare linkuri
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const fs = await import('fs/promises')
    const logsDir = path.join(ROOT, 'logs')

    const files = await fs.readdir(logsDir).catch(() => [])
    const linkCheckFiles = files
      .filter(f => f.startsWith('link_check_'))
      .sort()
      .reverse()

    if (linkCheckFiles.length === 0) {
      return NextResponse.json({ status: 'no_reports', message: 'Nu există rapoarte de link check' })
    }

    const latestFile = path.join(logsDir, linkCheckFiles[0])
    const content = await fs.readFile(latestFile, 'utf-8')
    const stats = JSON.parse(content)

    return NextResponse.json({
      status: 'ok',
      latest_report: linkCheckFiles[0],
      stats
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Eroare citire raport',
      details: error.message?.slice(0, 200)
    }, { status: 500 })
  }
}

/**
 * POST /api/admin/link-check
 * Lansează verificarea linkurilor
 * Body: { mode: 'full' | 'quick', deal_id?: string, dry_run?: boolean }
 */
export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const mode = body.mode || 'quick'
  const dealId = body.deal_id || null
  const dryRun = body.dry_run || false

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'link_checker.py')
    const args = [
      `--mode ${mode}`,
      dealId ? `--deal-id ${dealId}` : '',
      dryRun ? '--dry-run' : ''
    ].filter(Boolean).join(' ')

    const command = `python "${scriptPath}" ${args}`

    const startTime = Date.now()
    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 120000, // 2 minute pentru full check
      env: { ...process.env }
    })

    const elapsed = Date.now() - startTime

    // Parsează statisticile din output
    const totalMatch = stdout.match(/Total verificate: (\d+)/)
    const okMatch = stdout.match(/✅ OK: (\d+)/)
    const brokenMatch = stdout.match(/❌ Broken: (\d+)/)

    return NextResponse.json({
      status: 'ok',
      mode,
      deal_id: dealId,
      dry_run: dryRun,
      elapsed_ms: elapsed,
      summary: {
        total: totalMatch ? parseInt(totalMatch[1]) : null,
        ok: okMatch ? parseInt(okMatch[1]) : null,
        broken: brokenMatch ? parseInt(brokenMatch[1]) : null
      },
      output: stdout.slice(0, 800),
      errors: stderr ? stderr.slice(0, 200) : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Link check error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}
