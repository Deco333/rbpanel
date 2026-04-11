// Roblox External Executor - Main JavaScript

const API_BASE = '';

// DOM Elements
const processSelect = document.getElementById('process-select');
const refreshProcessesBtn = document.getElementById('refresh-processes');
const btnAttach = document.getElementById('btn-attach');
const btnInject = document.getElementById('btn-inject');
const btnDetach = document.getElementById('btn-detach');
const btnExecute = document.getElementById('btn-execute');
const btnClear = document.getElementById('btn-clear');
const btnClearOutput = document.getElementById('btn-clear-output');
const scriptEditor = document.getElementById('script-editor');
const outputConsole = document.getElementById('output-console');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const pidDisplay = document.getElementById('pid-display');
const bridgeStatus = document.getElementById('bridge-status');

let isAttached = false;
let currentPid = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadProcesses();
    updateStatus();
    setInterval(updateStatus, 3000);
});

// Load Roblox processes
async function loadProcesses() {
    try {
        const response = await fetch(`${API_BASE}/api/processes`);
        const processes = await response.json();
        
        processSelect.innerHTML = '<option value="">-- Select Roblox Process --</option>';
        
        if (processes.length === 0) {
            const option = document.createElement('option');
            option.textContent = 'No Roblox processes found';
            option.disabled = true;
            processSelect.appendChild(option);
            return;
        }
        
        processes.forEach(proc => {
            const option = document.createElement('option');
            option.value = proc.pid;
            option.textContent = `${proc.name} (PID: ${proc.pid})`;
            processSelect.appendChild(option);
        });
        
        log('Processes refreshed', 'info');
    } catch (error) {
        log(`Failed to load processes: ${error.message}`, 'error');
    }
}

// Attach to process
async function attach() {
    const pid = processSelect.value || null;
    
    try {
        const response = await fetch(`${API_BASE}/api/attach`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pid: pid ? parseInt(pid) : null })
        });
        
        const result = await response.json();
        
        if (result.success) {
            isAttached = true;
            currentPid = result.pid;
            updateUIState();
            log(`Attached to process ${result.pid}`, 'success');
            
            if (result.offsets) {
                log(`Loaded ${Object.keys(result.offsets).length} offsets`, 'info');
            }
        } else {
            log(`Attach failed: ${result.error}`, 'error');
        }
    } catch (error) {
        log(`Attach error: ${error.message}`, 'error');
    }
}

// Detach from process
async function detach() {
    try {
        const response = await fetch(`${API_BASE}/api/detach`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            isAttached = false;
            currentPid = null;
            updateUIState();
            log('Detached from process', 'info');
        }
    } catch (error) {
        log(`Detach error: ${error.message}`, 'error');
    }
}

// Inject DLL
async function injectDLL() {
    if (!isAttached) {
        log('Please attach to a process first', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/inject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dll_path: 'bin/bridge.dll' })
        });
        
        const result = await response.json();
        
        if (result.success) {
            log(result.message, 'success');
            if (result.warning) {
                log(result.warning, 'warning');
            }
        } else {
            log(`Injection failed: ${result.error}`, 'error');
        }
    } catch (error) {
        log(`Injection error: ${error.message}`, 'error');
    }
}

// Execute script
async function executeScript() {
    if (!isAttached) {
        log('Please attach to a process first', 'warning');
        return;
    }
    
    const script = scriptEditor.value.trim();
    if (!script) {
        log('No script to execute', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script: script })
        });
        
        const result = await response.json();
        
        if (result.success) {
            log('Script executed', 'success');
            
            if (result.output && result.output.length > 0) {
                result.output.forEach(line => {
                    log(line, 'output');
                });
            }
            
            if (result.warning) {
                log(result.warning, 'warning');
            }
        } else {
            log(`Execution failed: ${result.error}`, 'error');
        }
    } catch (error) {
        log(`Execution error: ${error.message}`, 'error');
    }
}

// Clear editor
function clearEditor() {
    scriptEditor.value = '';
    scriptEditor.focus();
    log('Editor cleared', 'info');
}

// Clear output
async function clearOutput() {
    try {
        await fetch(`${API_BASE}/api/clear`, { method: 'POST' });
        outputConsole.innerHTML = '<div class="log-entry info">[*] Output cleared</div>';
    } catch (error) {
        log(`Clear error: ${error.message}`, 'error');
    }
}

// Update status
async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const status = await response.json();
        
        if (status.attached) {
            statusIndicator.className = 'status-dot online';
            statusText.textContent = 'Connected';
            pidDisplay.textContent = `PID: ${status.pid}`;
            
            if (status.bridge_status === 'online') {
                bridgeStatus.textContent = `Bridge: Online (${status.clients} clients)`;
                bridgeStatus.style.color = 'var(--accent-green)';
            } else {
                bridgeStatus.textContent = 'Bridge: Offline (simulation mode)';
                bridgeStatus.style.color = 'var(--accent-yellow)';
            }
        } else {
            statusIndicator.className = 'status-dot offline';
            statusText.textContent = 'Disconnected';
            pidDisplay.textContent = '';
            bridgeStatus.textContent = 'Bridge: Offline';
            bridgeStatus.style.color = 'var(--text-secondary)';
        }
    } catch (error) {
        // Silently fail for status updates
    }
}

// Update UI state based on attachment
function updateUIState() {
    btnAttach.disabled = isAttached;
    btnDetach.disabled = !isAttached;
    btnInject.disabled = !isAttached;
    btnExecute.disabled = !isAttached;
    processSelect.disabled = isAttached;
    refreshProcessesBtn.disabled = isAttached;
}

// Log message to console
function log(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    
    outputConsole.appendChild(entry);
    outputConsole.scrollTop = outputConsole.scrollHeight;
}

// Event listeners
refreshProcessesBtn.addEventListener('click', loadProcesses);
btnAttach.addEventListener('click', attach);
btnDetach.addEventListener('click', detach);
btnInject.addEventListener('click', injectDLL);
btnExecute.addEventListener('click', executeScript);
btnClear.addEventListener('click', clearEditor);
btnClearOutput.addEventListener('click', clearOutput);

// Keyboard shortcuts
scriptEditor.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        executeScript();
    }
});
