"""
VM Control Tools - cursor, keyboard, text input
"""

from typing import Any, TYPE_CHECKING
from .base import BaseTool, ToolType

if TYPE_CHECKING:
    from src.vm.controller import VMController


class CursorMoveTool(BaseTool):
    """Move cursor to specified coordinates"""

    def __init__(self, vm_controller: "VMController"):
        self.vm = vm_controller

    @property
    def tool_type(self) -> ToolType:
        return ToolType.CURSOR_MOVE

    def validate_args(self, args: str) -> bool:
        """Validate x,y coordinates"""
        try:
            parts = args.split(",")
            if len(parts) != 2:
                return False
            x, y = int(parts[0].strip()), int(parts[1].strip())
            return 0 <= x <= 1920 and 0 <= y <= 1080
        except (ValueError, IndexError):
            return False

    async def execute(self, args: str) -> dict[str, Any]:
        """Move cursor to x,y"""
        parts = args.split(",")
        x, y = int(parts[0].strip()), int(parts[1].strip())

        await self.vm.move_cursor(x, y)
        return {"success": True, "x": x, "y": y}


class CursorClickTool(BaseTool):
    """Click mouse button"""

    VALID_BUTTONS = {"left", "right", "middle"}

    def __init__(self, vm_controller: "VMController"):
        self.vm = vm_controller

    @property
    def tool_type(self) -> ToolType:
        return ToolType.CURSOR_CLICK

    def validate_args(self, args: str) -> bool:
        """Validate button name"""
        return args.lower().strip() in self.VALID_BUTTONS

    async def execute(self, args: str) -> dict[str, Any]:
        """Click specified button"""
        button = args.lower().strip()
        await self.vm.click(button)
        return {"success": True, "button": button}


class TextInputTool(BaseTool):
    """Type text into VM"""

    def __init__(self, vm_controller: "VMController"):
        self.vm = vm_controller

    @property
    def tool_type(self) -> ToolType:
        return ToolType.TEXT_INPUT

    def validate_args(self, args: str) -> bool:
        """Any text is valid"""
        return len(args) > 0

    async def execute(self, args: str) -> dict[str, Any]:
        """Type text"""
        await self.vm.type_text(args)
        return {"success": True, "text": args}


class KeyInputTool(BaseTool):
    """Press keyboard keys/combinations"""

    def __init__(self, vm_controller: "VMController"):
        self.vm = vm_controller

    @property
    def tool_type(self) -> ToolType:
        return ToolType.KEY_INPUT

    def validate_args(self, args: str) -> bool:
        """Validate key combination"""
        return len(args) > 0

    async def execute(self, args: str) -> dict[str, Any]:
        """Press keys"""
        await self.vm.press_keys(args)
        return {"success": True, "keys": args}
