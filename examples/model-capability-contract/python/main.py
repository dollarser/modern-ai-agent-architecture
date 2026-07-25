from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class ModelCapabilities:
    tool_calling: bool = True
    structured_output: bool = True
    streaming: bool = True
    cancel: bool = True


class FakeProvider:
    def __init__(self, capabilities: ModelCapabilities = ModelCapabilities()):
        self.capabilities = capabilities
        self.cancelled = False

    def complete(self, prompt: str, *, tools: list[dict] | None = None, schema: dict | None = None) -> dict:
        if tools and not self.capabilities.tool_calling:
            return {"success": False, "error_code": "capability_unsupported", "retryable": False}
        if schema and not self.capabilities.structured_output:
            return {"success": False, "error_code": "capability_unsupported", "retryable": False}
        return {"success": True, "output": prompt, "usage": {"input_tokens": len(prompt), "output_tokens": 1}}

    def stream(self, prompt: str) -> Iterator[str]:
        if not self.capabilities.streaming:
            raise RuntimeError("capability_unsupported")
        yield from prompt.split()

    def cancel(self) -> None:
        if not self.capabilities.cancel:
            raise RuntimeError("capability_unsupported")
        self.cancelled = True
