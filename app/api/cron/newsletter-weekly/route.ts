import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isCronRequest(req: NextRequest): boolean {
  return req.headers.get('authorization') === `Bearer ${process.env.CRON_SECRET}`
}

// Rulează Vineri la 07:00 UTC (09:00 RO)
export async function GET(req: NextRequest) {
  if (!isCronRequest(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'newsletter.py')
    const { stdout } = await execAsync(
      `python "${scriptPath}" --type weekly`,
      { cwd: ROOL, timeout: 60000, env: { ...process.env } }
    )

    const success = stdout.includes('trimis cu succes')
    console.log(`[CRON newsletter-weekly] ${success ? 'OK' : 'FAIL'}`)
    return NextResponse.json({ ok: success, type: 'weekly', output: stdout.slice(0, 200) })
  } catch (error: any) {
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
