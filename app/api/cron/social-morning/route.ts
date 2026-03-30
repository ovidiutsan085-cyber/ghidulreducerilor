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
    const scriptPath = path.join(ROOT, 'scripts', 'social_media_poster.py')
    const { stdout } = await execAsync(
      `python "${scriptPath}" --session morning`,
      { cwd: ROOL, timeout: 60000, env: { ...process.env } }
    )

    console.log(`[CRON social-morning] OK`)
    return NextResponse.json({ ok: true, session: 'morning', output: stdout.slice(0, 200) })
  } catch (error: any) {
    console.error(`[CRON social-morning] FAIL:`, error.message)
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
