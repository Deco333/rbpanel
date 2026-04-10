"""
Main entry point for Python External Executor
"""

import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memory import MemoryManager
from core.bridge import BridgeServer
from core.injector import Injector
from offsets.manager import OffsetManager
from ui.app import create_app


def main():
    """Initialize and run the executor"""
    print("=" * 60)
    print("🐍 Python External Executor")
    print("=" * 60)
    
    # Initialize components
    print("\n[*] Initializing components...")
    
    memory_manager = MemoryManager()
    bridge_server = BridgeServer(host="localhost", port=6767)
    offset_manager = OffsetManager()
    
    # Try to fetch latest offsets
    print("[*] Fetching offsets from imtheo.lol...")
    if offset_manager.fetch_offsets():
        print(f"    ✓ Offsets loaded for {offset_manager.get_roblox_version()}")
    else:
        print("    ⚠ Failed to fetch offsets, using defaults")
        offset_manager.load_default_offsets()
    
    # Create injector
    injector = Injector(memory_manager, bridge_server)
    
    # Create Flask app
    app = create_app(injector, bridge_server)
    
    print("\n[*] Starting web interface...")
    print("    → Open http://localhost:5000 in your browser")
    print("\n" + "=" * 60)
    
    # Run the application
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down...")
        injector.detach()
        bridge_server.stop()
        print("[*] Goodbye!")


if __name__ == "__main__":
    main()
