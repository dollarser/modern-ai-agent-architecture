"""教学用 JSON Schema 子集：递归校验，未知关键字与错误定义均拒绝。"""

import json
import math
from typing import Any

KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "enum",
            "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
            "title", "description", "default"}
TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def check_schema(schema: Any) -> None:
    if not isinstance(schema, dict) or set(schema) - KEYWORDS:
        raise ValueError("不支持的 Schema 关键字或定义")
    if "type" in schema and schema["type"] not in TYPES:
        raise ValueError("不支持的 Schema type")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("Schema properties 必须是对象")
    for value in properties.values():
        check_schema(value)
    if "items" in schema:
        check_schema(schema["items"])
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise ValueError("additionalProperties 仅支持布尔值")
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError("Schema required 必须是字符串数组")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("Schema enum 必须是非空数组")
    for key in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
        if key in schema:
            value = schema[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"Schema {key} 必须是有限数值")
            if key not in {"minimum", "maximum"} and (value < 0 or int(value) != value):
                raise ValueError(f"Schema {key} 必须是非负整数")


def equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a == b


def check_json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)) and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            check_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            check_json(item)
        return
    raise ValueError("Tool 参数必须是 JSON 值")


def validate(schema: dict[str, Any], value: Any) -> None:
    check_schema(schema)
    # 不接受 NaN、非 JSON 对象或循环引用。
    json.dumps(value, allow_nan=False)
    check_json(value)
    _validate(schema, value)


def _validate(schema: dict[str, Any], value: Any) -> None:
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    matches = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "number": numeric,
        "integer": numeric and value % 1 == 0,
        "boolean": isinstance(value, bool), "null": value is None,
    }
    if "type" in schema and not matches[schema["type"]]:
        raise TypeError("Tool 参数类型错误")
    if "enum" in schema and not any(
        equal(value, item)
        for item in schema["enum"]
    ):
        raise ValueError("Tool 参数不在允许值中")
    if numeric:
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ValueError("Tool 参数超出数值范围")
    if isinstance(value, (str, list)):
        lower, upper = ("minLength", "maxLength") if isinstance(value, str) else ("minItems", "maxItems")
        if len(value) < schema.get(lower, 0) or len(value) > schema.get(upper, math.inf):
            raise ValueError("Tool 参数超出长度范围")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            raise ValueError("Tool 参数缺少必填字段")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                _validate(properties[key], item)
            elif schema.get("additionalProperties") is False:
                raise ValueError("Tool 参数包含未知字段")
    if isinstance(value, list) and "items" in schema:
        for item in value:
            _validate(schema["items"], item)
