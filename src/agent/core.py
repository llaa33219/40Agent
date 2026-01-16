"""
40Agent Core - Autonomous agent that sees and controls the VM
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Any

from src.config import settings
from src.tools import ToolExecutor, ToolParser
from src.vm import VMController, VMScreenCapture
from src.stream import VideoStreamProcessor, AvatarController
from .omni_client import OmniClient, OmniEvent, EventType

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Current state of the agent"""

    is_running: bool = False
    is_thinking: bool = False
    is_speaking: bool = False
    current_task: str | None = None
    last_response: str | None = None
    tool_results: list[dict] = field(default_factory=list)
    frame_count: int = 0


class Agent:
    """
    40Agent - Autonomous AI agent that can see and control a VM

    Uses Qwen3-omni for multimodal perception:
    - Video input: VM screen (480p @ 12fps)
    - Audio input: User voice
    - Text output: Tool commands
    - Audio output: Voice responses
    """

    def __init__(self):
        # Components
        self.vm_controller = VMController(
            vm_name=settings.vm_name,
            qmp_socket=settings.vm_qmp_socket,
        )
        self.vm_capture = VMScreenCapture(
            vm_name=settings.vm_name,
            qmp_socket=settings.vm_qmp_socket,
            native_width=settings.vm_native_width,
            native_height=settings.vm_native_height,
            native_fps=settings.vm_native_fps,
        )
        self.video_processor = VideoStreamProcessor(
            native_width=settings.vm_native_width,
            native_height=settings.vm_native_height,
            ai_width=settings.ai_input_width,
            ai_height=settings.ai_input_height,
            ai_fps=settings.ai_input_fps,
        )
        self.avatar_controller = AvatarController(settings.character_dir)
        self.tool_executor: ToolExecutor | None = None
        self.omni_client: OmniClient | None = None

        # State
        self._state = AgentState()
        self._lock = asyncio.Lock()

        # Event handlers
        self._response_handlers: list[Callable[[str], None]] = []
        self._state_handlers: list[Callable[[AgentState], None]] = []

        # Autonomous loop
        self._loop_task: asyncio.Task | None = None
        self._accumulated_text = ""

    async def start(self) -> bool:
        """Initialize and start the agent"""
        logger.info("Starting 40Agent...")

        # Connect to VM
        vm_connected = await self.vm_controller.connect()
        capture_connected = await self.vm_capture.connect()

        if not vm_connected or not capture_connected:
            logger.warning("VM not fully connected - running in demo mode")

        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            vm_controller=self.vm_controller,
            avatar_controller=self.avatar_controller,
        )

        # Load avatar
        await self.avatar_controller.load_avatar("default")

        # Connect to Omni API
        if settings.dashscope_api_key:
            self.omni_client = OmniClient(
                api_key=settings.dashscope_api_key,
                model=settings.omni_model,
                voice=settings.omni_voice,
                ws_url=settings.omni_ws_url,
                system_prompt=settings.agent_system_prompt,
            )

            # Register event handler
            self.omni_client.on_event(self._handle_omni_event)

            # Connect
            if await self.omni_client.connect():
                logger.info("Connected to Omni API")
            else:
                logger.warning("Failed to connect to Omni API - running in limited mode")
        else:
            logger.warning("No DASHSCOPE_API_KEY - running without AI")

        self._state.is_running = True

        # Start autonomous loop
        self._loop_task = asyncio.create_task(self._autonomous_loop())

        logger.info("40Agent started successfully")
        return True

    async def stop(self) -> None:
        """Stop the agent"""
        logger.info("Stopping 40Agent...")

        self._state.is_running = False

        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        if self.omni_client:
            await self.omni_client.disconnect()

        await self.vm_capture.disconnect()
        await self.vm_controller.disconnect()

        logger.info("40Agent stopped")

    def _handle_omni_event(self, event: OmniEvent) -> None:
        """Handle events from the Omni API"""
        try:
            if event.event_type == EventType.TEXT_DELTA:
                # Accumulate text response
                delta = event.data.get("delta", "")
                self._accumulated_text += delta

            elif event.event_type == EventType.AUDIO_TRANSCRIPT:
                # Audio transcript (what the model is saying)
                delta = event.data.get("delta", "")
                for handler in self._response_handlers:
                    handler(delta)

            elif event.event_type == EventType.INPUT_TRANSCRIPT:
                # What the user said
                transcript = event.data.get("transcript", "")
                logger.info(f"User said: {transcript}")

            elif event.event_type == EventType.SPEECH_STARTED:
                # User started speaking - interrupt
                self._state.is_speaking = False
                asyncio.create_task(self.avatar_controller.set_speaking(False))

            elif event.event_type == EventType.RESPONSE_DONE:
                # Response complete - process accumulated text
                asyncio.create_task(self._process_response(self._accumulated_text))
                self._accumulated_text = ""
                self._state.is_thinking = False

        except Exception as e:
            logger.error(f"Error handling Omni event: {e}")

    async def _process_response(self, text: str) -> None:
        """Process the agent's response - extract and execute tools"""
        if not text:
            return

        self._state.last_response = text

        # Check for tool calls
        if self.tool_executor and self.tool_executor.has_tool_calls(text):
            logger.info(f"Executing tools from response")
            results = await self.tool_executor.execute_all(text)
            self._state.tool_results = results

            # Notify state handlers
            for handler in self._state_handlers:
                handler(self._state)

        # Set speaking state based on whether there's speech content
        speech = ToolParser.extract_speech(text)
        if speech:
            self._state.is_speaking = True
            await self.avatar_controller.set_speaking(True)

    async def _autonomous_loop(self) -> None:
        """
        Main autonomous loop - continuously sends VM frames to the model
        """
        logger.info("Starting autonomous loop")

        frame_interval = 1.0 / settings.ai_input_fps

        while self._state.is_running:
            try:
                start_time = time.time()

                # Capture and process frame
                frame, info = await self.vm_capture.capture_frame()
                processed = self.video_processor.process_frame(frame, info.timestamp)
                self._state.frame_count = processed.frame_number

                # Send frame to model (at AI fps rate)
                if self.omni_client and self.omni_client.is_connected:
                    if self.video_processor.should_send_ai_frame(info.timestamp):
                        self.omni_client.send_video_frame(processed.ai_frame_b64)

                # Notify state handlers
                for handler in self._state_handlers:
                    handler(self._state)

                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in autonomous loop: {e}")
                await asyncio.sleep(0.1)

        logger.info("Autonomous loop stopped")

    async def send_message(self, text: str) -> None:
        """Send a text message to the agent"""
        if self.omni_client and self.omni_client.is_connected:
            self._state.is_thinking = True
            self.omni_client.send_text(text)
        else:
            logger.warning("Cannot send message - Omni API not connected")

    def on_response(self, handler: Callable[[str], None]) -> None:
        """Register a handler for agent responses"""
        self._response_handlers.append(handler)

    def on_state_change(self, handler: Callable[[AgentState], None]) -> None:
        """Register a handler for state changes"""
        self._state_handlers.append(handler)

    @property
    def state(self) -> AgentState:
        """Get current agent state"""
        return self._state

    def get_state_dict(self) -> dict:
        """Get state as dictionary for JSON serialization"""
        return {
            "isRunning": self._state.is_running,
            "isThinking": self._state.is_thinking,
            "isSpeaking": self._state.is_speaking,
            "currentTask": self._state.current_task,
            "lastResponse": self._state.last_response,
            "toolResults": self._state.tool_results,
            "frameCount": self._state.frame_count,
            "vmConnected": self.vm_controller.is_connected,
            "omniConnected": self.omni_client.is_connected if self.omni_client else False,
            "avatar": self.avatar_controller.get_state_for_web(),
        }
