"""
VM Controller - Direct QEMU QMP integration for VM control
"""

import asyncio
import json
import logging
import socket
from typing import Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MouseButton(Enum):
    LEFT = 1
    MIDDLE = 2
    RIGHT = 4


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
    is_running: bool = False
    cursor_x: int = 0
    cursor_y: int = 0
    screen_width: int = 1920
    screen_height: int = 1080


class VMController:
    """
    Controller for QEMU VMs via direct QMP socket connection.
    No libvirt required - just qemu-full.
    """

    def __init__(self, vm_name: str = "40agent-vm", qmp_socket: str | None = None):
        self.vm_name = vm_name
        self.qmp_socket = qmp_socket or f"/tmp/qemu-{vm_name}-qmp.sock"
        self._sock: socket.socket | None = None
        self._state = VMState()
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> bool:
        try:
            sock_path = Path(self.qmp_socket)
            if not sock_path.exists():
                logger.warning(
                    f"QMP socket not found: {self.qmp_socket}. Running in simulation mode."
                )
                logger.info(f"Start QEMU with: -qmp unix:{self.qmp_socket},server,nowait")
                return False

            self._reader, self._writer = await asyncio.open_unix_connection(self.qmp_socket)

            greeting = await self._reader.readline()
            logger.debug(f"QMP greeting: {greeting.decode()}")

            await self._send_qmp_command("qmp_capabilities")

            self._state.is_running = True
            logger.info(f"Connected to QEMU via QMP: {self.qmp_socket}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to QMP: {e}")
            return False

    async def disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def _send_qmp_command(self, command: str, **kwargs) -> Any:
        if not self._writer or not self._reader:
            logger.debug(f"Simulation: QMP command {command} with {kwargs}")
            return {"return": {}}

        try:
            cmd = {"execute": command}
            if kwargs:
                cmd["arguments"] = kwargs

            self._writer.write(json.dumps(cmd).encode() + b"\n")
            await self._writer.drain()

            response = await self._reader.readline()
            return json.loads(response.decode())
        except Exception as e:
            logger.error(f"QMP command failed: {e}")
            return None

    async def move_cursor(self, x: int, y: int) -> None:
        async with self._lock:
            x = max(0, min(x, self._state.screen_width - 1))
            y = max(0, min(y, self._state.screen_height - 1))

            self._state.cursor_x = x
            self._state.cursor_y = y

            if self._writer:
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
        async with self._lock:
            if self._writer:
                await self._send_qmp_command(
                    "input-send-event",
                    events=[{"type": "btn", "data": {"button": f"mouse_{button}", "down": True}}],
                )
                await asyncio.sleep(0.05)
                await self._send_qmp_command(
                    "input-send-event",
                    events=[{"type": "btn", "data": {"button": f"mouse_{button}", "down": False}}],
                )
            else:
                logger.debug(
                    f"Simulation: Click {button} at ({self._state.cursor_x}, {self._state.cursor_y})"
                )

    async def type_text(self, text: str) -> None:
        async with self._lock:
            for char in text:
                await self._send_key(char)
                await asyncio.sleep(0.02)

    async def _send_key(self, key: str, hold: bool = False) -> None:
        if self._writer:
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
        async with self._lock:
            parts = [k.strip() for k in keys.lower().split("+")]

            modifiers = []
            for part in parts:
                if part in ("ctrl", "alt", "shift", "meta", "super", "win"):
                    modifiers.append(part)

            for mod in modifiers:
                await self._send_key(mod, hold=True)

            for part in parts:
                if part not in modifiers:
                    await self._send_key(part)

            for mod in reversed(modifiers):
                if self._writer:
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
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._writer is not None
