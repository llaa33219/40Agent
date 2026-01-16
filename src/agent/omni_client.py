"""
Qwen3-Omni Realtime Client
Handles WebSocket connection to Qwen3-omni-flash-realtime API
"""

import asyncio
import base64
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum

import pyaudio
from dashscope.audio.qwen_omni import (
    OmniRealtimeConversation,
    OmniRealtimeCallback,
    MultiModality,
    AudioFormat,
)

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events from the Omni API"""

    SESSION_CREATED = "session.created"
    AUDIO_TRANSCRIPT = "response.audio_transcript.delta"
    AUDIO_DATA = "response.audio.delta"
    TEXT_DELTA = "response.text.delta"
    INPUT_TRANSCRIPT = "conversation.item.input_audio_transcription.completed"
    SPEECH_STARTED = "input_audio_buffer.speech_started"
    SPEECH_STOPPED = "input_audio_buffer.speech_stopped"
    RESPONSE_DONE = "response.done"
    ERROR = "error"


@dataclass
class OmniEvent:
    """Event from the Omni API"""

    event_type: EventType
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AudioPlayer:
    """Threaded audio player for streaming output"""

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.pya = pyaudio.PyAudio()
        self.stream = self.pya.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True,
        )
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._player_loop, daemon=True)
        self._thread.start()

    def _player_loop(self) -> None:
        """Background thread for audio playback"""
        while self._running:
            try:
                audio_data = self._audio_queue.get(timeout=0.1)
                self.stream.write(audio_data)
            except queue.Empty:
                continue

    def add_audio(self, audio_b64: str) -> None:
        """Add base64 encoded audio to playback queue"""
        try:
            audio_bytes = base64.b64decode(audio_b64)
            self._audio_queue.put(audio_bytes)
        except Exception as e:
            logger.error(f"Failed to decode audio: {e}")

    def cancel(self) -> None:
        """Cancel current playback"""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    def shutdown(self) -> None:
        """Shutdown the audio player"""
        self._running = False
        self._thread.join(timeout=1.0)
        self.stream.close()
        self.pya.terminate()


class OmniCallback(OmniRealtimeCallback):
    """Callback handler for Omni API events"""

    def __init__(self, event_handler: Callable[[OmniEvent], None]):
        self.event_handler = event_handler
        self.audio_player: AudioPlayer | None = None

    def on_open(self) -> None:
        logger.info("Omni connection opened")
        self.audio_player = AudioPlayer()

    def on_close(self, close_status_code: int, close_msg: str) -> None:
        logger.info(f"Omni connection closed: {close_status_code} - {close_msg}")
        if self.audio_player:
            self.audio_player.shutdown()

    def on_event(self, response: dict) -> None:
        try:
            event_type_str = response.get("type", "")

            # Map to event type
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                logger.debug(f"Unknown event type: {event_type_str}")
                return

            event = OmniEvent(event_type=event_type, data=response)

            # Handle audio playback
            if event_type == EventType.AUDIO_DATA and self.audio_player:
                audio_b64 = response.get("delta", "")
                if audio_b64:
                    self.audio_player.add_audio(audio_b64)

            # Cancel playback on speech detection (interrupt)
            if event_type == EventType.SPEECH_STARTED and self.audio_player:
                self.audio_player.cancel()

            # Forward to handler
            self.event_handler(event)

        except Exception as e:
            logger.error(f"Error handling event: {e}")


class OmniClient:
    """
    Client for Qwen3-omni-flash-realtime API
    Supports multimodal input (text, audio, video) and output (text, audio)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-omni-flash-realtime",
        voice: str = "Chelsie",
        ws_url: str = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime",
        system_prompt: str = "",
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.ws_url = ws_url
        self.system_prompt = system_prompt

        self._conversation: OmniRealtimeConversation | None = None
        self._callback: OmniCallback | None = None
        self._event_handlers: list[Callable[[OmniEvent], None]] = []
        self._connected = False

        # Audio input
        self._mic_pya: pyaudio.PyAudio | None = None
        self._mic_stream = None
        self._audio_capture_thread: threading.Thread | None = None
        self._capturing_audio = False

    def on_event(self, handler: Callable[[OmniEvent], None]) -> None:
        """Register an event handler"""
        self._event_handlers.append(handler)

    def _dispatch_event(self, event: OmniEvent) -> None:
        """Dispatch event to all handlers"""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def connect(self) -> bool:
        """Connect to the Omni API"""
        try:
            import dashscope

            dashscope.api_key = self.api_key

            self._callback = OmniCallback(self._dispatch_event)

            self._conversation = OmniRealtimeConversation(
                model=self.model,
                callback=self._callback,
                url=self.ws_url,
            )

            self._conversation.connect()

            # Configure session
            self._conversation.update_session(
                output_modalities=[MultiModality.AUDIO, MultiModality.TEXT],
                voice=self.voice,
                input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
                output_audio_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                enable_input_audio_transcription=True,
                input_audio_transcription_model="gummy-realtime-v1",
                enable_turn_detection=True,
                turn_detection_type="server_vad",
            )

            # Set system prompt if provided
            if self.system_prompt:
                self._conversation.add_item(
                    item_type="message",
                    role="system",
                    content=[{"type": "input_text", "text": self.system_prompt}],
                )

            self._connected = True
            logger.info("Connected to Omni API")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Omni API: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Omni API"""
        self.stop_audio_capture()

        if self._conversation:
            try:
                self._conversation.close()
            except Exception as e:
                logger.error(f"Error closing conversation: {e}")

        self._connected = False
        logger.info("Disconnected from Omni API")

    def start_audio_capture(self) -> None:
        """Start capturing audio from microphone"""
        if self._capturing_audio:
            return

        self._mic_pya = pyaudio.PyAudio()
        self._mic_stream = self._mic_pya.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=3200,
        )

        self._capturing_audio = True
        self._audio_capture_thread = threading.Thread(
            target=self._audio_capture_loop,
            daemon=True,
        )
        self._audio_capture_thread.start()
        logger.info("Audio capture started")

    def stop_audio_capture(self) -> None:
        """Stop capturing audio"""
        self._capturing_audio = False

        if self._audio_capture_thread:
            self._audio_capture_thread.join(timeout=1.0)

        if self._mic_stream:
            self._mic_stream.close()

        if self._mic_pya:
            self._mic_pya.terminate()

        logger.info("Audio capture stopped")

    def _audio_capture_loop(self) -> None:
        """Background thread for audio capture"""
        while self._capturing_audio and self._mic_stream:
            try:
                audio_data = self._mic_stream.read(3200, exception_on_overflow=False)
                audio_b64 = base64.b64encode(audio_data).decode("ascii")

                if self._conversation and self._connected:
                    self._conversation.append_audio(audio_b64)

            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                break

    def send_video_frame(self, frame_b64: str) -> None:
        """Send a video frame to the model"""
        if not self._conversation or not self._connected:
            return

        try:
            # Add video frame as image input
            self._conversation.add_item(
                item_type="message",
                role="user",
                content=[
                    {
                        "type": "input_image",
                        "image": f"data:image/jpeg;base64,{frame_b64}",
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Failed to send video frame: {e}")

    def send_text(self, text: str) -> None:
        """Send a text message to the model"""
        if not self._conversation or not self._connected:
            return

        try:
            self._conversation.add_item(
                item_type="message",
                role="user",
                content=[{"type": "input_text", "text": text}],
            )
            # Trigger response
            self._conversation.create_response()
        except Exception as e:
            logger.error(f"Failed to send text: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._connected
