from typing import Dict, Iterable, List, Optional, Type, Union

from python_rag.app.tools.base import BaseTool


ToolSpec = Union[BaseTool, Type[BaseTool]]

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "default_registry",
]


class ToolRegistry:
    def __init__(self, tools: Optional[Iterable[ToolSpec]] = None):
        self._tools: Dict[str, BaseTool] = {}
        for tool in tools or []:
            self.register(tool)

    def _coerce_tool(self, tool: ToolSpec) -> BaseTool:
        if isinstance(tool, type) and issubclass(tool, BaseTool):
            return tool()
        if isinstance(tool, BaseTool):
            return tool
        raise TypeError("tool must be a BaseTool instance or subclass")

    def register(self, tool: ToolSpec, overwrite: bool = False) -> BaseTool:
        tool_instance = self._coerce_tool(tool)

        if tool_instance.name in self._tools and not overwrite:
            raise ValueError("tool already registered: {0}".format(tool_instance.name))

        self._tools[tool_instance.name] = tool_instance
        return tool_instance

    def register_many(self, tools: Iterable[ToolSpec], overwrite: bool = False) -> None:
        for tool in tools:
            self.register(tool, overwrite=overwrite)

    def unregister(self, name: str) -> BaseTool:
        try:
            return self._tools.pop(name)
        except KeyError:
            raise KeyError("tool not found: {0}".format(name))

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError("tool not found: {0}".format(name))

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self, permission_level: Optional[str] = None) -> List[str]:
        return [tool.name for tool in self.list(permission_level=permission_level)]

    def list(self, permission_level: Optional[str] = None) -> List[BaseTool]:
        tools = list(self._tools.values())
        if permission_level is None:
            return tools
        return [
            tool
            for tool in tools
            if tool.permission_level == permission_level
        ]

    def descriptors(self, permission_level: Optional[str] = None) -> List[dict]:
        return [
            tool.to_descriptor()
            for tool in self.list(permission_level=permission_level)
        ]

    def export_openai_tools_schema(
        self,
        names: Optional[Iterable[str]] = None,
        permission_level: Optional[str] = None,
        include_runtime_fields: bool = False,
    ) -> List[dict]:
        if names is None:
            tools = self.list(permission_level=permission_level)
        else:
            tools = [self.get(name) for name in names]
            if permission_level is not None:
                tools = [
                    tool
                    for tool in tools
                    if tool.permission_level == permission_level
                ]

        return [
            tool.to_openai_tool_schema(
                include_runtime_fields=include_runtime_fields,
            )
            for tool in tools
        ]


default_registry = ToolRegistry()
