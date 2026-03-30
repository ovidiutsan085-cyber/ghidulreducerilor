import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isAuthorized(req: NextRequest): boolean {
  const token = req.headers.get('x-admin-token')
  return token === process.env.ADMIN_SECRET_TOKEN
}

/**
 * GET /api/admin/newsletter
 * Returnează preview newsletter (HTML generat)
 */
export async function GET(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const type = req.nextUrl.searchParams.get('type') || 'daily'

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'newsletter.py')
    const outputFile = path.join(ROOT, 'data', `newsletter_preview_${type}.html`)
    const command = `python "${scriptPath}" --type ${type} --dry-run --output "${outputFile}"`

    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 30000,
      env: { ...process.env }
    })

    // Încearcă să citească HTML-ul generat
    const fs = await import('fs/promises')
    let htmlContent = null
    try {
      htmlContent = await fs.readFile(outputFile, 'utf-8')
    } catch {}

    // Extrage subject din output
    const subjectMatch = stdout.match(/Subject: (.+)/)
    const subject = subjectMatch ? subjectMatch[1] : null
    const htmlLengthMatch = stdout.match(/Lungime HTML: (\d+)/)
    const htmlLength = htmlLengthMatch ? parseInt(htmlLengthMatch[1]) : 0

    return NextResponse.json({
      status: 'ok',
      type,
      subject,
      html_length: htmlLength,
      has_preview: !!htmlContent,
      preview_url: htmlContent ? `/data/newsletter_preview_${type}.html` : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Newsletter preview error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}

/**
 * POST /api/admin/newsletter
 * Trimite newsletter
 * Body: { type: 'daily' | 'weekly', dry_run?: boolean }
 */
export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => ({}))
  const type = body.type || 'daily'
  const dryRun = body.dry_run || false

  const validTypes = ['daily', 'weekly', 'price_alert']
  if (!validTypes.includes(type)) {
    return NextResponse.json({ error: `Tip invalid: ${type}` }, { status: 400 })
  }

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'newsletter.py')
    const args = [`--type ${type}`, dryRun ? '--dry-run' : ''].filter(Boolean).join(' ')
    const command = `python "${scriptPath}" ${args}`

    const startTime = Date.now()
    const { stdout, stderr } = await execAsync(command, {
      cwd: ROOT,
      timeout: 60000,
      env: { ...process.env }
    })

    const elapsed = Date.now() - startTime
    const success = stdout.includes('trimis cu succes') || dryRun

    const subjectMatch = stdout.match(/Subject: (.+)/)
    const subject = subjectMatch ? subjectMatch[1].trim() : null

    return NextResponse.json({
      status: success ? 'sent' : 'error',
      type,
      dry_run: dryRun,
      elapsed_ms: elapsed,
      subject,
      output: stdout.slice(0, 500),
      errors: stderr ? stderr.slice(0, 200) : null
    })

  } catch (error: any) {
    return NextResponse.json({
      error: 'Newsletter send error',
      details: error.message?.slice(0, 300)
    }, { status: 500 })
  }
}
