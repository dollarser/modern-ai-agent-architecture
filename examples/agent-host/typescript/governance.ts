/** 运行治理：统一策略决策与可复现能力快照工具。 */

import { createHash } from "node:crypto"

export enum ConfigScope {
  Managed = "managed", Project = "project", User = "user",
  Local = "local", Session = "session",
}
export type PolicyLayer = { scope: ConfigScope; allow?: Set<string>; deny?: Set<string> }
export const mergePolicyLayers = (layers: PolicyLayer[]): {
  allowed: Set<string>; denied: Set<string>
} => {
  const allowed = new Set<string>()
  const denied = new Set<string>()
  for (const layer of layers) {
    layer.allow?.forEach((item) => allowed.add(item))
    layer.deny?.forEach((item) => denied.add(item))
  }
  denied.forEach((item) => allowed.delete(item))
  return { allowed, denied }
}

export enum PolicyDecision { Allow = "allow", Ask = "ask", Deny = "deny" }
export type PolicyRequest = {
  subject: string
  capability: string
  arguments: Record<string, unknown>
  resource: string
  runId: string
  source: string
  risk: "normal" | "high"
}
export interface PolicyEngine {
  version: string
  evaluate(request: PolicyRequest): PolicyDecision
}
export class DefaultPolicyEngine implements PolicyEngine {
  readonly version = "default-policy-v1"
  readonly allowedTools: Set<string>
  readonly deniedTools: Set<string>
  constructor(allowedTools: Set<string>, layers: PolicyLayer[] = []) {
    const merged = mergePolicyLayers(layers)
    this.allowedTools = new Set([...allowedTools, ...merged.allowed])
    this.deniedTools = merged.denied
  }
  evaluate(request: PolicyRequest): PolicyDecision {
    if (this.deniedTools.has(request.capability) || !this.allowedTools.has(request.capability)) {
      return PolicyDecision.Deny
    }
    return request.risk === "high" ? PolicyDecision.Ask : PolicyDecision.Allow
  }
}

export type CapabilitySnapshot = {
  tools: Array<Record<string, unknown>>
  skills: Array<Record<string, unknown>>
  policyVersion: string
  config: Record<string, unknown>
  snapshotHash: string
}

export const sha256Text = (value: string): string =>
  createHash("sha256").update(value).digest("hex")

export const withSnapshotHash = (
  body: Omit<CapabilitySnapshot, "snapshotHash">,
): CapabilitySnapshot => ({ ...body, snapshotHash: sha256Text(JSON.stringify(body)) })
