"""
Inochi2D Avatar Motion Tool
"""

from typing import Any, TYPE_CHECKING
from .base import BaseTool, ToolType

if TYPE_CHECKING:
    from src.stream.avatar import AvatarController


class I2DMotionTool(BaseTool):
    """Trigger Inochi2D avatar motion"""

    def __init__(self, avatar_controller: "AvatarController"):
        self.avatar = avatar_controller

    @property
    def tool_type(self) -> ToolType:
        return ToolType.I2D_MOTION

    def validate_args(self, args: str) -> bool:
        """Check if motion exists"""
        return len(args) > 0

    async def execute(self, args: str) -> dict[str, Any]:
        """Trigger motion"""
        motion_name = args.strip()
        success = await self.avatar.trigger_motion(motion_name)
        return {"success": success, "motion": motion_name}
