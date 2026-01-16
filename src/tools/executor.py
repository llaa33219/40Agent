"""
Tool Executor - Routes tool calls to appropriate handlers
"""

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from .base import BaseTool, ToolCall, ToolParser, ToolType
from .vm_tools import CursorMoveTool, CursorClickTool, TextInputTool, KeyInputTool
from .avatar_tools import I2DMotionTool

if TYPE_CHECKING:
    from src.vm.controller import VMController
    from src.stream.avatar import AvatarController

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Manages and executes tools"""

    def __init__(
        self,
        vm_controller: "VMController",
        avatar_controller: "AvatarController",
    ):
        self.vm = vm_controller
        self.avatar = avatar_controller
        self._tools: dict[ToolType, BaseTool] = {}
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Initialize all tools"""
        self._tools = {
            ToolType.CURSOR_MOVE: CursorMoveTool(self.vm),
            ToolType.CURSOR_CLICK: CursorClickTool(self.vm),
            ToolType.TEXT_INPUT: TextInputTool(self.vm),
            ToolType.KEY_INPUT: KeyInputTool(self.vm),
            ToolType.I2D_MOTION: I2DMotionTool(self.avatar),
        }

    def get_tool(self, tool_type: ToolType) -> BaseTool | None:
        """Get a tool by type"""
        return self._tools.get(tool_type)

    async def execute_tool(self, tool_call: ToolCall) -> dict[str, Any]:
        """Execute a single tool call"""
        tool = self.get_tool(tool_call.tool_type)

        if tool is None:
            return {"success": False, "error": f"Unknown tool: {tool_call.tool_type}"}

        if not tool.validate_args(tool_call.args):
            return {"success": False, "error": f"Invalid arguments: {tool_call.args}"}

        try:
            result = await tool.execute(tool_call.args)
            logger.info(f"Tool executed: {tool_call.tool_type.value} -> {result}")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_call.tool_type.value} - {e}")
            return {"success": False, "error": str(e)}

    async def execute_all(self, text: str) -> list[dict[str, Any]]:
        """Parse text and execute all found tool calls"""
        tool_calls = ToolParser.parse(text)
        results = []

        for tool_call in tool_calls:
            result = await self.execute_tool(tool_call)
            results.append({"tool": tool_call.tool_type.value, "args": tool_call.args, **result})

        return results

    def has_tool_calls(self, text: str) -> bool:
        """Check if text contains any tool calls"""
        return len(ToolParser.parse(text)) > 0

    def extract_speech(self, text: str) -> str:
        """Extract speech (non-tool) content"""
        return ToolParser.extract_speech(text)
