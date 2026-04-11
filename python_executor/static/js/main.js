// Main JavaScript for Python External Executor UI

class ExecutorUI {
    constructor() {
        this.attached = false;
        this.currentPid = null;
        
        // DOM Elements
        this.elements = {
            statusIndicator: document.getElementById('status-indicator'),
            pidDisplay: document.getElementById('pid-display'),
            bridgeStatus: document.getElementById('bridge-status'),
            processSelect: document.getElementById('process-select'),
            refreshBtn: document.getElementById('refresh-btn'),
            attachBtn: document.getElementById('attach-btn'),
            detachBtn: document.getElementById('detach-btn'),
            executeBtn: document.getElementById('execute-btn'),
            clearBtn: document.getElementById('clear-btn'),
            scriptEditor: document.getElementById('script-editor'),
            consoleOutput: document.getElementById('console-output'),
            consoleClearBtn: document.getElementById('console-clear-btn')
        };
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.refreshProcesses();
        this.log('info', 'Executor UI initialized');
    }
    
    bindEvents() {
        this.elements.refreshBtn.addEventListener('click', () => this.refreshProcesses());
        this.elements.attachBtn.addEventListener('click', () => this.attach());
        this.elements.detachBtn.addEventListener('click', () => this.detach());
        this.elements.executeBtn.addEventListener('click', () => this.execute());
        this.elements.clearBtn.addEventListener('click', () => this.clear());
        this.elements.consoleClearBtn.addEventListener('click', () => this.clearConsole());
    }
    
    async refreshProcesses() {
        try {
            const response = await fetch('/api/processes');
            const data = await response.json();
            
            this.elements.processSelect.innerHTML = '<option value="">-- Select a process --</option>';
            
            if (data.processes && data.processes.length > 0) {
                data.processes.forEach(proc => {
                    const option = document.createElement('option');
                    option.value = proc.pid;
                    option.textContent = `${proc.name} (PID: ${proc.pid})`;
                    this.elements.processSelect.appendChild(option);
                });
                this.log('success', `Found ${data.processes.length} Roblox process(es)`);
            } else {
                this.log('info', 'No Roblox processes found. Start Roblox first.');
            }
        } catch (error) {
            this.log('error', `Failed to refresh processes: ${error.message}`);
        }
    }
    
    async attach() {
        const pid = this.elements.processSelect.value;
        
        if (!pid) {
            this.log('error', 'Please select a process first');
            return;
        }
        
        try {
            this.elements.attachBtn.disabled = true;
            this.log('info', `Attaching to process ${pid}...`);
            
            const response = await fetch('/api/attach', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pid: parseInt(pid) })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.attached = true;
                this.currentPid = pid;
                this.updateUIState();
                this.log('success', `Successfully attached to process ${pid}`);
                this.checkBridgeStatus();
            } else {
                this.log('error', `Failed to attach: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            this.log('error', `Attach failed: ${error.message}`);
        } finally {
            this.elements.attachBtn.disabled = false;
        }
    }
    
    async detach() {
        try {
            this.log('info', 'Detaching from process...');
            
            const response = await fetch('/api/detach', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.attached = false;
                this.currentPid = null;
                this.updateUIState();
                this.log('success', 'Successfully detached');
            }
        } catch (error) {
            this.log('error', `Detach failed: ${error.message}`);
        }
    }
    
    async execute() {
        const script = this.elements.scriptEditor.value.trim();
        
        if (!script) {
            this.log('error', 'Script editor is empty');
            return;
        }
        
        if (!this.attached) {
            this.log('error', 'Not attached to any process');
            return;
        }
        
        try {
            this.elements.executeBtn.disabled = true;
            this.log('script', 'Executing script...');
            
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.log('success', 'Script executed successfully');
                // Показываем вывод если есть
                if (data.output) {
                    this.log('info', `Output: ${data.output}`);
                }
                // Показываем предупреждение если есть (для симуляции)
                if (data.warning) {
                    this.log('warning', `⚠️ ${data.warning}`);
                }
            } else {
                this.log('error', `Execution failed: ${data.error || 'Unknown error'}`);
                // Показываем подсказку если есть
                if (data.hint) {
                    this.log('warning', `💡 ${data.hint}`);
                }
            }
        } catch (error) {
            this.log('error', `Execute failed: ${error.message}`);
        } finally {
            this.elements.executeBtn.disabled = false;
        }
    }
    
    clear() {
        this.elements.scriptEditor.value = '';
        this.log('info', 'Editor cleared');
    }
    
    clearConsole() {
        this.elements.consoleOutput.innerHTML = '';
        this.log('info', 'Console cleared');
    }
    
    async checkBridgeStatus() {
        try {
            const response = await fetch('/api/bridge');
            const data = await response.json();
            
            if (data.running) {
                this.elements.bridgeStatus.textContent = `Online (${data.clients} clients)`;
                this.elements.bridgeStatus.className = 'status-value connected';
            } else {
                this.elements.bridgeStatus.textContent = 'Offline';
                this.elements.bridgeStatus.className = 'status-value disconnected';
            }
        } catch (error) {
            this.elements.bridgeStatus.textContent = 'Error';
            this.elements.bridgeStatus.className = 'status-value disconnected';
        }
    }
    
    updateUIState() {
        if (this.attached) {
            this.elements.statusIndicator.textContent = 'Connected';
            this.elements.statusIndicator.className = 'status-value connected';
            this.elements.pidDisplay.textContent = this.currentPid;
            this.elements.attachBtn.disabled = true;
            this.elements.detachBtn.disabled = false;
            this.elements.executeBtn.disabled = false;
            this.elements.processSelect.disabled = true;
        } else {
            this.elements.statusIndicator.textContent = 'Disconnected';
            this.elements.statusIndicator.className = 'status-value disconnected';
            this.elements.pidDisplay.textContent = '-';
            this.elements.attachBtn.disabled = false;
            this.elements.detachBtn.disabled = true;
            this.elements.executeBtn.disabled = true;
            this.elements.processSelect.disabled = false;
        }
    }
    
    log(type, message) {
        const line = document.createElement('div');
        line.className = `console-line ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        line.textContent = `[${timestamp}] ${message}`;
        
        this.elements.consoleOutput.appendChild(line);
        this.elements.consoleOutput.scrollTop = this.elements.consoleOutput.scrollHeight;
    }
}

// Initialize the UI when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.executorUI = new ExecutorUI();
    
    // Periodically check bridge status
    setInterval(() => {
        if (window.executorUI.attached) {
            window.executorUI.checkBridgeStatus();
        }
    }, 5000);
});
