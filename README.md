# 40Agent

AI Agent that can see and control virtual machines using Qwen3-omni multimodal model.

## Features

- **Real-time VM Vision**: Continuously captures VM screen at 480p 12fps for AI perception
- **Multimodal AI**: Uses Qwen3-omni-flash-realtime for vision, audio input/output
- **VM Control**: Mouse movement, clicking, keyboard input via QEMU/libvirt
- **Web Interface**: Full-screen VM display with chat overlay (port 8040)
- **Avatar System**: Inochi2D avatar with motion control
- **Autonomous Operation**: Agent runs continuously, taking actions without waiting

## Quick Start

```bash
# 1. API 키 설정
cp .env.example .env
# .env 파일 열어서 DASHSCOPE_API_KEY 입력

# 2. 실행 - 자동으로 환경 설정됨
python run.py
```

That's it! The script will:
1. Install `uv` if not present
2. Create virtual environment
3. Install all dependencies
4. Start the server on http://localhost:8040

## Requirements

- Python 3.11+
- QEMU/libvirt (for VM control)
- `.env` file with DASHSCOPE_API_KEY

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install libvirt-dev portaudio19-dev

# Arch Linux
sudo pacman -S libvirt portaudio

# macOS
brew install libvirt portaudio
```

## Configuration

`.env` 파일에서 설정:

```bash
cp .env.example .env
```

```env
# .env
DASHSCOPE_API_KEY=sk-your-api-key-here

# Optional
VM_NAME=40agent-vm
SERVER_PORT=8040
OMNI_VOICE=Chelsie
```

## Project Structure

```
40Agent/
├── run.py              # Entry point (auto-setup + launch)
├── pyproject.toml      # Dependencies & project config
├── src/
│   ├── agent/          # AI agent core (Qwen3-omni client)
│   ├── tools/          # Tool system (cursor, keyboard, avatar)
│   ├── vm/             # VM control & screen capture
│   ├── stream/         # Video processing & avatar
│   ├── server/         # FastAPI web server
│   └── config.py       # Settings
├── web/                # Web interface (HTML/CSS/JS)
├── character/          # Inochi2D avatar files (.inx)
├── model/              # Local model files (if any)
└── vm_data/            # VM disk images & configs
```

## Usage

### Web Interface

Open http://localhost:8040 in your browser.

- **Full screen**: VM display fills the entire screen
- **Press `T`**: Toggle chat interface
- **Bottom right**: Inochi2D avatar

### Chat Commands

Just type naturally - the agent understands context from seeing the VM:

- "Open Firefox and go to google.com"
- "Click on the settings icon"
- "Type 'hello world' in the text field"

### Agent Tools

The agent uses these tools (in XML format):

```xml
<tool name="cursor-move">x,y</tool>        <!-- Move cursor to coordinates -->
<tool name="cursor-click">button</tool>    <!-- Click (left/right/middle) -->
<tool name="text-input">text</tool>        <!-- Type text -->
<tool name="key-input">keys</tool>         <!-- Press keys (ctrl+c, enter, etc) -->
<tool name="i2d-motion">motion</tool>      <!-- Trigger avatar motion -->
```

## VM Setup

### Creating a VM

1. Download pearOS-NiceC0re-25-12 ISO
2. Create VM with libvirt:

```bash
virt-install \
  --name 40agent-vm \
  --ram 4096 \
  --vcpus 2 \
  --disk size=20 \
  --cdrom pearOS-NiceC0re-25-12.iso \
  --os-variant archlinux \
  --graphics spice
```

3. Install the OS and start the VM

### VM Configuration

The VM should be:
- Name: `40agent-vm` (or change in config)
- Resolution: 1920x1080
- Graphics: SPICE or VNC

## API Reference

### WebSocket Endpoints

- `/ws/stream` - VM video stream (binary JPEG frames)
- `/ws/agent` - Agent communication (JSON messages)

### REST Endpoints

- `GET /` - Web interface
- `GET /api/state` - Agent state
- `GET /api/avatar/state` - Avatar state

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run with auto-reload
uv run uvicorn src.server.app:app --reload --port 8040

# Run tests
uv run pytest

# Lint
uv run ruff check src
```

## Technical Details

### Video Pipeline

1. VM screen captured via libvirt screendump (1920x1080 @ 30fps)
2. Downscaled to 480p @ 12fps for AI input
3. Full resolution streamed to web at 30fps
4. JPEG encoding for both streams

### AI Model

- Model: `qwen3-omni-flash-realtime`
- Input: Video frames (480p), audio (16kHz PCM)
- Output: Text (tool commands), audio (24kHz PCM)
- Connection: WebSocket to DashScope API

### Tool Execution

1. Agent outputs text with `<tool>` tags
2. ToolParser extracts tool calls
3. ToolExecutor routes to appropriate handler
4. Results logged and optionally reported back

## License

MIT
