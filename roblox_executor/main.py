"""
Roblox External Executor - Main Entry Point
Launches both the UI server and bridge server
"""
import sys
import os
import threading
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import run_ui
from core.bridge import run_bridge

def main():
    print("=" * 60)
    print("🎮 Roblox External Executor v1.0")
    print("=" * 60)
    print()
    print("Starting services...")
    print()
    
    # Start bridge server in background thread (port 6767)
    # This is for external communication
    bridge_thread = threading.Thread(
        target=run_bridge,
        kwargs={'port': 6767},
        daemon=True
    )
    bridge_thread.start()
    time.sleep(1)  # Give bridge time to start
    
    # Start UI server (port 5000)
    print("✅ Bridge server started on http://localhost:6767")
    print()
    print("🌐 Opening UI at http://localhost:5000")
    print()
    print("Instructions:")
    print("1. Open http://localhost:5000 in your browser")
    print("2. Click 'Refresh' to find Roblox processes")
    print("3. Select a process and click 'Attach'")
    print("4. (Optional) Click 'Inject DLL' for real execution")
    print("5. Write Lua script and click 'Execute' or press Ctrl+Enter")
    print()
    print("Note: DLL injection requires Windows + Administrator privileges")
    print("      Without DLL, scripts run in simulation mode")
    print()
    print("=" * 60)
    
    try:
        run_ui(port=5000)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)

if __name__ == '__main__':
    main()
