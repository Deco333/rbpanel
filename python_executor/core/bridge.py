"""
HTTP Bridge Server for communication with injected scripts
"""

import threading
import json
from typing import Optional, Dict, Callable, Set
from flask import Flask, request, Response


class BridgeServer:
    """HTTP server for bridge communication"""
    
    def __init__(self, host: str = "localhost", port: int = 6767):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Connected clients
        self.connected_pids: Set[int] = set()
        
        # Script storage
        self.pending_scripts: Dict[int, str] = {}
        self.script_order = 0
        
        # Callbacks
        self.on_script_request: Optional[Callable[[int], str]] = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/ping', methods=['POST'])
        def ping():
            pid = self._get_pid_from_request()
            if pid:
                self.connected_pids.add(pid)
            return Response("pong", mimetype='text/plain')
        
        @self.app.route('/handle', methods=['POST'])
        def handle():
            try:
                data = request.get_data(as_text=True)
                lines = data.splitlines()
                
                if len(lines) < 2:
                    return Response("", mimetype='text/plain')
                
                request_type = lines[0]
                pid = int(lines[1]) if lines[1].isdigit() else 0
                
                if request_type == "listen":
                    self.connected_pids.add(pid)
                    # Return pending script if available
                    if pid in self.pending_scripts:
                        script = self.pending_scripts.pop(pid)
                        return Response(script, mimetype='text/plain')
                    return Response("", mimetype='text/plain')
                
                elif request_type == "compile":
                    source = "\n".join(lines[3:]) if len(lines) > 3 else ""
                    # Handle compilation request
                    return Response("", mimetype='text/plain')
                
                return Response("", mimetype='text/plain')
                
            except Exception as e:
                print(f"Bridge error: {e}")
                return Response("", mimetype='text/plain')
        
        @self.app.route('/status', methods=['GET'])
        def status():
            return Response(json.dumps({
                "running": self.is_running,
                "connected_clients": len(self.connected_pids),
                "pids": list(self.connected_pids)
            }), mimetype='application/json')
    
    def _get_pid_from_request(self) -> Optional[int]:
        """Extract PID from request"""
        try:
            data = request.get_data(as_text=True)
            lines = data.splitlines()
            if len(lines) > 1 and lines[1].isdigit():
                return int(lines[1])
        except:
            pass
        return None
    
    def run_threaded(self):
        """Запуск сервера в текущем потоке с возможностью обновления статуса"""
        self.is_running = True
        # Запускаем Flask в этом потоке (блокирующе)
        self.app.run(
            host=self.host,
            port=self.port,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    def start(self):
        """Start the bridge server in background thread"""
        if self.is_running:
            return
        
        def run_server():
            self.is_running = True
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    def stop(self):
        """Stop the bridge server"""
        self.is_running = False
        self.connected_pids.clear()
    
    def queue_script(self, script: str, pid: Optional[int] = None):
        """Queue a script for execution"""
        self.script_order += 1
        if pid:
            self.pending_scripts[pid] = script
        else:
            # Queue for all connected clients
            for connected_pid in self.connected_pids:
                self.pending_scripts[connected_pid] = script
    
    def get_connected_count(self) -> int:
        """Get number of connected clients"""
        return len(self.connected_pids)
    
    def is_client_connected(self, pid: int) -> bool:
        """Check if specific client is connected"""
        return pid in self.connected_pids
    
    def update_client_count(self, count: int):
        """Update client count from external source (for main.py integration)"""
        # Это заглушка для будущего расширения
        pass
