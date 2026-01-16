"""
VM Screen Capture - Capture VM display via QEMU QMP screendump
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from typing import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    width: int
    height: int
    timestamp: float
    frame_number: int


class VMScreenCapture:
    """
    Captures VM screen via QEMU QMP screendump command.
    No libvirt required - just qemu-full.
    """

    def __init__(
        self,
        vm_name: str,
        qmp_socket: str | None = None,
        native_width: int = 1920,
        native_height: int = 1080,
        native_fps: int = 30,
    ):
        self.vm_name = vm_name
        self.qmp_socket = qmp_socket or f"/tmp/qemu-{vm_name}-qmp.sock"
        self.native_width = native_width
        self.native_height = native_height
        self.native_fps = native_fps

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._frame_count = 0
        self._last_frame: np.ndarray | None = None
        self._tmp_dir = tempfile.mkdtemp(prefix="40agent-")

    async def connect(self) -> bool:
        try:
            sock_path = Path(self.qmp_socket)
            if not sock_path.exists():
                logger.warning(f"QMP socket not found: {self.qmp_socket}. Using test pattern.")
                logger.info(f"Start QEMU with: -qmp unix:{self.qmp_socket},server,nowait")
                return False

            self._reader, self._writer = await asyncio.open_unix_connection(self.qmp_socket)

            greeting = await self._reader.readline()
            logger.debug(f"QMP greeting: {greeting.decode()}")

            await self._send_qmp_command("qmp_capabilities")

            logger.info(f"Screen capture connected via QMP: {self.qmp_socket}")
            return True

        except Exception as e:
            logger.error(f"Screen capture connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

        if os.path.exists(self._tmp_dir):
            import shutil

            shutil.rmtree(self._tmp_dir, ignore_errors=True)

    async def _send_qmp_command(self, command: str, **kwargs):
        if not self._writer or not self._reader:
            return None

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

    def _generate_test_pattern(self) -> np.ndarray:
        import cv2

        frame = np.zeros((self.native_height, self.native_width, 3), dtype=np.uint8)

        for y in range(self.native_height):
            frame[y, :, 0] = int(255 * y / self.native_height)
            frame[y, :, 2] = int(255 * (1 - y / self.native_height))

        cv2.putText(
            frame,
            "40Agent - Test Pattern",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            3,
        )
        cv2.putText(
            frame,
            f"Frame: {self._frame_count}",
            (50, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            f"VM: {self.vm_name} (not connected)",
            (50, 300),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (200, 200, 200),
            2,
        )

        t = time.time()
        x = int((np.sin(t) + 1) / 2 * (self.native_width - 100))
        cv2.circle(frame, (x + 50, 500), 30, (0, 255, 0), -1)

        return frame

    async def capture_frame(self) -> tuple[np.ndarray, FrameInfo]:
        import cv2

        self._frame_count += 1
        timestamp = time.time()

        if self._writer:
            try:
                tmp_path = os.path.join(self._tmp_dir, f"screen_{self._frame_count % 2}.ppm")

                result = await self._send_qmp_command("screendump", filename=tmp_path)

                if result and "return" in result:
                    await asyncio.sleep(0.01)

                    if os.path.exists(tmp_path):
                        frame = cv2.imread(tmp_path)
                        if frame is not None:
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            self._last_frame = frame
                        else:
                            frame = (
                                self._last_frame
                                if self._last_frame is not None
                                else self._generate_test_pattern()
                            )
                    else:
                        frame = (
                            self._last_frame
                            if self._last_frame is not None
                            else self._generate_test_pattern()
                        )
                else:
                    frame = (
                        self._last_frame
                        if self._last_frame is not None
                        else self._generate_test_pattern()
                    )

            except Exception as e:
                logger.error(f"Screen capture failed: {e}")
                frame = (
                    self._last_frame
                    if self._last_frame is not None
                    else self._generate_test_pattern()
                )
        else:
            frame = self._generate_test_pattern()

        info = FrameInfo(
            width=frame.shape[1],
            height=frame.shape[0],
            timestamp=timestamp,
            frame_number=self._frame_count,
        )

        return frame, info

    async def stream_frames(
        self, fps: int | None = None
    ) -> AsyncGenerator[tuple[np.ndarray, FrameInfo], None]:
        fps = fps or self.native_fps
        frame_interval = 1.0 / fps
        self._running = True

        while self._running:
            start_time = time.time()

            frame, info = await self.capture_frame()
            yield frame, info

            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        self._running = False
