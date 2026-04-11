"""
Process injector module
Handles script injection into Roblox processes
"""

import time
from typing import Optional, List, Tuple
from .memory import MemoryManager
from .luau import LuauCompiler
from .bridge import BridgeServer


class Injector:
    """Handles script injection into Roblox processes"""
    
    def __init__(self, memory_manager: MemoryManager, bridge: BridgeServer):
        self.memory = memory_manager
        self.bridge = bridge
        self.compiler = LuauCompiler()
        self.attached_pid: Optional[int] = None
    
    def find_processes(self) -> List[Tuple[int, str]]:
        """Find all Roblox processes"""
        return self.memory.find_roblox_processes()
    
    def attach(self, pid: int) -> bool:
        """Attach to a Roblox process"""
        if self.memory.attach(pid):
            self.attached_pid = pid
            return True
        return False
    
    def detach(self):
        """Detach from current process"""
        self.memory.detach()
        self.attached_pid = None
    
    def is_attached(self) -> bool:
        """Check if attached to a process"""
        return self.memory.is_attached()
    
    def execute_script(self, source: str) -> bool:
        """
        Execute a Lua script in the attached process
        
        Returns True if script was queued successfully
        """
        if not self.is_attached():
            return False
        
        # Проверка наличия подключенного клиента (DLL в игре)
        if self.bridge.get_connected_count() == 0:
            print("Warning: No connected clients (Bridge DLL not injected)")
            # В реальном сценарии здесь была бы ошибка
            # Для демонстрации продолжаем но с предупреждением
            return False
        
        # Compile the script
        bytecode = self.compiler.compile(source)
        if not bytecode:
            print("Failed to compile script")
            return False
        
        # Encode to base64
        encoded = self.compiler.encode_base64(bytecode)
        
        # Queue for execution via bridge
        self.bridge.queue_script(encoded, self.attached_pid)
        
        return True
    
    def execute_file(self, filepath: str) -> bool:
        """Execute a Lua script from file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            return self.execute_script(source)
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get current injector status"""
        return {
            "attached": self.is_attached(),
            "pid": self.attached_pid,
            "bridge_running": self.bridge.is_running,
            "connected_clients": self.bridge.get_connected_count()
        }
