from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, Optional


DEFAULT_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

__all__ = [
    "BaseTool",
    "DEFAULT_INPUT_SCHEMA",
]


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = DEFAULT_INPUT_SCHEMA
    timeout_ms: int = 30000
    permission_level: str = "user"

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        timeout_ms: Optional[int] = None,
        permission_level: Optional[str] = None,
    ):
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if input_schema is not None:
            self.input_schema = input_schema
        if timeout_ms is not None:
            self.timeout_ms = timeout_ms
        if permission_level is not None:
            self.permission_level = permission_level

        self._validate_definition()

    def _validate_definition(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("tool name is required")
        self.name = self.name.strip()

        if not isinstance(self.description, str):
            raise ValueError("tool description must be a string")
        self.description = self.description.strip()

        if not isinstance(self.input_schema, dict):
            raise ValueError("tool input_schema must be a dict")

        if not isinstance(self.timeout_ms, int) or self.timeout_ms <= 0:
            raise ValueError("tool timeout_ms must be a positive integer")

        if not isinstance(self.permission_level, str) or not self.permission_level.strip():
            raise ValueError("tool permission_level is required")
        self.permission_level = self.permission_level.strip()

    def to_openai_tool_schema(self, include_runtime_fields: bool = False) -> Dict[str, Any]:
        schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": deepcopy(self.input_schema or DEFAULT_INPUT_SCHEMA),
            },
        }

        if include_runtime_fields:
            schema["x_timeout_ms"] = self.timeout_ms
            schema["x_permission_level"] = self.permission_level

        return schema

    def to_descriptor(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": deepcopy(self.input_schema or DEFAULT_INPUT_SCHEMA),
            "timeout_ms": self.timeout_ms,
            "permission_level": self.permission_level,
        }

    @abstractmethod
    async def run(self, arguments: dict) -> dict:
        raise NotImplementedError
