import asyncio

import pytest

from python_rag.app.tools.base import BaseTool
from python_rag.app.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo input text."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
        "additionalProperties": False,
    }
    timeout_ms = 1500
    permission_level = "user"

    async def run(self, arguments: dict) -> dict:
        return {"text": arguments["text"]}


class AdminTool(BaseTool):
    name = "admin.lookup"
    description = "Admin-only lookup."
    input_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    timeout_ms = 5000
    permission_level = "admin"

    async def run(self, arguments: dict) -> dict:
        return {"ok": True}


def test_tool_registry_can_register_and_query_tool():
    tool = EchoTool()
    registry = ToolRegistry()

    returned = registry.register(tool)

    assert returned is tool
    assert registry.has("echo")
    assert registry.get("echo") is tool
    assert registry.names() == ["echo"]
    assert asyncio.run(registry.get("echo").run({"text": "hello"})) == {
        "text": "hello",
    }


def test_tool_registry_can_register_tool_class():
    registry = ToolRegistry()

    tool = registry.register(EchoTool)

    assert isinstance(tool, EchoTool)
    assert registry.get("echo") is tool


def test_tool_registry_rejects_duplicate_names_without_overwrite():
    registry = ToolRegistry([EchoTool()])

    with pytest.raises(ValueError, match="tool already registered"):
        registry.register(EchoTool())

    replacement = EchoTool(description="Replacement echo.")
    registry.register(replacement, overwrite=True)

    assert registry.get("echo") is replacement
    assert registry.get("echo").description == "Replacement echo."


def test_tool_registry_filters_by_permission_level():
    registry = ToolRegistry([EchoTool(), AdminTool()])

    assert registry.names(permission_level="user") == ["echo"]
    assert registry.names(permission_level="admin") == ["admin.lookup"]
    assert registry.descriptors(permission_level="admin") == [
        {
            "name": "admin.lookup",
            "description": "Admin-only lookup.",
            "input_schema": AdminTool.input_schema,
            "timeout_ms": 5000,
            "permission_level": "admin",
        }
    ]


def test_tool_registry_exports_openai_compatible_tools_schema():
    registry = ToolRegistry([EchoTool()])

    schema = registry.export_openai_tools_schema()

    assert schema == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Echo input text.",
                "parameters": EchoTool.input_schema,
            },
        }
    ]
    assert "x_timeout_ms" not in schema[0]
    assert "x_permission_level" not in schema[0]


def test_tool_registry_can_export_runtime_fields_when_requested():
    registry = ToolRegistry([EchoTool(), AdminTool()])

    schema = registry.export_openai_tools_schema(
        permission_level="user",
        include_runtime_fields=True,
    )

    assert len(schema) == 1
    assert schema[0]["function"]["name"] == "echo"
    assert schema[0]["x_timeout_ms"] == 1500
    assert schema[0]["x_permission_level"] == "user"


def test_tool_registry_can_export_selected_names():
    registry = ToolRegistry([EchoTool(), AdminTool()])

    schema = registry.export_openai_tools_schema(names=["admin.lookup"])

    assert [item["function"]["name"] for item in schema] == ["admin.lookup"]


def test_base_tool_validates_required_fields():
    class InvalidTool(BaseTool):
        async def run(self, arguments: dict) -> dict:
            return {}

    with pytest.raises(ValueError, match="tool name is required"):
        InvalidTool()
