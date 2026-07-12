/** 第 16 章 DatabaseReviewAgent 演示入口。 */

import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { pathToFileURL } from "node:url"

export * from "./assembly.js"
export * from "./application.js"
export * from "./coding-scenario.js"
export * from "./database-review-scenario.js"
export * from "./installed-adapters.js"
import { AutoApproveGate } from "./assembly.js"
import { DatabaseReviewAgent } from "./database-review-scenario.js"

async function demo(): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "database-review-agent-"))
  try {
    const checkpoint = join(directory, "checkpoints.json")
    const task = "查找数据库配置并给出变更建议"
    const first = await new DatabaseReviewAgent(
      checkpoint, { interruptAfterSteps: 2 }, { approval: new AutoApproveGate() },
    )
      .run(task, "demo-run")
    console.log(JSON.stringify(first, null, 2))
    const completed = await new DatabaseReviewAgent(
      checkpoint, {}, { approval: new AutoApproveGate() },
    ).run(task, "demo-run")
    console.log(JSON.stringify(completed, null, 2))
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await demo()
