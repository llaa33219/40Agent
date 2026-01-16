"""
Video Stream Processor - Handles frame processing and encoding for AI/web
"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from typing import AsyncGenerator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ProcessedFrame:
    """A processed video frame ready for transmission"""

    # Original resolution frame (for web display)
    web_frame: bytes  # JPEG encoded
    web_width: int
    web_height: int

    # AI resolution frame (downscaled for model input)
    ai_frame: bytes  # JPEG encoded
    ai_frame_b64: str  # Base64 encoded for API
    ai_width: int
    ai_height: int

    timestamp: float
    frame_number: int


class VideoStreamProcessor:
    """
    Processes video frames for dual output:
    - Full resolution JPEG for web display (1920x1080)
    - Downscaled JPEG for AI input (480p @ 12fps)
    """

    def __init__(
        self,
        native_width: int = 1920,
        native_height: int = 1080,
        ai_width: int = 854,  # 480p 16:9
        ai_height: int = 480,
        ai_fps: int = 12,
        web_quality: int = 85,
        ai_quality: int = 70,
    ):
        self.native_width = native_width
        self.native_height = native_height
        self.ai_width = ai_width
        self.ai_height = ai_height
        self.ai_fps = ai_fps
        self.web_quality = web_quality
        self.ai_quality = ai_quality

        self._frame_count = 0
        self._last_ai_frame_time = 0
        self._ai_frame_interval = 1.0 / ai_fps

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp: float,
    ) -> ProcessedFrame:
        """Process a single frame for web and AI output"""
        self._frame_count += 1

        # Ensure frame is in BGR for OpenCV encoding
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # Assume RGB, convert to BGR
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            frame_bgr = frame

        # Encode full resolution for web
        _, web_buffer = cv2.imencode(
            ".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, self.web_quality]
        )
        web_frame = web_buffer.tobytes()

        # Downscale for AI
        ai_frame_bgr = cv2.resize(
            frame_bgr,
            (self.ai_width, self.ai_height),
            interpolation=cv2.INTER_AREA,
        )

        # Encode for AI
        _, ai_buffer = cv2.imencode(
            ".jpg", ai_frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, self.ai_quality]
        )
        ai_frame = ai_buffer.tobytes()
        ai_frame_b64 = base64.b64encode(ai_frame).decode("ascii")

        return ProcessedFrame(
            web_frame=web_frame,
            web_width=frame_bgr.shape[1],
            web_height=frame_bgr.shape[0],
            ai_frame=ai_frame,
            ai_frame_b64=ai_frame_b64,
            ai_width=self.ai_width,
            ai_height=self.ai_height,
            timestamp=timestamp,
            frame_number=self._frame_count,
        )

    def should_send_ai_frame(self, timestamp: float) -> bool:
        """Check if enough time has passed to send another AI frame"""
        elapsed = timestamp - self._last_ai_frame_time
        if elapsed >= self._ai_frame_interval:
            self._last_ai_frame_time = timestamp
            return True
        return False

    async def process_stream(
        self,
        frame_generator: AsyncGenerator[tuple[np.ndarray, any], None],
    ) -> AsyncGenerator[ProcessedFrame, None]:
        """Process a stream of frames"""
        async for frame, info in frame_generator:
            processed = self.process_frame(frame, info.timestamp)
            yield processed
