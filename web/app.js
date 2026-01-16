/**
 * 40Agent Web Application
 * Handles VM streaming, chat interface, and avatar display
 */

class FortyAgent {
    constructor() {
        // Elements
        this.vmCanvas = document.getElementById('vm-canvas');
        this.vmCtx = this.vmCanvas.getContext('2d');
        this.avatarCanvas = document.getElementById('avatar-canvas');
        this.avatarCtx = this.avatarCanvas.getContext('2d');
        this.chatContainer = document.getElementById('chat-container');
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.connectionStatus = document.getElementById('connection-status');
        this.agentStatus = document.getElementById('agent-status');
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.shortcutHint = document.getElementById('shortcut-hint');
        
        // WebSocket connections
        this.streamWs = null;
        this.agentWs = null;
        
        // State
        this.isChatOpen = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        
        // Initialize
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectStream();
        this.connectAgent();
        this.resizeCanvas();
        
        // Hide shortcut hint after 5 seconds
        setTimeout(() => {
            this.shortcutHint.classList.add('hidden');
        }, 5000);
    }
    
    setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // 't' to toggle chat (only if not typing)
            if (e.key.toLowerCase() === 't' && document.activeElement !== this.chatInput) {
                e.preventDefault();
                this.toggleChat();
            }
            // Escape to close chat
            if (e.key === 'Escape' && this.isChatOpen) {
                this.toggleChat();
            }
        });
        
        // Chat input
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Chat buttons
        document.getElementById('chat-send').addEventListener('click', () => this.sendMessage());
        document.getElementById('chat-close').addEventListener('click', () => this.toggleChat());
        
        // Window resize
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        // VM canvas - maintain aspect ratio
        const containerWidth = window.innerWidth;
        const containerHeight = window.innerHeight;
        const aspectRatio = 16 / 9;
        
        let canvasWidth, canvasHeight;
        
        if (containerWidth / containerHeight > aspectRatio) {
            canvasHeight = containerHeight;
            canvasWidth = canvasHeight * aspectRatio;
        } else {
            canvasWidth = containerWidth;
            canvasHeight = canvasWidth / aspectRatio;
        }
        
        this.vmCanvas.width = 1920;
        this.vmCanvas.height = 1080;
        this.vmCanvas.style.width = `${canvasWidth}px`;
        this.vmCanvas.style.height = `${canvasHeight}px`;
        
        // Avatar canvas
        this.avatarCanvas.width = 200;
        this.avatarCanvas.height = 300;
    }
    
    // WebSocket: Video Stream
    connectStream() {
        const wsUrl = `ws://${window.location.host}/ws/stream`;
        this.streamWs = new WebSocket(wsUrl);
        this.streamWs.binaryType = 'blob';
        
        this.updateConnectionStatus('connecting');
        
        this.streamWs.onopen = () => {
            console.log('Stream connected');
            this.updateConnectionStatus('connected');
            this.reconnectAttempts = 0;
        };
        
        this.streamWs.onmessage = async (event) => {
            // Receive JPEG frame as blob
            const blob = event.data;
            const img = new Image();
            img.onload = () => {
                this.vmCtx.drawImage(img, 0, 0, this.vmCanvas.width, this.vmCanvas.height);
                URL.revokeObjectURL(img.src);
            };
            img.src = URL.createObjectURL(blob);
        };
        
        this.streamWs.onclose = () => {
            console.log('Stream disconnected');
            this.updateConnectionStatus('disconnected');
            this.attemptReconnect('stream');
        };
        
        this.streamWs.onerror = (error) => {
            console.error('Stream error:', error);
        };
    }
    
    // WebSocket: Agent Communication
    connectAgent() {
        const wsUrl = `ws://${window.location.host}/ws/agent`;
        this.agentWs = new WebSocket(wsUrl);
        
        this.agentWs.onopen = () => {
            console.log('Agent connected');
            this.updateAgentStatus('idle', 'Ready');
            // Request initial state
            this.agentWs.send(JSON.stringify({ type: 'state' }));
        };
        
        this.agentWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'response':
                    this.addMessage(data.text, 'agent');
                    break;
                case 'state':
                    this.handleStateUpdate(data.data);
                    break;
                case 'tool':
                    this.handleToolResult(data);
                    break;
            }
        };
        
        this.agentWs.onclose = () => {
            console.log('Agent disconnected');
            this.updateAgentStatus('error', 'Disconnected');
            this.attemptReconnect('agent');
        };
        
        this.agentWs.onerror = (error) => {
            console.error('Agent error:', error);
        };
    }
    
    attemptReconnect(type) {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error(`Max reconnection attempts reached for ${type}`);
            return;
        }
        
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        
        console.log(`Reconnecting ${type} in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            if (type === 'stream') {
                this.connectStream();
            } else if (type === 'agent') {
                this.connectAgent();
            }
        }, delay);
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus.className = `visible ${status}`;
        
        switch (status) {
            case 'connected':
                this.connectionStatus.textContent = 'Connected';
                // Hide after 2 seconds
                setTimeout(() => {
                    this.connectionStatus.classList.remove('visible');
                }, 2000);
                break;
            case 'connecting':
                this.connectionStatus.textContent = 'Connecting...';
                break;
            case 'disconnected':
                this.connectionStatus.textContent = 'Disconnected';
                break;
        }
    }
    
    updateAgentStatus(status, text) {
        this.agentStatus.classList.remove('hidden');
        this.statusIndicator.className = status;
        this.statusText.textContent = text;
    }
    
    handleStateUpdate(state) {
        if (state.isThinking) {
            this.updateAgentStatus('thinking', 'Thinking...');
        } else if (state.isSpeaking) {
            this.updateAgentStatus('speaking', 'Speaking...');
        } else if (state.isRunning) {
            this.updateAgentStatus('idle', 'Ready');
        }
        
        // Update avatar if available
        if (state.avatar) {
            this.updateAvatar(state.avatar);
        }
    }
    
    handleToolResult(data) {
        // Could display tool execution results if needed
        console.log('Tool result:', data);
    }
    
    updateAvatar(avatarState) {
        // Placeholder for avatar rendering
        // In a full implementation, this would use Inochi2D
        if (avatarState.currentMotion) {
            document.getElementById('avatar-status').textContent = avatarState.currentMotion;
        }
    }
    
    toggleChat() {
        this.isChatOpen = !this.isChatOpen;
        
        if (this.isChatOpen) {
            this.chatContainer.classList.remove('hidden');
            this.chatInput.focus();
            this.shortcutHint.classList.add('hidden');
        } else {
            this.chatContainer.classList.add('hidden');
        }
    }
    
    sendMessage() {
        const text = this.chatInput.value.trim();
        if (!text) return;
        
        // Add to UI
        this.addMessage(text, 'user');
        
        // Send to agent
        if (this.agentWs && this.agentWs.readyState === WebSocket.OPEN) {
            this.agentWs.send(JSON.stringify({
                type: 'chat',
                text: text
            }));
        }
        
        // Clear input
        this.chatInput.value = '';
    }
    
    addMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = text;
        
        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    addSystemMessage(text) {
        this.addMessage(text, 'system');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.fortyAgent = new FortyAgent();
});
