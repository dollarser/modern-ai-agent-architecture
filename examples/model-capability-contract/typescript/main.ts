export type ModelCapabilities = { toolCalling: boolean; structuredOutput: boolean; streaming: boolean; cancel: boolean }

export class FakeProvider {
  cancelled = false
  constructor(public readonly capabilities: ModelCapabilities = { toolCalling: true, structuredOutput: true, streaming: true, cancel: true }) {}
  complete(prompt: string, options: { tools?: unknown[]; schema?: unknown } = {}): Record<string, unknown> {
    if (options.tools && !this.capabilities.toolCalling || options.schema && !this.capabilities.structuredOutput) {
      return { success: false, error_code: "capability_unsupported", retryable: false }
    }
    return { success: true, output: prompt, usage: { inputTokens: prompt.length, outputTokens: 1 } }
  }
  *stream(prompt: string): Generator<string> {
    if (!this.capabilities.streaming) throw new Error("capability_unsupported")
    yield* prompt.split(" ")
  }
  cancel(): void {
    if (!this.capabilities.cancel) throw new Error("capability_unsupported")
    this.cancelled = true
  }
}
