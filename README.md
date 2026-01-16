# 40Agent

AI Agent that can see and control virtual machines using Qwen3-omni multimodal model.

## Features

- **Real-time VM Vision**: Continuously captures VM screen at 480p 12fps for AI perception
- **Multimodal AI**: Uses Qwen3-omni-flash-realtime for vision, audio input/output
- **VM Control**: Mouse movement, clicking, keyboard input via QEMU QMP
- **Web Interface**: Full-screen VM display with chat overlay (port 8040)
- **Avatar System**: Inochi2D avatar with motion control
- **Autonomous Operation**: Agent runs continuously, taking actions without waiting

## Quick Start

```bash
# 1. API 키 설정
cp .env.example .env
# .env 파일 열어서 DASHSCOPE_API_KEY 입력

# 2. 실행 - VM 자동 시작됨
python run.py
```

That's it! The script will:
1. Install `uv` if not present
2. Create virtual environment
3. Install all dependencies
4. Start QEMU VM automatically (if disk exists)
5. Start the server on http://localhost:8040

## Requirements

- Python 3.11+
- QEMU (qemu-full)
- `.env` file with DASHSCOPE_API_KEY

### System Dependencies

```bash
# Arch Linux
sudo pacman -S qemu-full portaudio

# Ubuntu/Debian
sudo apt install qemu-system-x86 portaudio19-dev

# macOS
brew install qemu portaudio
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
VM_MEMORY=4096
VM_CPUS=2
SERVER_PORT=8040
OMNI_VOICE=Chelsie
```

## Project Structure

```
40Agent/
├── run.py              # Entry point (auto-setup + VM launch)
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
└── vm_data/            # VM disk images
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

### Creating a VM Disk

```bash
# Create disk image
mkdir -p vm_data
qemu-img create -f qcow2 vm_data/40agent-vm.qcow2 20G

# Install OS from ISO (run manually once)
qemu-system-x86_64 \
  -m 4096 -smp 2 \
  -hda vm_data/40agent-vm.qcow2 \
  -cdrom your-os.iso \
  -boot d \
  -device virtio-vga \
  -display gtk
```

After installation, `python run.py` will automatically start the VM.

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

1. VM screen captured via QEMU QMP screendump (1920x1080 @ 30fps)
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
