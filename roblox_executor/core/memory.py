"""
Roblox External Executor - Core Memory Module
Handles reading/writing process memory using Windows API
"""
import ctypes
from ctypes import wintypes
import sys

if sys.platform != 'win32':
    raise ImportError("This module only works on Windows")

# Windows Constants
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

class ProcessMemory:
    def __init__(self, pid):
        self.pid = pid
        self.handle = None
        self.open()
    
    def open(self):
        """Open process handle"""
        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.OpenProcess(
            PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION,
            False,
            self.pid
        )
        if not self.handle:
            raise RuntimeError(f"Failed to open process {self.pid}")
    
    def close(self):
        """Close process handle"""
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
    
    def read_bytes(self, address, size):
        """Read bytes from memory address"""
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        
        result = kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if not result:
            raise RuntimeError(f"Failed to read memory at {hex(address)}")
        
        return buffer.raw[:bytes_read.value]
    
    def write_bytes(self, address, data):
        """Write bytes to memory address"""
        kernel32 = ctypes.windll.kernel32
        bytes_written = ctypes.c_size_t(0)
        
        result = kernel32.WriteProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            data,
            len(data),
            ctypes.byref(bytes_written)
        )
        
        if not result:
            raise RuntimeError(f"Failed to write memory at {hex(address)}")
        
        return bytes_written.value
    
    def read_int(self, address):
        """Read 4-byte integer"""
        data = self.read_bytes(address, 4)
        return int.from_bytes(data, 'little')
    
    def read_long(self, address):
        """Read 8-byte long"""
        data = self.read_bytes(address, 8)
        return int.from_bytes(data, 'little')
    
    def write_int(self, address, value):
        """Write 4-byte integer"""
        self.write_bytes(address, value.to_bytes(4, 'little'))
    
    def write_long(self, address, value):
        """Write 8-byte long"""
        self.write_bytes(address, value.to_bytes(8, 'little'))
    
    def allocate_memory(self, size):
        """Allocate memory in target process"""
        kernel32 = ctypes.windll.kernel32
        addr = kernel32.VirtualAllocEx(
            self.handle,
            None,
            size,
            MEM_COMMIT,
            PAGE_READWRITE
        )
        if not addr:
            raise RuntimeError("Failed to allocate memory")
        return addr
    
    def free_memory(self, address):
        """Free allocated memory"""
        kernel32 = ctypes.windll.kernel32
        kernel32.VirtualFreeEx(self.handle, ctypes.c_void_p(address), 0, 0x8000)
