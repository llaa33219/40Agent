"""
40Agent Configuration
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.resolve())
    character_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "character")
    model_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "model")
    vm_data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "vm_data")

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8040

    # API Keys
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")

    # Qwen Omni Model
    omni_model: str = "qwen3-omni-flash-realtime"
    omni_voice: str = "Chelsie"
    omni_ws_url: str = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"

    # Audio settings
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000

    # VM settings
    vm_name: str = "40agent-vm"
    vm_qmp_socket: str = "/tmp/qemu-40agent-vm-qmp.sock"
    vm_native_width: int = 1920
    vm_native_height: int = 1080
    vm_native_fps: int = 30

    # AI input settings (downscaled for model input)
    ai_input_width: int = 854  # 480p width (16:9)
    ai_input_height: int = 480
    ai_input_fps: int = 12

    # Agent settings
    agent_system_prompt: str = """You are 40Agent, an AI assistant that can see and control a virtual machine.
You can see the VM screen in real-time and interact with it using these tools:

<tool name="cursor-move">x,y</tool> - Move cursor to coordinates (0-1920, 0-1080)
<tool name="cursor-click">button</tool> - Click mouse button (left/right/middle)
<tool name="text-input">text</tool> - Type text
<tool name="key-input">keys</tool> - Press keys (e.g., "ctrl+c", "enter", "alt+tab")
<tool name="i2d-motion">motion_name</tool> - Trigger avatar motion

You operate autonomously - continue working on tasks without waiting for confirmation.
When speaking, use natural voice. When using tools, output the tool XML.
The VM runs pearOS (Arch Linux with KDE). Help users accomplish their goals."""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
