"""
VM Controller - QEMU/libvirt integration for VM control
"""

import asyncio
import logging
from typing import Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MouseButton(Enum):
    LEFT = 1
    MIDDLE = 2
    RIGHT = 4


# Key mapping for special keys
KEY_MAP = {
    "enter": "ret",
    "return": "ret",
    "backspace": "backspace",
    "tab": "tab",
    "escape": "esc",
    "esc": "esc",
    "space": "spc",
    "delete": "delete",
    "del": "delete",
    "insert": "insert",
    "ins": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "meta",
    "super": "meta",
    "win": "meta",
}


@dataclass
class VMState:
    """Current state of the VM"""

    is_running: bool = False
    cursor_x: int = 0
    cursor_y: int = 0
    screen_width: int = 1920
    screen_height: int = 1080


class VMController:
    """
    Controller for QEMU/libvirt VMs
    Provides cursor movement, clicking, keyboard input
    """

    def __init__(self, vm_name: str = "40agent-vm"):
        self.vm_name = vm_name
        self._conn = None
        self._domain = None
        self._state = VMState()
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to libvirt and get VM domain"""
        try:
            import libvirt

            # Connect to QEMU system
            self._conn = libvirt.open("qemu:///system")
            if self._conn is None:
                logger.error("Failed to connect to QEMU")
                return False

            # Look up the domain
            try:
                self._domain = self._conn.lookupByName(self.vm_name)
                self._state.is_running = self._domain.isActive()
                logger.info(f"Connected to VM: {self.vm_name}, running: {self._state.is_running}")
                return True
            except libvirt.libvirtError:
                logger.warning(f"VM '{self.vm_name}' not found. Will run in simulation mode.")
                return False

        except ImportError:
            logger.warning("libvirt-python not installed. Running in simulation mode.")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to VM: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from libvirt"""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._domain = None

    async def _send_qmp_command(self, command: str, **kwargs) -> Any:
        """Send QMP command to QEMU (via libvirt)"""
        if not self._domain:
            logger.debug(f"Simulation: QMP command {command} with {kwargs}")
            return {"return": {}}

        try:
            import json

            cmd = {"execute": command, "arguments": kwargs} if kwargs else {"execute": command}
            result = self._domain.qemuMonitorCommand(json.dumps(cmd), 0)
            return json.loads(result)
        except Exception as e:
            logger.error(f"QMP command failed: {e}")
            return None

    async def move_cursor(self, x: int, y: int) -> None:
        """Move cursor to absolute position"""
        async with self._lock:
            # Clamp coordinates
            x = max(0, min(x, self._state.screen_width - 1))
            y = max(0, min(y, self._state.screen_height - 1))

            self._state.cursor_x = x
            self._state.cursor_y = y

            if self._domain:
                # Use input-send-event for absolute positioning
                await self._send_qmp_command(
                    "input-send-event",
                    events=[
                        {"type": "abs", "data": {"axis": "x", "value": x}},
                        {"type": "abs", "data": {"axis": "y", "value": y}},
                    ],
                )
            else:
                logger.debug(f"Simulation: Move cursor to ({x}, {y})")

    async def click(self, button: str = "left") -> None:
        """Click mouse button"""
        async with self._lock:
            button_code = {
                "left": 0,
                "middle": 1,
                "right": 2,
            }.get(button.lower(), 0)

            if self._domain:
                # Press
                await self._send_qmp_command(
                    "input-send-event",
                    events=[{"type": "btn", "data": {"button": f"mouse_{button}", "down": True}}],
                )
                await asyncio.sleep(0.05)
                # Release
                await self._send_qmp_command(
                    "input-send-event",
                    events=[{"type": "btn", "data": {"button": f"mouse_{button}", "down": False}}],
                )
            else:
                logger.debug(
                    f"Simulation: Click {button} at ({self._state.cursor_x}, {self._state.cursor_y})"
                )

    async def type_text(self, text: str) -> None:
        """Type text character by character"""
        async with self._lock:
            for char in text:
                await self._send_key(char)
                await asyncio.sleep(0.02)  # Small delay between characters

    async def _send_key(self, key: str, hold: bool = False) -> None:
        """Send a single key press"""
        if self._domain:
            # Map special characters
            qcode = KEY_MAP.get(key.lower(), key)

            await self._send_qmp_command(
                "input-send-event",
                events=[
                    {"type": "key", "data": {"key": {"type": "qcode", "data": qcode}, "down": True}}
                ],
            )
            if not hold:
                await asyncio.sleep(0.02)
                await self._send_qmp_command(
                    "input-send-event",
                    events=[
                        {
                            "type": "key",
                            "data": {"key": {"type": "qcode", "data": qcode}, "down": False},
                        }
                    ],
                )
        else:
            logger.debug(f"Simulation: Key press '{key}'")

    async def press_keys(self, keys: str) -> None:
        """
        Press key combination (e.g., "ctrl+c", "alt+tab")
        """
        async with self._lock:
            parts = [k.strip() for k in keys.lower().split("+")]

            # Press modifier keys first
            modifiers = []
            for part in parts:
                if part in ("ctrl", "alt", "shift", "meta", "super", "win"):
                    modifiers.append(part)

            # Hold modifiers
            for mod in modifiers:
                await self._send_key(mod, hold=True)

            # Press non-modifier keys
            for part in parts:
                if part not in modifiers:
                    await self._send_key(part)

            # Release modifiers
            for mod in reversed(modifiers):
                if self._domain:
                    qcode = KEY_MAP.get(mod, mod)
                    await self._send_qmp_command(
                        "input-send-event",
                        events=[
                            {
                                "type": "key",
                                "data": {"key": {"type": "qcode", "data": qcode}, "down": False},
                            }
                        ],
                    )

    @property
    def state(self) -> VMState:
        """Get current VM state"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected to VM"""
        return self._domain is not None
