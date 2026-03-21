/**
 * Computer Use Agent — Frontend Application
 *
 * Manages session lifecycle, SSE streaming, VNC embedding, and chat UI.
 */

const API_BASE = window.location.origin;

// ====== State ======

let state = {
    sessions: [],
    activeSessionId: null,
    eventSource: null,
    isProcessing: false,
};

// ====== DOM References ======

const dom = {
    sessionList: document.getElementById('session-list'),
    btnNewSession: document.getElementById('btn-new-session'),
    chatMessages: document.getElementById('chat-messages'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    btnSend: document.getElementById('btn-send'),
    vncContainer: document.getElementById('vnc-container'),
    vncStatus: document.getElementById('vnc-status'),
    agentStatus: document.getElementById('agent-status'),
    healthStatus: document.getElementById('health-status'),
};

// ====== API Functions ======

async function apiCall(method, path, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(`${API_BASE}${path}`, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || 'API Error');
    }
    if (resp.status === 204) return null;
    return resp.json();
}

async function createSession(title) {
    return apiCall('POST', '/api/sessions', { title });
}

async function listSessions() {
    const data = await apiCall('GET', '/api/sessions');
    return data.sessions;
}

async function deleteSession(sessionId) {
    return apiCall('DELETE', `/api/sessions/${sessionId}`);
}

async function sendMessage(sessionId, text) {
    return apiCall('POST', `/api/sessions/${sessionId}/messages`, { text });
}

async function getMessages(sessionId) {
    const data = await apiCall('GET', `/api/sessions/${sessionId}/messages`);
    return data.messages;
}

async function getVNCInfo(sessionId) {
    return apiCall('GET', `/api/sessions/${sessionId}/vnc`);
}

async function checkHealth() {
    return apiCall('GET', '/health');
}

// ====== Session Management ======

async function refreshSessions() {
    try {
        state.sessions = await listSessions();
        renderSessionList();
    } catch (e) {
        console.error('Failed to refresh sessions:', e);
    }
}

async function handleNewSession() {
    dom.btnNewSession.disabled = true;
    try {
        const session = await createSession(null);
        state.sessions.unshift(session);
        renderSessionList();
        await selectSession(session.id);
    } catch (e) {
        addSystemMessage(`Failed to create session: ${e.message}`, 'error');
    } finally {
        dom.btnNewSession.disabled = false;
    }
}

async function selectSession(sessionId) {
    if (state.activeSessionId === sessionId) return;

    // Disconnect previous SSE
    disconnectSSE();

    state.activeSessionId = sessionId;
    state.isProcessing = false;
    updateInputState();

    // Highlight in sidebar
    renderSessionList();

    // Load chat history
    await loadChatHistory(sessionId);

    // Connect VNC
    await connectVNC(sessionId);

    // Connect SSE
    connectSSE(sessionId);
}

async function handleDeleteSession(sessionId, event) {
    event.stopPropagation();
    if (!confirm('Delete this session?')) return;

    try {
        await deleteSession(sessionId);

        if (state.activeSessionId === sessionId) {
            disconnectSSE();
            state.activeSessionId = null;
            clearChat();
            clearVNC();
        }

        await refreshSessions();
    } catch (e) {
        console.error('Failed to delete session:', e);
    }
}

// ====== Chat ======

async function loadChatHistory(sessionId) {
    clearChat();
    try {
        const messages = await getMessages(sessionId);
        for (const msg of messages) {
            renderMessage(msg.role, msg.content);
        }
        scrollChatToBottom();
    } catch (e) {
        addSystemMessage('Failed to load chat history', 'error');
    }
}

async function handleSendMessage(e) {
    e.preventDefault();
    const text = dom.chatInput.value.trim();
    if (!text || !state.activeSessionId) return;

    dom.chatInput.value = '';
    state.isProcessing = true;
    updateInputState();

    // Render user message immediately
    renderMessage('user', text);
    scrollChatToBottom();

    try {
        await sendMessage(state.activeSessionId, text);
        // SSE will deliver the agent's response
    } catch (e) {
        addSystemMessage(`Failed to send: ${e.message}`, 'error');
        state.isProcessing = false;
        updateInputState();
    }
}

