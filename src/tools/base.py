"""
Base tool definitions for 40Agent
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolType(Enum):
    """Available tool types"""

    CURSOR_MOVE = "cursor-move"
    CURSOR_CLICK = "cursor-click"
    TEXT_INPUT = "text-input"
    KEY_INPUT = "key-input"
    I2D_MOTION = "i2d-motion"


@dataclass
class ToolCall:
    """Represents a parsed tool call"""

    tool_type: ToolType
    args: str
    raw: str


class BaseTool(ABC):
    """Base class for all tools"""

    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Return the tool type"""
        pass

    @abstractmethod
    async def execute(self, args: str) -> dict[str, Any]:
        """Execute the tool with given arguments"""
        pass

    @abstractmethod
    def validate_args(self, args: str) -> bool:
        """Validate the arguments"""
        pass


class ToolParser:
    """Parser for extracting tool calls from text"""

    # Pattern to match <tool name="tool-name">args</tool>
    TOOL_PATTERN = re.compile(r'<tool\s+name="([^"]+)">(.*?)</tool>', re.DOTALL)

    # Alternative pattern: <tool-name>args</tool-name>
    ALT_PATTERN = re.compile(
        r"<(cursor-move|cursor-click|text-input|key-input|i2d-motion)>(.*?)</\1>", re.DOTALL
    )

    @classmethod
    def parse(cls, text: str) -> list[ToolCall]:
        """Parse text and extract all tool calls"""
        tool_calls = []

        # Try main pattern first
        for match in cls.TOOL_PATTERN.finditer(text):
            tool_name = match.group(1)
            args = match.group(2).strip()
            raw = match.group(0)

            try:
                tool_type = ToolType(tool_name)
                tool_calls.append(ToolCall(tool_type=tool_type, args=args, raw=raw))
            except ValueError:
                # Unknown tool type, skip
                continue

        # Try alternative pattern
        for match in cls.ALT_PATTERN.finditer(text):
            tool_name = match.group(1)
            args = match.group(2).strip()
            raw = match.group(0)

            try:
                tool_type = ToolType(tool_name)
                # Avoid duplicates
                if not any(tc.raw == raw for tc in tool_calls):
                    tool_calls.append(ToolCall(tool_type=tool_type, args=args, raw=raw))
            except ValueError:
                continue

        return tool_calls

    @classmethod
    def extract_speech(cls, text: str) -> str:
        """Extract non-tool text (speech) from the response"""
        # Remove all tool calls
        result = cls.TOOL_PATTERN.sub("", text)
        result = cls.ALT_PATTERN.sub("", result)
        return result.strip()
