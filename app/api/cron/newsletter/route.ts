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

  const type = req.nextUrl.searchParams.get('type') || 'daily'

  try {
    const scriptPath = path.join(ROOT, 'scripts', 'newsletter.py')
    const { stdout, stderr } = await execAsync(
      `python "${scriptPath}" --type ${type}`,
      { cwd: ROOL, timeout: 60000, env: { ...process.env } }
    )

    const success = stdout.includes('trimis cu succes')
    console.log(`[CRON newsletter] ${success ? 'OK' : 'FAIL'} — type: ${type}`)
    return NextResponse.json({ ok: success, type, output: stdout.slice(0, 200) })
  } catch (error: any) {
    console.error(`[CRON newsletter] FAIL:`, error.message)
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
