"""
FastAPI Web Server for 40Agent
Provides WebSocket streaming of VM display and agent interaction
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiofiles
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.agent import Agent

logger = logging.getLogger(__name__)

# Global agent instance
agent: Agent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - start/stop agent"""
    global agent

    # Startup
    logger.info("Starting 40Agent server...")
    agent = Agent()
    await agent.start()

    yield

    # Shutdown
    logger.info("Shutting down 40Agent server...")
    if agent:
        await agent.stop()


app = FastAPI(
    title="40Agent",
    description="AI Agent that can see and control VMs",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
web_dir = settings.project_root / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main web interface"""
    index_path = web_dir / "index.html"
    if index_path.exists():
        async with aiofiles.open(index_path, "r") as f:
            return HTMLResponse(content=await f.read())
    return HTMLResponse(content="<h1>40Agent - Web interface not found</h1>")


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for VM video streaming
    Sends JPEG frames continuously
    """
    await websocket.accept()
    logger.info("Video stream client connected")

    try:
        if agent is None:
            await websocket.close(code=1011, reason="Agent not initialized")
            return

        # Stream frames
        frame_interval = 1.0 / 30  # 30fps for web display

        while True:
            try:
                # Capture frame
                frame, info = await agent.vm_capture.capture_frame()
                processed = agent.video_processor.process_frame(frame, info.timestamp)

                # Send as binary (JPEG)
                await websocket.send_bytes(processed.web_frame)

                await asyncio.sleep(frame_interval)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Video stream client disconnected")


@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket endpoint for agent interaction
    Handles chat messages and state updates
    """
    await websocket.accept()
    logger.info("Agent client connected")

    try:
        if agent is None:
            await websocket.close(code=1011, reason="Agent not initialized")
            return

        # Register response handler
        async def send_response(text: str):
            try:
                await websocket.send_json(
                    {
                        "type": "response",
                        "text": text,
                    }
                )
            except Exception:
                pass

        # Note: Since the handler is sync, we need to use asyncio.create_task
        def response_handler(text: str):
            asyncio.create_task(send_response(text))

        agent.on_response(response_handler)

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "chat":
                    # User chat message
                    text = data.get("text", "")
                    if text:
                        await agent.send_message(text)

                elif msg_type == "state":
                    # Request current state
                    await websocket.send_json(
                        {
                            "type": "state",
                            "data": agent.get_state_dict(),
                        }
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Agent WS error: {e}")

    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Agent client disconnected")


@app.get("/api/state")
async def get_state():
    """Get current agent state"""
    if agent is None:
        return {"error": "Agent not initialized"}
    return agent.get_state_dict()


@app.get("/api/avatar/state")
async def get_avatar_state():
    """Get current avatar state"""
    if agent is None:
        return {"error": "Agent not initialized"}
    return agent.avatar_controller.get_state_for_web()


def run_server():
    """Run the FastAPI server"""
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(f"Starting 40Agent server on {settings.server_host}:{settings.server_port}")

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
