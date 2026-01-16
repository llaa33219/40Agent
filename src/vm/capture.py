"""
VM Screen Capture - Capture VM display via libvirt/SPICE/VNC
"""

import asyncio
import logging
import time
from typing import AsyncGenerator
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """Information about a captured frame"""

    width: int
    height: int
    timestamp: float
    frame_number: int


class VMScreenCapture:
    """
    Captures VM screen via libvirt screendump or SPICE/VNC
    """

    def __init__(
        self,
        vm_name: str,
        native_width: int = 1920,
        native_height: int = 1080,
        native_fps: int = 30,
    ):
        self.vm_name = vm_name
        self.native_width = native_width
        self.native_height = native_height
        self.native_fps = native_fps

        self._conn = None
        self._domain = None
        self._running = False
        self._frame_count = 0
        self._last_frame: np.ndarray | None = None

    async def connect(self) -> bool:
        """Connect to libvirt"""
        try:
            import libvirt

            self._conn = libvirt.open("qemu:///system")
            if self._conn is None:
                logger.error("Failed to connect to QEMU for screen capture")
                return False

            try:
                self._domain = self._conn.lookupByName(self.vm_name)
                logger.info(f"Screen capture connected to VM: {self.vm_name}")
                return True
            except libvirt.libvirtError:
                logger.warning(f"VM '{self.vm_name}' not found. Using test pattern.")
                return False

        except ImportError:
            logger.warning("libvirt-python not installed. Using test pattern.")
            return False
        except Exception as e:
            logger.error(f"Screen capture connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from libvirt"""
        self._running = False
        if self._conn:
            self._conn.close()
            self._conn = None
            self._domain = None

    def _generate_test_pattern(self) -> np.ndarray:
        """Generate a test pattern when VM is not available"""
        import cv2

        # Create a gradient background
        frame = np.zeros((self.native_height, self.native_width, 3), dtype=np.uint8)

        # Gradient
        for y in range(self.native_height):
            frame[y, :, 0] = int(255 * y / self.native_height)  # Blue gradient
            frame[y, :, 2] = int(255 * (1 - y / self.native_height))  # Red gradient

        # Add text
        cv2.putText(
            frame,
            f"40Agent - Test Pattern",
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

        # Moving element to show it's live
        t = time.time()
        x = int((np.sin(t) + 1) / 2 * (self.native_width - 100))
        cv2.circle(frame, (x + 50, 500), 30, (0, 255, 0), -1)

        return frame

    async def capture_frame(self) -> tuple[np.ndarray, FrameInfo]:
        """Capture a single frame from the VM"""
        import cv2

        self._frame_count += 1
        timestamp = time.time()

        if self._domain:
            try:
                import tempfile
                import os

                # Use libvirt screendump
                with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as f:
                    tmp_path = f.name

                # Take screenshot
                stream = self._conn.newStream(0)
                self._domain.screenshot(stream, 0, 0)

                # Read data
                data = b""
                while True:
                    chunk = stream.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                stream.finish()

                # Save and read with OpenCV
                with open(tmp_path, "wb") as f:
                    f.write(data)

                frame = cv2.imread(tmp_path)
                os.unlink(tmp_path)

                if frame is not None:
                    # Convert BGR to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self._last_frame = frame
                else:
                    frame = self._generate_test_pattern()

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
        """Stream frames continuously"""
        fps = fps or self.native_fps
        frame_interval = 1.0 / fps
        self._running = True

        while self._running:
            start_time = time.time()

            frame, info = await self.capture_frame()
            yield frame, info

            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        """Stop streaming"""
        self._running = False
