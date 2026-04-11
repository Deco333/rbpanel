"""
Roblox External Executor - Main UI Application
Flask web server with Attach, Execute, Clear buttons
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
import psutil
import requests
import threading
import sys
import os

# Import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.injector import Injector, find_roblox_process
from offsets.manager import OffsetsManager

app = Flask(__name__)

# Global state
executor_state = {
    "attached": False,
    "pid": None,
    "bridge_port": 6767,
    "internal_bridge_port": 6768,
    "output": []
}

offsets_manager = OffsetsManager()

# Routes
@app.route('/')
def index():
    """Main UI page"""
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    if filename.startswith('js/'):
        return send_from_directory('static/js', filename[3:])
    elif filename.startswith('css/'):
        return send_from_directory('static/css', filename[4:])
    return send_from_directory('static', filename)

@app.route('/api/processes', methods=['GET'])
def get_processes():
    """Get list of Roblox processes"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'Roblox' in proc.info['name']:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return jsonify(processes)

@app.route('/api/attach', methods=['POST'])
def attach():
    """Attach to Roblox process"""
    global executor_state
    
    data = request.json
    pid = data.get('pid')
    
    if not pid:
        # Auto-find Roblox process
        pid = find_roblox_process()
        if not pid:
            return jsonify({"success": False, "error": "No Roblox process found"}), 404
    
    try:
        pid = int(pid)
        # Verify process exists
        proc = psutil.Process(pid)
        if 'Roblox' not in proc.name():
            return jsonify({"success": False, "error": "Selected process is not Roblox"}), 400
        
        executor_state["attached"] = True
        executor_state["pid"] = pid
        executor_state["output"].append(f"[*] Attached to Roblox process (PID: {pid})")
        
        # Fetch latest offsets
        offsets_manager.fetch_offsets()
        
        return jsonify({
            "success": True,
            "message": f"Attached to process {pid}",
            "pid": pid,
            "offsets": offsets_manager.get_all_offsets()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/detach', methods=['POST'])
def detach():
    """Detach from Roblox process"""
    global executor_state
    
    executor_state["attached"] = False
    executor_state["pid"] = None
    executor_state["output"].append("[*] Detached from process")
    
    return jsonify({"success": True, "message": "Detached successfully"})

@app.route('/api/execute', methods=['POST'])
def execute():
    """Execute Lua script"""
    global executor_state
    
    if not executor_state["attached"]:
        return jsonify({"success": False, "error": "Not attached to any process"}), 400
    
    data = request.json
    script = data.get('script', '')
    
    if not script.strip():
        return jsonify({"success": False, "error": "No script provided"}), 400
    
    try:
        # Try to connect to internal bridge (injected DLL)
        try:
            response = requests.post(
                f"http://127.0.0.1:{executor_state['internal_bridge_port']}/api/execute",
                json={"script": script},
                timeout=2
            )
            result = response.json()
            output = result.get('output', [])
            for line in output:
                executor_state["output"].append(f"[Output] {line}")
            
            return jsonify({
                "success": True,
                "message": "Script executed via injected DLL",
                "output": output
            })
        except requests.exceptions.RequestException:
            # Bridge not available, use simulation mode
            executor_state["output"].append(f"[SIMULATION] Executing: {script[:50]}...")
            
            # Simulate print output
            import re
            matches = re.findall(r'print\(["\'](.+?)["\']\)', script)
            simulated_output = []
            for match in matches:
                simulated_output.append(match)
                executor_state["output"].append(f"[Output] {match}")
            
            if not matches:
                executor_state["output"].append("[SIMULATION] Script executed (no print statements)")
            
            return jsonify({
                "success": True,
                "message": "Script executed (simulation mode - DLL not injected)",
                "output": simulated_output,
                "warning": "DLL not injected. Running in simulation mode."
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear output"""
    global executor_state
    executor_state["output"] = []
    return jsonify({"success": True, "message": "Output cleared"})

@app.route('/api/inject', methods=['POST'])
def inject():
    """Inject bridge DLL into Roblox process"""
    global executor_state
    
    if not executor_state["attached"]:
        return jsonify({"success": False, "error": "Not attached to any process"}), 400
    
    dll_path = request.json.get('dll_path', 'bin/bridge.dll')
    
    try:
        injector = Injector(executor_state["pid"])
        injector.inject_dll(dll_path)
        
        executor_state["output"].append(f"[+] Injected bridge.dll into process {executor_state['pid']}")
        
        # Wait a moment for bridge to start
        import time
        time.sleep(1)
        
        # Check if bridge is running
        try:
            response = requests.get(
                f"http://127.0.0.1:{executor_state['internal_bridge_port']}/api/status",
                timeout=2
            )
            if response.status_code == 200:
                executor_state["output"].append("[+] Bridge server is running inside Roblox")
                return jsonify({
                    "success": True,
                    "message": "DLL injected successfully, bridge is running"
                })
        except:
            pass
        
        return jsonify({
            "success": True,
            "message": "DLL injected (bridge status unknown)"
        })
    except Exception as e:
        executor_state["output"].append(f"[-] Injection failed: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get executor status"""
    global executor_state
    
    bridge_status = "offline"
    clients = 0
    
    # Check internal bridge
    try:
        response = requests.get(
            f"http://127.0.0.1:{executor_state['internal_bridge_port']}/api/status",
            timeout=1
        )
        if response.status_code == 200:
            data = response.json()
            bridge_status = "online"
            clients = data.get('clients', 0)
    except:
        pass
    
    return jsonify({
        "attached": executor_state["attached"],
        "pid": executor_state["pid"],
        "bridge_status": bridge_status,
        "clients": clients,
        "output_lines": len(executor_state["output"])
    })

@app.route('/api/output', methods=['GET'])
def get_output():
    """Get output buffer"""
    global executor_state
    return jsonify(executor_state["output"][-50:])  # Last 50 lines

def run_ui(port=5000):
    """Run the UI server"""
    print(f"[*] Starting UI server on http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    run_ui()
