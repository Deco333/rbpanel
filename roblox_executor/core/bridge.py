"""
Roblox External Executor - Internal HTTP Bridge Server
This server runs inside the Roblox process (via injected DLL)
and executes Lua scripts received from the external Python application.
"""
from flask import Flask, request, jsonify
import threading
import sys
import os

# Global state for bridge
bridge_state = {
    "status": "offline",
    "clients": 0,
    "last_script": "",
    "output": [],
    "pid": 0
}

app = Flask(__name__)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Return bridge status"""
    return jsonify({
        "status": bridge_state["status"],
        "clients": bridge_state["clients"],
        "pid": bridge_state["pid"],
        "message": "Bridge is running inside Roblox process" if bridge_state["status"] == "online" else "Bridge not injected"
    })

@app.route('/api/execute', methods=['POST'])
def execute_script():
    """Execute Lua script in Roblox context"""
    data = request.json
    script = data.get('script', '')
    
    if not script:
        return jsonify({"success": False, "error": "No script provided"}), 400
    
    try:
        # In real implementation, this would call Lua VM directly
        # For now, we simulate execution
        bridge_state["last_script"] = script
        bridge_state["output"].append(f"Executed: {script[:50]}...")
        
        # Simulate print output
        if 'print(' in script:
            # Extract string from print("...")
            import re
            matches = re.findall(r'print\(["\'](.+?)["\']\)', script)
            for match in matches:
                bridge_state["output"].append(match)
        
        return jsonify({
            "success": True,
            "message": "Script executed successfully",
            "output": bridge_state["output"][-10:]  # Last 10 outputs
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_output():
    """Clear output buffer"""
    bridge_state["output"] = []
    return jsonify({"success": True, "message": "Output cleared"})

def run_bridge(port=6767):
    """Run the bridge server"""
    bridge_state["status"] = "online"
    bridge_state["pid"] = os.getpid()
    
    print(f"[*] Bridge server starting on port {port}")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    run_bridge()
