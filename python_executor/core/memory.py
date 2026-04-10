"""
Memory management module for reading/writing process memory
Uses pywin32 for Windows API access
"""

import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple
import psutil


# Windows constants
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
MEM_RELEASE = 0x8000


class MemoryManager:
    """Handles process memory operations"""
    
    def __init__(self):
        self.process_handle: Optional[int] = None
        self.process_id: Optional[int] = None
        self.base_address: Optional[int] = None
        
    def find_roblox_processes(self) -> List[Tuple[int, str]]:
        """Find all Roblox processes"""
        roblox_processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'] or ""
                if name.lower().startswith('roblox'):
                    roblox_processes.append((proc.info['pid'], name))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return roblox_processes
    
    def attach(self, pid: int) -> bool:
        """Attach to a process by PID"""
        try:
            kernel32 = ctypes.windll.kernel32
            
            # Open process with full access
            handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not handle:
                return False
            
            self.process_handle = handle
            self.process_id = pid
            
            # Get base address of main module
            process = psutil.Process(pid)
            for module in process.memory_maps(grouped=False):
                if 'RobloxPlayerBeta.exe' in module.path:
                    self.base_address = int(module.addr, 16)
                    break
            
            return True
        except Exception as e:
            print(f"Failed to attach: {e}")
            return False
    
    def detach(self):
        """Detach from current process"""
        if self.process_handle:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
            self.process_id = None
            self.base_address = None
    
    def is_attached(self) -> bool:
        """Check if attached to a process"""
        return self.process_handle is not None and self.process_id is not None
    
    def read_bytes(self, address: int, size: int) -> bytes:
        """Read bytes from memory"""
        if not self.process_handle:
            raise RuntimeError("Not attached to any process")
        
        buffer = ctypes.create_string_buffer(size)
        bytes_read = wintypes.SIZE_T()
        
        result = ctypes.windll.kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if not result:
            raise RuntimeError(f"Failed to read memory at {hex(address)}")
        
        return buffer.raw[:bytes_read.value]
    
    def read_ulonglong(self, address: int) -> int:
        """Read an 8-byte unsigned integer"""
        data = self.read_bytes(address, 8)
        return int.from_bytes(data, byteorder='little')
    
    def read_uint(self, address: int) -> int:
        """Read a 4-byte unsigned integer"""
        data = self.read_bytes(address, 4)
        return int.from_bytes(data, byteorder='little')
    
    def write_bytes(self, address: int, data: bytes) -> bool:
        """Write bytes to memory"""
        if not self.process_handle:
            raise RuntimeError("Not attached to any process")
        
        bytes_written = wintypes.SIZE_T()
        
        result = ctypes.windll.kernel32.WriteProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            data,
            len(data),
            ctypes.byref(bytes_written)
        )
        
        return result != 0
    
    def allocate_memory(self, size: int) -> Optional[int]:
        """Allocate memory in target process"""
        if not self.process_handle:
            return None
        
        addr = ctypes.windll.kernel32.VirtualAllocEx(
            self.process_handle,
            None,
            size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE
        )
        
        return addr if addr else None
    
    def free_memory(self, address: int) -> bool:
        """Free allocated memory"""
        if not self.process_handle:
            return False
        
        return ctypes.windll.kernel32.VirtualFreeEx(
            self.process_handle,
            ctypes.c_void_p(address),
            0,
            MEM_RELEASE
        ) != 0
    
    def get_base_address(self) -> int:
        """Get the base address of RobloxPlayerBeta.exe"""
        return self.base_address or 0
