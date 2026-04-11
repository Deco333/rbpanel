"""
Flask web application for the executor UI
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from typing import Optional


def create_app(injector=None, bridge=None):
    """Create and configure the Flask application"""
    
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    CORS(app)
    
    # Store references to core components
    app.injector = injector
    app.bridge = bridge
    
    @app.route('/')
    def index():
        """Main UI page"""
        return render_template('index.html')
    
    @app.route('/api/processes', methods=['GET'])
    def get_processes():
        """Get list of Roblox processes"""
        if not app.injector:
            return jsonify({"error": "Injector not initialized"}), 500
        
        processes = app.injector.find_processes()
        return jsonify({
            "processes": [{"pid": pid, "name": name} for pid, name in processes]
        })
    
    @app.route('/api/attach', methods=['POST'])
    def attach():
        """Attach to a process"""
        if not app.injector:
            return jsonify({"error": "Injector not initialized"}), 500
        
        data = request.get_json()
        pid = data.get('pid')
        
        if not pid:
            return jsonify({"error": "PID required"}), 400
        
        success = app.injector.attach(pid)
        
        if success:
            # Start bridge if not running
            if not app.bridge.is_running:
                app.bridge.start()
            
            return jsonify({"success": True, "pid": pid})
        else:
            return jsonify({"success": False, "error": "Failed to attach"}), 400
    
    @app.route('/api/detach', methods=['POST'])
    def detach():
        """Detach from current process"""
        if not app.injector:
            return jsonify({"error": "Injector not initialized"}), 500
        
        app.injector.detach()
        return jsonify({"success": True})
    
    @app.route('/api/execute', methods=['POST'])
    def execute():
        """Execute a script"""
        if not app.injector:
            return jsonify({"error": "Injector not initialized"}), 500
        
        data = request.get_json()
        script = data.get('script', '')
        
        if not script.strip():
            return jsonify({"error": "Script is empty"}), 400
        
        if not app.injector.is_attached():
            return jsonify({
                "success": False, 
                "error": "Not attached to any process"
            }), 400
        
        # Проверка на наличие подключенного клиента
        client_count = app.bridge.get_connected_count()
        if client_count == 0:
            # РЕЖИМ СИМУЛЯЦИИ для демонстрации (удалите в продакшене)
            # В реальном сценарии раскомментируйте код ниже:
            """
            return jsonify({
                "success": False, 
                "error": "Нет подключенных клиентов (Bridge DLL не внедрена в игру).",
                "hint": "Для работы требуется внедрение DLL."
            }), 400
            """
            
            # СИМУЛЯЦИЯ выполнения (для тестов без DLL)
            import logging
            logging.info(f"[SIMULATED] Executing script in PID {app.injector.attached_pid}")
            simulated_output = f"[Simulated Output]\nScript executed successfully\n> {script[:100]}..."
            return jsonify({
                "success": True,
                "message": "Скрипт выполнен (симуляция)",
                "output": simulated_output,
                "warning": "DLL не подключена. Это симуляция выполнения."
            })
        
        success = app.injector.execute_script(script)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Execution failed"}), 400
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """Get executor status"""
        if not app.injector:
            return jsonify({"error": "Injector not initialized"}), 500
        
        return jsonify(app.injector.get_status())
    
    @app.route('/api/bridge', methods=['GET'])
    def bridge_status():
        """Get bridge server status"""
        if not app.bridge:
            return jsonify({"error": "Bridge not initialized"}), 500
        
        return jsonify({
            "running": app.bridge.is_running,
            "clients": app.bridge.get_connected_count()
        })
    
    return app