function clearChat() {
    dom.chatMessages.innerHTML = '<div class="empty-state"><p>Start a conversation with the agent</p></div>';
}

function renderMessage(role, content) {
    // Remove empty state
    const emptyState = dom.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    let displayRole = role;
    let bodyText = '';

    if (typeof content === 'string') {
        bodyText = content;
    } else if (content && typeof content === 'object') {
        if (content.type === 'tool_use') {
            displayRole = 'tool';
            bodyText = `🔧 ${content.name}\n${JSON.stringify(content.input, null, 2)}`;
        } else if (content.type === 'tool_result') {
            displayRole = 'tool';
            bodyText = content.output || content.error || 'Tool executed';
        } else if (content.type === 'text') {
            bodyText = content.text || '';
        } else {
            bodyText = JSON.stringify(content, null, 2);
        }
    }

    const avatar = displayRole === 'user' ? '👤' : displayRole === 'tool' ? '🔧' : '🤖';
    const senderName = displayRole === 'user' ? 'You' : displayRole === 'tool' ? 'Tool' : 'Agent';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    div.className = `message ${displayRole}`;
    div.innerHTML = `
        <div class="message-header">
            <div class="message-avatar ${displayRole}">${avatar}</div>
            <span class="message-sender">${senderName}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-body">${escapeHtml(bodyText)}</div>
    `;

    dom.chatMessages.appendChild(div);
    scrollChatToBottom();
}

function addSystemMessage(text, type = 'status') {
    const emptyState = dom.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerHTML = `<div class="message-body">${escapeHtml(text)}</div>`;
    dom.chatMessages.appendChild(div);
    scrollChatToBottom();
}

function scrollChatToBottom() {
    requestAnimationFrame(() => {
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    });
}

function updateInputState() {
    const enabled = state.activeSessionId && !state.isProcessing;
    dom.chatInput.disabled = !enabled;
    dom.btnSend.disabled = !enabled;

    if (state.isProcessing) {
        dom.agentStatus.textContent = 'Processing...';
        dom.agentStatus.className = 'badge running';
    } else if (state.activeSessionId) {
        dom.agentStatus.textContent = 'Ready';
        dom.agentStatus.className = 'badge';
    } else {
        dom.agentStatus.textContent = 'Idle';
        dom.agentStatus.className = 'badge';
    }
}

// ====== SSE Streaming ======

function connectSSE(sessionId) {
    disconnectSSE();

    const url = `${API_BASE}/api/sessions/${sessionId}/stream`;
    state.eventSource = new EventSource(url);

    state.eventSource.addEventListener('text', (e) => {
        const data = JSON.parse(e.data);
        renderMessage('assistant', data.text);
    });

    state.eventSource.addEventListener('thinking', (e) => {
        const data = JSON.parse(e.data);
        addThinkingMessage(data.thinking);
    });

    state.eventSource.addEventListener('tool_use', (e) => {
        const data = JSON.parse(e.data);
        renderMessage('tool', `🔧 Using: ${data.name}\n${JSON.stringify(data.input, null, 2)}`);
    });

    state.eventSource.addEventListener('tool_result', (e) => {
        const data = JSON.parse(e.data);
        let text = '';
        if (data.output) text += data.output;
        if (data.error) text += `❌ ${data.error}`;
        if (data.has_screenshot) text += (text ? '\n' : '') + '📸 Screenshot captured';
        renderMessage('tool', text || 'Tool completed');
    });

    state.eventSource.addEventListener('status', (e) => {
        const data = JSON.parse(e.data);
        addSystemMessage(`Status: ${data.status}`);
        refreshSessions();
    });

    state.eventSource.addEventListener('error', (e) => {
        if (e.data) {
            const data = JSON.parse(e.data);
            addSystemMessage(`Error: ${data.message}`, 'error');
        }
    });

    state.eventSource.addEventListener('done', () => {
        state.isProcessing = false;
        updateInputState();
        addSystemMessage('✅ Task completed — enter a new task below');
        refreshSessions();
    });

    state.eventSource.onerror = () => {
        // EventSource will auto-reconnect
        console.warn('SSE connection error, reconnecting...');
    };
}

