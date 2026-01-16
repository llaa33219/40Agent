"""
Inochi2D Avatar Controller
Handles loading and controlling inochi2d (.inx) avatars
"""

import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class AvatarState:
    """Current state of the avatar"""

    loaded: bool = False
    current_motion: str | None = None
    available_motions: list[str] = field(default_factory=list)
    expression: str = "neutral"
    is_speaking: bool = False


class AvatarController:
    """
    Controller for Inochi2D avatars

    Note: Full Inochi2D integration requires the inochi2d runtime.
    This implementation provides the interface and can be extended
    with actual Inochi2D bindings.
    """

    def __init__(self, character_dir: Path):
        self.character_dir = character_dir
        self._state = AvatarState()
        self._current_avatar_path: Path | None = None
        self._motion_callbacks: list[Callable[[str], None]] = []
        self._lock = asyncio.Lock()

        # Default available motions
        self._default_motions = [
            "idle",
            "wave",
            "nod",
            "shake",
            "think",
            "happy",
            "surprised",
            "confused",
            "speaking",
        ]

    async def load_avatar(self, avatar_name: str) -> bool:
        """
        Load an avatar from the character directory

        Args:
            avatar_name: Name of the avatar file (without extension) or full filename
        """
        async with self._lock:
            # Find the avatar file
            if not avatar_name.endswith(".inx"):
                avatar_name = f"{avatar_name}.inx"

            avatar_path = self.character_dir / avatar_name

            if not avatar_path.exists():
                # Try to find any .inx file if specific one not found
                inx_files = list(self.character_dir.glob("*.inx"))
                if inx_files:
                    avatar_path = inx_files[0]
                    logger.info(f"Using first available avatar: {avatar_path.name}")
                else:
                    logger.warning(f"No avatar files found in {self.character_dir}")
                    # Continue anyway with default state for demo

            self._current_avatar_path = avatar_path
            self._state.loaded = True
            self._state.available_motions = self._default_motions.copy()
            self._state.current_motion = "idle"

            logger.info(f"Avatar loaded: {avatar_path}")
            return True

    async def trigger_motion(self, motion_name: str) -> bool:
        """
        Trigger an avatar motion

        Args:
            motion_name: Name of the motion to trigger
        """
        async with self._lock:
            if not self._state.loaded:
                logger.warning("No avatar loaded")
                return False

            motion_name = motion_name.lower().strip()

            # Accept any motion (for flexibility)
            self._state.current_motion = motion_name

            # Notify callbacks
            for callback in self._motion_callbacks:
                try:
                    callback(motion_name)
                except Exception as e:
                    logger.error(f"Motion callback error: {e}")

            logger.info(f"Motion triggered: {motion_name}")
            return True

    async def set_speaking(self, is_speaking: bool) -> None:
        """Set speaking state (for lip sync animation)"""
        async with self._lock:
            self._state.is_speaking = is_speaking
            if is_speaking:
                self._state.current_motion = "speaking"
            elif self._state.current_motion == "speaking":
                self._state.current_motion = "idle"

    async def set_expression(self, expression: str) -> None:
        """Set facial expression"""
        async with self._lock:
            self._state.expression = expression

    def on_motion(self, callback: Callable[[str], None]) -> None:
        """Register a callback for motion changes"""
        self._motion_callbacks.append(callback)

    @property
    def state(self) -> AvatarState:
        """Get current avatar state"""
        return self._state

    def get_state_for_web(self) -> dict:
        """Get avatar state as dict for web transmission"""
        return {
            "loaded": self._state.loaded,
            "currentMotion": self._state.current_motion,
            "availableMotions": self._state.available_motions,
            "expression": self._state.expression,
            "isSpeaking": self._state.is_speaking,
            "avatarPath": str(self._current_avatar_path) if self._current_avatar_path else None,
        }
