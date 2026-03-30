import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

// Verificare token admin
function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token') || req.nextUrl.searchParams.get('token')
  return token === process.env.ADMIN_SECRET_TOKEN
}

/**
 * GET /api/admin/pipeline
 * Returnează ultimul raport pipeline
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const fs = await import('fs/promises')
    const logsDir = path.join(ROOT, 'logs')

    // Caută cel mai recent raport pipeline
    const files = await fs.readdir(logsDir).catch(() => [])
    const pipelineFiles = files
      .filter(f => f.startsWith('pipeline_stats_'))
      .sort()
      .reverse()

    if (pipelineFiles.length === 0) {
      return NextResponse.json({ status: 'no_reports', message: 'Nu există rapoarte pipeline' })
    }

    const latestFile = path.join(logsDir, pipelineFiles[0])
    const content = await fs.readFile(latestFile, 'utf-8')
    const stats = JSON.parse(content)

    return NextResponse.json({
      status: 'ok',
      latest_report: pipelineFiles[0],
      stats
    })
  } catch (error) {
    return NextResponse.json({ error: 'Eroare citire raport', details: String(error) }, { status: 500 })
  }
}

/**
 * POST /api/admin/pipeline
 * Lansează pipeline-ul zilnic
 * Body: { mode: 'full' | 'cleanup', dry_run?: boolean }
 */
export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const mode = body.mode || 'full'
  const dryRun = body.dry_run || false

  const validModes = ['full', 'cleanup']
  if (!validModes.includes(mode)) {
    return NextResponse.json({ error: `Mod invalid: ${mode}` }, { status: 400 })
  }

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'daily_pipeline.py')
    const args = [`--mode ${mode}`, dryRun ? '--dry-run' : ''].filter(Boolean).join(' ')
    const command = `python "${scriptPath}" ${args}`

    const startTime = Date.now()
    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 60000 // 60 secunde timeout
    })

    const elapsed = Date.now() - startTime

    // Parsează output JSON dacă există
    let pipelineStats = null
    try {
      const jsonMatch = stdout.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        pipelineStats = JSON.parse(jsonMatch[0])
      }
    } catch {}

    return NextResponse.json({
      status: 'ok',
      mode,
      dry_run: dryRun,
      elapsed_ms: elapsed,
      stats: pipelineStats,
      output: stdout.slice(0, 500),
      errors: stderr ? stderr.slice(0, 200) : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Pipeline error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}
