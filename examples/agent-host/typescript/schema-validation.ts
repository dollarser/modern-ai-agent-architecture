/** 教学用 JSON Schema 子集；未知关键字和错误定义均拒绝。 */
type Schema = Record<string, unknown>
const keywords = new Set(["type", "properties", "required", "additionalProperties", "items", "enum",
  "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "title", "description", "default"])
const types = new Set(["object", "array", "string", "number", "integer", "boolean", "null"])
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const checkSchema = (schema: unknown): void => {
  if (!object(schema) || Object.keys(schema).some((key) => !keywords.has(key))) {
    throw new Error("不支持的 Schema 关键字或定义")
  }
  if (schema.type !== undefined && !types.has(String(schema.type))) throw new Error("不支持的 Schema type")
  if (schema.properties !== undefined && !object(schema.properties)) throw new Error("Schema properties 必须是对象")
  Object.values((schema.properties ?? {}) as Schema).forEach(checkSchema)
  if (schema.items !== undefined) checkSchema(schema.items)
  if (schema.additionalProperties !== undefined && typeof schema.additionalProperties !== "boolean") {
    throw new Error("additionalProperties 仅支持布尔值")
  }
  if (schema.required !== undefined && (!Array.isArray(schema.required) ||
    !schema.required.every((item) => typeof item === "string"))) throw new Error("Schema required 必须是字符串数组")
  if (schema.enum !== undefined && (!Array.isArray(schema.enum) || !schema.enum.length)) throw new Error("Schema enum 必须是非空数组")
  for (const key of ["minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"]) {
    const value = schema[key]
    if (value !== undefined && (typeof value !== "number" || !Number.isFinite(value) ||
      (!["minimum", "maximum"].includes(key) && (!Number.isInteger(value) || value < 0)))) {
      throw new Error(`Schema ${key} 数值无效`)
    }
  }
}
const jsonValue = (value: unknown): void => {
  if (value === null || typeof value === "string" || typeof value === "boolean") return
  if (typeof value === "number" && Number.isFinite(value)) return
  if (Array.isArray(value)) { value.forEach(jsonValue); return }
  if (object(value)) { Object.values(value).forEach(jsonValue); return }
  throw new Error("Tool 参数必须是 JSON 值")
}
const equal = (a: unknown, b: unknown): boolean => {
  if (a === b) return true
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => equal(v, b[i]))
  if (object(a) && object(b)) return Object.keys(a).length === Object.keys(b).length &&
    Object.keys(a).every((key) => Object.hasOwn(b, key) && equal(a[key], b[key]))
  return false
}
const validateValue = (schema: Schema, value: unknown): void => {
  const numeric = typeof value === "number" && Number.isFinite(value)
  const matches: Record<string, boolean> = {
    object: object(value), array: Array.isArray(value), string: typeof value === "string",
    number: numeric, integer: numeric && Number.isInteger(value),
    boolean: typeof value === "boolean", null: value === null,
  }
  if (schema.type !== undefined && !matches[String(schema.type)]) throw new Error("Tool 参数类型错误")
  if (Array.isArray(schema.enum) && !schema.enum.some((item) => equal(item, value))) throw new Error("Tool 参数不在允许值中")
  if (numeric && (Number(value) < Number(schema.minimum ?? -Infinity) || Number(value) > Number(schema.maximum ?? Infinity))) {
    throw new Error("Tool 参数超出数值范围")
  }
  if (typeof value === "string" || Array.isArray(value)) {
    const [lower, upper] = typeof value === "string" ? ["minLength", "maxLength"] : ["minItems", "maxItems"]
    const length = typeof value === "string" ? Array.from(value).length : value.length
    if (length < Number(schema[lower] ?? 0) || length > Number(schema[upper] ?? Infinity)) throw new Error("Tool 参数超出长度范围")
  }
  if (object(value)) {
    if (((schema.required ?? []) as string[]).some((key) => !Object.hasOwn(value, key))) throw new Error("Tool 参数缺少必填字段")
    const properties = (schema.properties ?? {}) as Record<string, Schema>
    for (const [key, item] of Object.entries(value)) {
      if (Object.hasOwn(properties, key)) validateValue(properties[key], item)
      else if (schema.additionalProperties === false) throw new Error("Tool 参数包含未知字段")
    }
  }
  if (Array.isArray(value) && schema.items) value.forEach((item) => validateValue(schema.items as Schema, item))
}
export const validate = (schema: Schema, value: unknown): void => {
  checkSchema(schema)
  JSON.stringify(value) // 拒绝循环引用。
  jsonValue(value)
  validateValue(schema, value)
}
