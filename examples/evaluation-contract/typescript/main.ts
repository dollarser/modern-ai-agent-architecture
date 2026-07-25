export type Case = { caseId: string; allowedTools: string[]; forbiddenTools: string[]; expectedStatus: string; maxToolCalls: number; versions: Record<string, string> }
export type TraceEvent = { event?: string; tool?: string; status?: string }

export function runCase(c: Case, trace: TraceEvent[]): Record<string, unknown> {
  const tools = trace.filter((event) => event.event === "tool_call").map((event) => event.tool!)
  const forbidden = [...new Set(tools.filter((tool) => c.forbiddenTools.includes(tool)))].sort()
  const passed = trace.at(-1)?.status === c.expectedStatus &&
    tools.every((tool) => c.allowedTools.includes(tool)) && forbidden.length === 0 && tools.length <= c.maxToolCalls
  return { caseId: c.caseId, passed, toolCalls: tools, forbiddenTools: forbidden, versions: c.versions }
}
