import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)
const ROOT = path.join(process.cwd())

function isCronRequest(req: NextRequest): boolean {
  return req.headers.get('authorization') === `Bearer ${process.env.CRON_SECRET}`
}

export async function GET(req: NextRequest) {
  if (!isCronRequest(req)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const today = new Date().toISOString().split('T')[0]
    const scriptPath = path.join(ROOT, 'scripts', 'report_daily.py')
    const { stdout } = await execAsync(
      `python "${scriptPath}" --date ${today} --send-email`,
      { cwd: ROOT, timeout: 60000, env: { ...process.env } }
    )

    console.log(`[CRON report] OK — ${today}`)
    return NextResponse.json({ ok: true, date: today, output: stdout.slice(0, 200) })
  } catch (error: any) {
    console.error(`[CRON report] FAIL:`, error.message)
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
