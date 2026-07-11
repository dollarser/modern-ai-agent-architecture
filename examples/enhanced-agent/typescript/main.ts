/** 第 16 章 Enhanced Agent 入口。完整组装见 assembly.ts。 */

import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { pathToFileURL } from "node:url"

export * from "./assembly.js"
import { EnhancedAgent } from "./assembly.js"

async function demo(): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "enhanced-agent-"))
  try {
    const checkpoint = join(directory, "checkpoints.json")
    const task = "查找数据库配置并给出变更建议"
    const first = await new EnhancedAgent(checkpoint, { interruptAfterSteps: 2 })
      .run(task, "demo-session")
    console.log(JSON.stringify(first, null, 2))
    const completed = await new EnhancedAgent(checkpoint).run(task, "demo-session")
    console.log(JSON.stringify(completed, null, 2))
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await demo()
