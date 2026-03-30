import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

// Vercel Cron Jobs trimit acest header
function isCronRequest(req: NextRequest): boolean {
  return req.headers.get('authorization') === `Bearer ${process.env.CRON_SECRET}`
}

export async function GET(req: NextRequest) {
  if (!isCronRequest(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const mode = req.nextUrl.searchParams.get('mode') || 'full'

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'daily_pipeline.py')
    const { stdout, stderr } = await execAsync(
      `python "${scriptPath}" --mode ${mode}`,
      { cwd: ROOT, timeout: 300000, env: { ...process.env } }
    )

    console.log(`[CRON scrape] OK — mode: ${mode}`)
    return NextResponse.json({ ok: true, mode, output: stdout.slice(0, 300) })
  } catch (error: any) {
    console.error(`[CRON scrape] FAIL:`, error.message)
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
