export type MemoryRecord = {
  key: string; content: string; tenantId: string; subjectId: string
  provenance: "user_input" | "tool_result" | "conversation_compaction"
  trust: "untrusted" | "verified" | "user_confirmed"
  consent: boolean; retentionUntil?: number
}

export class GovernedMemory {
  private readonly records = new Map<string, MemoryRecord>()
  put(record: MemoryRecord): void {
    if (!record.tenantId || !record.subjectId) throw new Error("Memory 必须绑定 tenantId 和 subjectId")
    if (record.key.startsWith("preference/") && !record.consent) throw new Error("用户偏好写入需要明确 consent")
    this.records.set(`${record.tenantId}:${record.subjectId}:${record.key}`, record)
  }
  get(key: string, tenantId: string, subjectId: string): MemoryRecord | undefined {
    const storageKey = `${tenantId}:${subjectId}:${key}`
    const record = this.records.get(storageKey)
    if (record?.retentionUntil !== undefined && record.retentionUntil <= Date.now() / 1000) {
      this.records.delete(storageKey); return undefined
    }
    return record
  }
  forget(key: string, tenantId: string, subjectId: string): boolean {
    return this.records.delete(`${tenantId}:${subjectId}:${key}`)
  }
}

export type ArtifactView = { artifactId: string; summary: string; mediaType: string; checksum: string }
export function renderArtifact(view: ArtifactView): string {
  return `[artifact:${view.artifactId} ${view.mediaType} sha256=${view.checksum}] ${view.summary}`
}
export function estimateTokens(text: string): number { return Math.max(1, Math.ceil(text.length / 4)) }
export function buildContext(system: string, history: string[], artifacts: ArtifactView[], tokenBudget: number): string[] {
  const fixed = [system, ...artifacts.map(renderArtifact)]
  let used = fixed.reduce((sum, item) => sum + estimateTokens(item), 0)
  if (used > tokenBudget) throw new Error("固定 Context 已超过 token budget")
  const selected: string[] = []
  for (const item of [...history].reverse()) {
    const cost = estimateTokens(item)
    if (used + cost > tokenBudget) break
    selected.unshift(item); used += cost
  }
  return [...fixed, ...selected]
}
