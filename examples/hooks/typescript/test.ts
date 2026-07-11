import { AgentWithHooks, type ToolResult } from "./main.js";

const assert = (condition: boolean, message: string): void => {
  if (!condition) throw new Error(message);
};

const guarded = new AgentWithHooks();
guarded.registerCustomHook("before_tool_call", (toolName: unknown) => {
  if (String(toolName) !== "read_file") throw new Error("denied");
});
assert(guarded.run("危险任务", "delete_all") === null, "guard must block");

const masking = new AgentWithHooks();
masking.registerCustomHook("after_tool_call", (_name: unknown, value: unknown) => {
  const result = value as ToolResult;
  result.content = result.content.replace("sk-demo", "sk-***");
});
const masked = masking.run("读取", "read_file");
assert(masked?.content.includes("sk-***") === true, "after hook result must propagate");

const isolated = new AgentWithHooks();
isolated.registerCustomHook("after_tool_call", () => { throw new Error("metrics down"); });
assert(isolated.run("读取", "read_file")?.success === true, "observer failure must isolate");

console.log("hooks TypeScript tests: OK");
