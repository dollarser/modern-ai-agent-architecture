/** 单进程教学存储的安全原子替换；不提供跨进程事务或目录竞态隔离。 */
import { chmodSync, mkdtempSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"

export const atomicWriteText = (path: string, content: string, preserveMode = false): void => {
  const directory = mkdtempSync(join(dirname(path), ".agent-write-"))
  try {
    const temporary = join(directory, "content")
    writeFileSync(temporary, content, { encoding: "utf8", flag: "wx", mode: 0o600 })
    if (preserveMode) chmodSync(temporary, statSync(path).mode & 0o777)
    renameSync(temporary, path)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}
