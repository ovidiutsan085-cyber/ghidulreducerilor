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
    const scriptPath = path.join(ROOT, 'scripts', 'link_checker.py')
    const { stdout } = await execAsync(
      `python "${scriptPath}" --mode quick`,
      { cwd: ROOT, timeout: 120000, env: { ...process.env } }
    )

    console.log(`[CRON link-check] OK`)
    return NextResponse.json({ ok: true, output: stdout.slice(0, 300) })
  } catch (error: any) {
    console.error(`[CRON link-check] FAIL:`, error.message)
    return NextResponse.json({ ok: false, error: error.message?.slice(0, 200) }, { status: 500 })
  }
}
