import { DynamicToolRegistry, safeCalculate } from "./main.js";

function equal(actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error(`expected ${String(expected)}, got ${String(actual)}`);
}
function deepEqual(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error("values differ");
}
function throws(fn: () => unknown, expectedMessage?: string): void {
  try { fn(); } catch (error) {
    if (!expectedMessage || String(error).includes(expectedMessage)) return;
    throw new Error(`unexpected error: ${String(error)}`);
  }
  throw new Error("expected function to throw");
}

const tool = () => ({
  name: "echo",
  description: "回显文本",
  parameters: { type: "object", properties: { value: { type: "string" } }, required: ["value"] },
  handler: (args: Record<string, unknown>) => ({ success: true, value: args.value }),
  tags: ["test"], version: "1.0.0",
});

const registry = new DynamicToolRegistry();
registry.register(tool());
deepEqual(registry.execute("echo", { value: "ok" }), { success: true, value: "ok" });
equal(registry.execute("echo", {}).error_code, "invalid_arguments");
equal(registry.execute("echo", { value: 1 }).error_code, "invalid_arguments");
equal(registry.execute("echo", { value: "ok", extra: true }).error_code, "invalid_arguments");
throws(() => registry.register(tool()), "已注册");
equal(safeCalculate("(2 + 3) * 4"), 20);
throws(() => safeCalculate("globalThis.process.exit()"));
throws(() => safeCalculate("2 ** 11"));
console.log("tool registry TypeScript tests: OK");
