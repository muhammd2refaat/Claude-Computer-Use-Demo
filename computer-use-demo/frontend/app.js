/**
 * Energent AI Computer Use Agent — Frontend Application
 *
 * Manages session lifecycle, SSE streaming, VNC embedding, chat UI,
 * and file management. Supports concurrent sessions with dynamic
 * display allocation.
 */

const API_BASE = window.location.origin;

// ====== State ======

let state = {
    sessions: [],
    activeSessionId: null,
    eventSource: null,
    isProcessing: false,
    isRecording: false,
    recordingStartTime: null,
};

// ====== DOM References ======

const dom = {
    sessionList: document.getElementById('task-list'),
    btnNewSession: document.getElementById('btn-new-session'),
    chatMessages: document.getElementById('chat-messages'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    btnSend: document.getElementById('btn-send'),
    vncContainer: document.getElementById('vnc-container'),
    vncStatus: document.getElementById('vnc-status'),
    vncTitle: document.getElementById('vnc-title'),
    workspaceLabel: document.getElementById('workspace-label'),
    healthStatus: document.getElementById('health-status'),
    fileList: document.getElementById('file-list'),
    fileUploadArea: document.getElementById('file-upload-area'),
    fileInput: document.getElementById('file-input'),
    btnRefreshFiles: document.getElementById('btn-refresh-files'),
    searchInput: document.getElementById('search-input'),
    btnRecord: document.getElementById('btn-record'),
    btnStop: document.getElementById('btn-stop'),
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

async function listFiles(sessionId) {
    const data = await apiCall('GET', `/api/sessions/${sessionId}/files`);
    return data.files;
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

    // Clear and show welcome message
    clearChat();

    // Load chat history
    await loadChatHistory(sessionId);

    // Connect VNC
    await connectVNC(sessionId);

    // Load files
    await loadFiles(sessionId);

    // Connect SSE for real-time streaming
    connectSSE(sessionId);
}

async function handleDeleteSession(sessionId, event) {
    event.stopPropagation();
    if (!confirm('Delete this session and release its display?')) return;

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

// ====== Stop & Record ======

async function handleStopAgent() {
    if (!state.activeSessionId) return;

    try {
        const resp = await apiCall('POST', `/api/sessions/${state.activeSessionId}/stop`);
        addSystemMessage('Agent task stopped', 'status');
        state.isProcessing = false;
        updateInputState();
    } catch (e) {
        console.error('Failed to stop agent:', e);
        addSystemMessage(`Failed to stop: ${e.message}`, 'error');
    }
}

function handleRecord() {
    if (state.isRecording) {
        // Stop recording
        stopRecording();
    } else {
        // Start recording
        startRecording();
    }
}

function startRecording() {
    if (!state.activeSessionId) {
        addSystemMessage('Please select a session first', 'error');
        return;
    }

    state.isRecording = true;
    state.recordingStartTime = Date.now();

    // Update button UI
    dom.btnRecord.style.background = 'var(--error)';
    dom.btnRecord.style.color = 'white';
    dom.btnRecord.querySelector('span').textContent = 'Recording...';

    addSystemMessage('🔴 Recording started', 'status');

    // Note: Actual screen recording would require additional implementation
    // This is a UI state change to show the feature exists
    console.log('Recording started for session:', state.activeSessionId);
}

function stopRecording() {
    state.isRecording = false;
    const duration = Math.floor((Date.now() - state.recordingStartTime) / 1000);

    // Reset button UI
    dom.btnRecord.style.background = '';
    dom.btnRecord.style.color = '';
    dom.btnRecord.querySelector('span').textContent = 'Record';

    addSystemMessage(`⏹️ Recording stopped (${duration}s)`, 'status');

    console.log('Recording stopped');
}

// ====== Chat ======

async function loadChatHistory(sessionId) {
    try {
        const messages = await getMessages(sessionId);
        if (messages.length > 0) {
            const welcome = dom.chatMessages.querySelector('.welcome-message');
            if (welcome) welcome.remove();
        }
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
    autoResizeTextarea(dom.chatInput);
    state.isProcessing = true;
    updateInputState();

    // Remove welcome message
    const welcome = dom.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // Render user message immediately for instant feedback
    renderMessage('user', text);
    scrollChatToBottom();

    try {
        await sendMessage(state.activeSessionId, text);
        // SSE will deliver the agent's response in real-time
    } catch (e) {
        addSystemMessage(`Failed to send: ${e.message}`, 'error');
        state.isProcessing = false;
        updateInputState();
    }
}

function clearChat() {
    dom.chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="bot-avatar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="3" y="6" width="18" height="12" rx="2" stroke="currentColor" stroke-width="2"/>
                    <circle cx="8.5" cy="12" r="1.5" fill="currentColor"/>
                    <circle cx="15.5" cy="12" r="1.5" fill="currentColor"/>
                    <path d="M9 16h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </div>
            <div class="welcome-text">
                <p>Hi! Let me know what task to accomplish</p>
            </div>
        </div>`;
}

function renderMessage(role, content) {
    // Remove welcome message when first real message appears
    const welcome = dom.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

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
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    div.className = `message ${displayRole}`;
    div.innerHTML = `
        <div class="message-avatar ${displayRole}">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">${escapeHtml(bodyText)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    dom.chatMessages.appendChild(div);
    scrollChatToBottom();
}

function addSystemMessage(text, type = 'status') {
    const welcome = dom.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerHTML = `
        <div class="message-content" style="max-width: 100%; width: 100%;">
            <div class="message-bubble" style="text-align: center;">${escapeHtml(text)}</div>
        </div>
    `;
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
    dom.chatInput.placeholder = enabled
        ? 'Write a message...'
        : (state.activeSessionId ? 'Agent is processing...' : 'Create a task to start chatting...');
}

// ====== SSE Streaming (Real-time Progress) ======

function connectSSE(sessionId) {
    disconnectSSE();

    const url = `${API_BASE}/api/sessions/${sessionId}/stream`;
    state.eventSource = new EventSource(url);

    // Real-time text output from the agent
    state.eventSource.addEventListener('text', (e) => {
        const data = JSON.parse(e.data);
        renderMessage('assistant', data.text);
    });

    // Agent thinking/reasoning
    state.eventSource.addEventListener('thinking', (e) => {
        const data = JSON.parse(e.data);
        addThinkingMessage(data.thinking);
    });

    // Tool invocations (function calls)
    state.eventSource.addEventListener('tool_use', (e) => {
        const data = JSON.parse(e.data);
        renderMessage('tool', `🔧 Using: ${data.name}\n${JSON.stringify(data.input, null, 2)}`);
    });

    // Tool execution results
    state.eventSource.addEventListener('tool_result', (e) => {
        const data = JSON.parse(e.data);
        let text = '';
        if (data.output) text += data.output;
        if (data.error) text += `❌ ${data.error}`;
        if (data.has_screenshot) text += (text ? '\n' : '') + '📸 Screenshot captured';
        renderMessage('tool', text || 'Tool completed');
        // Refresh file list since a new screenshot was likely created
        if (state.activeSessionId) {
            loadFiles(state.activeSessionId).catch(() => {});
        }
    });

    // Session status changes
    state.eventSource.addEventListener('status', (e) => {
        const data = JSON.parse(e.data);
        if (data.status === 'running') {
            dom.vncStatus.textContent = 'Running';
            dom.vncStatus.className = 'badge running';
        } else if (data.status === 'idle') {
            dom.vncStatus.textContent = 'Ready';
            dom.vncStatus.className = 'badge';
        }
        refreshSessions();
    });

    // Error events from the agent
    state.eventSource.addEventListener('error', (e) => {
        if (e.data) {
            try {
                const data = JSON.parse(e.data);
                // Only show actual agent errors, not session-not-found
                if (data.message && !data.message.includes('not found') && !data.message.includes('not active')) {
                    addSystemMessage(`Error: ${data.message}`, 'error');
                }
            } catch (parseErr) {
                // Ignore parse errors from SSE
            }
        }
        // Prevent auto-reconnect loop: close on connection errors
        if (e.eventPhase === EventSource.CLOSED || !e.data) {
            disconnectSSE();
        }
    });

    // Agent loop completed
    state.eventSource.addEventListener('done', () => {
        state.isProcessing = false;
        updateInputState();
        addSystemMessage('✅ Task completed — enter a new task below');
        dom.vncStatus.textContent = 'Ready';
        dom.vncStatus.className = 'badge';
        refreshSessions();
    });

    state.eventSource.onerror = () => {
        // Close to prevent infinite reconnect loop for inactive sessions
        disconnectSSE();
    };
}

function disconnectSSE() {
    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }
}

function addThinkingMessage(text) {
    const welcome = dom.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = 'message thinking';
    div.innerHTML = `
        <div class="message-avatar assistant">💭</div>
        <div class="message-content">
            <div class="message-bubble">${escapeHtml(text || '...')}</div>
        </div>
    `;
    dom.chatMessages.appendChild(div);
    scrollChatToBottom();
}

// ====== VNC (Virtual Desktop View) ======

async function connectVNC(sessionId) {
    try {
        const info = await getVNCInfo(sessionId);
        let novncPath = info.novnc_url;

        // Dynamically append the current hostname to the noVNC URL
        if (!novncPath.includes('host=')) {
            novncPath += `&host=${window.location.hostname}`;
        }

        const vncUrl = `${window.location.origin}${novncPath}`;

        dom.vncContainer.innerHTML = `<iframe src="${vncUrl}" title="Virtual Desktop - Display :${info.display_num}"></iframe>`;
        dom.vncStatus.textContent = `Display :${info.display_num}`;
        dom.vncStatus.className = 'badge running';
        dom.vncTitle.textContent = `Virtual Desktop - Display :${info.display_num}`;
        dom.workspaceLabel.textContent = `Workspace ${info.display_num - 99}`;
    } catch (e) {
        dom.vncContainer.innerHTML = `
            <div class="vnc-placeholder">
                <div class="placeholder-icon">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 8v4M12 16h.01"/>
                    </svg>
                </div>
                <p class="placeholder-title">Connection Error</p>
                <p class="placeholder-subtitle">${escapeHtml(e.message)}</p>
            </div>`;
        dom.vncStatus.textContent = 'Disconnected';
        dom.vncStatus.className = 'badge error';
    }
}

function clearVNC() {
    dom.vncContainer.innerHTML = `
        <div class="vnc-placeholder">
            <div class="placeholder-icon">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <path d="M8 21h8M12 17v4"/>
                </svg>
            </div>
            <p class="placeholder-title">Virtual Desktop</p>
            <p class="placeholder-subtitle">Create a new task to activate the display</p>
        </div>`;
    dom.vncStatus.textContent = 'No session';
    dom.vncStatus.className = 'badge';
    dom.vncTitle.textContent = 'Virtual Desktop';
    dom.workspaceLabel.textContent = 'Workspace 1';
}

// ====== File Management ======

async function loadFiles(sessionId) {
    dom.btnRefreshFiles.disabled = false;
    try {
        const files = await listFiles(sessionId);
        renderFileList(files);
    } catch (e) {
        console.error('Failed to load files:', e);
        dom.fileList.innerHTML = '';
    }
}

function renderFileList(files) {
    if (!files || files.length === 0) {
        dom.fileList.innerHTML = '';
        return;
    }

    dom.fileList.innerHTML = files.map(file => {
        const icon = getFileIcon(file.name);
        const size = formatFileSize(file.size);
        const time = new Date(file.created_at * 1000).toLocaleTimeString([], {
            hour: '2-digit', minute: '2-digit'
        });

        return `
            <div class="file-item" onclick="downloadFile('${escapeAttr(file.name)}')">
                <span class="file-icon">${icon}</span>
                <div class="file-details">
                    <div class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
                    <div class="file-meta">${size} • ${time}</div>
                </div>
                <div class="file-actions">
                    <button class="file-action-btn" onclick="event.stopPropagation(); downloadFile('${escapeAttr(file.name)}')" title="Download">
                        ⬇️
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'png': '🖼️',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'gif': '🖼️',
        'webp': '🖼️',
        'pdf': '📄',
        'txt': '📝',
        'md': '📝',
        'json': '📋',
        'csv': '📊',
        'zip': '📦',
        'py': '🐍',
        'js': '📜',
        'html': '🌐',
    };
    return iconMap[ext] || '📄';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function downloadFile(filename) {
    if (!state.activeSessionId) return;
    const url = `${API_BASE}/api/sessions/${state.activeSessionId}/files/${encodeURIComponent(filename)}`;
    window.open(url, '_blank');
}

async function handleRefreshFiles() {
    if (!state.activeSessionId) return;
    await loadFiles(state.activeSessionId);
}

// ====== Render Session List ======

function renderSessionList() {
    if (state.sessions.length === 0) {
        dom.sessionList.innerHTML = `
            <div class="empty-state small">
                <p>No tasks yet</p>
            </div>`;
        return;
    }

    // Filter by search
    const searchTerm = dom.searchInput?.value?.toLowerCase() || '';
    const filteredSessions = state.sessions.filter(s =>
        s.title.toLowerCase().includes(searchTerm)
    );

    if (filteredSessions.length === 0) {
        dom.sessionList.innerHTML = `
            <div class="empty-state small">
                <p>No matching tasks</p>
            </div>`;
        return;
    }

    dom.sessionList.innerHTML = filteredSessions.map(s => `
        <div class="task-item ${s.id === state.activeSessionId ? 'active' : ''}"
             onclick="selectSession('${s.id}')">
            <span class="task-icon ${s.status}"></span>
            <div class="task-info">
                <div class="task-title">${escapeHtml(s.title)}</div>
                <div class="task-meta">${formatTime(s.created_at)} • ${s.status}</div>
            </div>
            <button class="task-delete" onclick="handleDeleteSession('${s.id}', event)" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// ====== Prompt Gallery ======

function usePrompt(prompt) {
    if (!state.activeSessionId) {
        // Create a new session first, then populate the prompt
        handleNewSession().then(() => {
            setTimeout(() => {
                dom.chatInput.value = prompt;
                autoResizeTextarea(dom.chatInput);
                dom.chatInput.focus();
            }, 500);
        });
    } else {
        dom.chatInput.value = prompt;
        autoResizeTextarea(dom.chatInput);
        dom.chatInput.focus();
    }
}

// ====== Utilities ======

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

function escapeAttr(text) {
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatTime(isoStr) {
    try {
        return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}

function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// ====== Health Check ======

async function startHealthCheck() {
    const check = async () => {
        try {
            const health = await checkHealth();
            const dot = dom.healthStatus.querySelector('.status-dot');
            const text = dom.healthStatus.querySelector('.status-text');
            dot.className = 'status-dot connected';
            text.textContent = `Connected (${health.active_sessions} active)`;
        } catch {
            const dot = dom.healthStatus.querySelector('.status-dot');
            const text = dom.healthStatus.querySelector('.status-text');
            dot.className = 'status-dot';
            text.textContent = 'Disconnected';
        }
    };

    await check();
    setInterval(check, 10000);
}

// ====== File Upload Area ======

function setupFileUpload() {
    if (!dom.fileUploadArea || !dom.fileInput) return;

    dom.fileUploadArea.addEventListener('click', () => {
        dom.fileInput.click();
    });

    dom.fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dom.fileUploadArea.style.borderColor = 'var(--accent)';
        dom.fileUploadArea.style.background = 'var(--accent-light)';
    });

    dom.fileUploadArea.addEventListener('dragleave', () => {
        dom.fileUploadArea.style.borderColor = '';
        dom.fileUploadArea.style.background = '';
    });

    dom.fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dom.fileUploadArea.style.borderColor = '';
        dom.fileUploadArea.style.background = '';
        // Handle dropped files
        console.log('Files dropped:', e.dataTransfer.files);
    });

    dom.fileInput.addEventListener('change', () => {
        console.log('Files selected:', dom.fileInput.files);
    });
}

// ====== Initialization ======

async function init() {
    // Bind events
    dom.btnNewSession.addEventListener('click', handleNewSession);
    dom.chatForm.addEventListener('submit', handleSendMessage);
    dom.btnRefreshFiles?.addEventListener('click', handleRefreshFiles);
    dom.btnRecord?.addEventListener('click', handleRecord);
    dom.btnStop?.addEventListener('click', handleStopAgent);

    // Search filter
    dom.searchInput?.addEventListener('input', () => {
        renderSessionList();
    });

    // Auto-resize textarea
    dom.chatInput.addEventListener('input', () => {
        autoResizeTextarea(dom.chatInput);
    });

    // Allow Enter to send (Shift+Enter for newline)
    dom.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Setup file upload
    setupFileUpload();

    // Start health checks
    startHealthCheck();

    // Load existing sessions
    await refreshSessions();

    // Update input state
    updateInputState();
}

// Make functions available for onclick handlers
window.selectSession = selectSession;
window.handleDeleteSession = handleDeleteSession;
window.downloadFile = downloadFile;
window.usePrompt = usePrompt;

// Start the app
document.addEventListener('DOMContentLoaded', init);