function disconnectSSE() {
    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }
}

function addThinkingMessage(text) {
    const emptyState = dom.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.className = 'message thinking';
    div.innerHTML = `
        <div class="message-header">
            <div class="message-avatar assistant">💭</div>
            <span class="message-sender">Thinking</span>
        </div>
        <div class="message-body">${escapeHtml(text || '...')}</div>
    `;
    dom.chatMessages.appendChild(div);
    scrollChatToBottom();
}

// ====== VNC ======

async function connectVNC(sessionId) {
    try {
        const info = await getVNCInfo(sessionId);
        let novncPath = info.novnc_url;
        
        // Dynamically append the current hostname to the noVNC URL
        if (!novncPath.includes('host=')) {
            novncPath += `&host=${window.location.hostname}`;
        }
        
        const vncUrl = `${window.location.origin}${novncPath}`;

        dom.vncContainer.innerHTML = `<iframe src="${vncUrl}" title="Virtual Desktop"></iframe>`;
        dom.vncStatus.textContent = `Display :${info.display_num}`;
        dom.vncStatus.className = 'badge running';
    } catch (e) {
        dom.vncContainer.innerHTML = `
            <div class="vnc-placeholder">
                <div class="placeholder-icon">⚠️</div>
                <p>Could not connect to VNC: ${escapeHtml(e.message)}</p>
            </div>`;
        dom.vncStatus.textContent = 'Disconnected';
        dom.vncStatus.className = 'badge error';
    }
}

function clearVNC() {
    dom.vncContainer.innerHTML = `
        <div class="vnc-placeholder">
            <div class="placeholder-icon">🖥️</div>
            <p>Select or create a session to view the virtual desktop</p>
        </div>`;
    dom.vncStatus.textContent = 'No session';
    dom.vncStatus.className = 'badge';
}

// ====== Render ======

function renderSessionList() {
    if (state.sessions.length === 0) {
        dom.sessionList.innerHTML = `
            <div class="empty-state">
                <p>No sessions yet</p>
                <p class="subtle">Click "New Task" to start</p>
            </div>`;
        return;
    }

    dom.sessionList.innerHTML = state.sessions.map(s => `
        <div class="session-item ${s.id === state.activeSessionId ? 'active' : ''}"
             onclick="selectSession('${s.id}')">
            <div class="session-title">${escapeHtml(s.title)}</div>
            <div class="session-meta">
                <span class="session-status-dot ${s.status}"></span>
                <span>${s.status}</span>
                <span>•</span>
                <span>${formatTime(s.created_at)}</span>
                <button class="session-delete" onclick="handleDeleteSession('${s.id}', event)">✕</button>
            </div>
        </div>
    `).join('');
}

// ====== Utilities ======

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

function formatTime(isoStr) {
    try {
        return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}

// ====== Health Check ======

async function startHealthCheck() {
    const check = async () => {
        try {
            const health = await checkHealth();
            const dot = dom.healthStatus.querySelector('.status-dot');
            const text = dom.healthStatus.querySelector('span:last-child');
            dot.className = 'status-dot connected';
            text.textContent = `Connected (${health.active_sessions} active)`;
        } catch {
            const dot = dom.healthStatus.querySelector('.status-dot');
            const text = dom.healthStatus.querySelector('span:last-child');
            dot.className = 'status-dot';
            text.textContent = 'Disconnected';
        }
    };

    await check();
    setInterval(check, 10000);
}

// ====== Initialization ======

async function init() {
    // Bind events
    dom.btnNewSession.addEventListener('click', handleNewSession);
    dom.chatForm.addEventListener('submit', handleSendMessage);

    // Allow Enter to send (Shift+Enter for newline)
    dom.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Start health checks
    startHealthCheck();

    // Load existing sessions
    await refreshSessions();
}

// Make functions available for onclick handlers
window.selectSession = selectSession;
window.handleDeleteSession = handleDeleteSession;

// Start the app
document.addEventListener('DOMContentLoaded', init);
