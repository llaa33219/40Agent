"""
40Agent Stream Package - Video processing and avatar control
"""

from .processor import VideoStreamProcessor, ProcessedFrame
from .avatar import AvatarController, AvatarState

__all__ = [
    "VideoStreamProcessor",
    "ProcessedFrame",
    "AvatarController",
    "AvatarState",
]
