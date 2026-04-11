"""
Roblox External Executor - DLL Injector
Injects the bridge DLL into Roblox process
"""
import os
import sys

# Windows-only imports
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes
else:
    ctypes = None
    wintypes = None

# Windows Constants
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

class Injector:
    def __init__(self, pid):
        self.pid = pid
        self.handle = None
        
        if sys.platform != 'win32':
            raise RuntimeError("DLL injection only works on Windows")
    
    def open_process(self):
        """Open target process"""
        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.handle:
            error = ctypes.windll.kernel32.GetLastError()
            raise RuntimeError(f"Failed to open process. Error code: {error}")
        return True
    
    def close_process(self):
        """Close process handle"""
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
    
    def inject_dll(self, dll_path):
        """Inject DLL into target process using LoadLibraryA"""
        if not self.handle:
            self.open_process()
        
        kernel32 = ctypes.windll.kernel32
        get_proc_address = kernel32.GetProcAddress
        load_library_a = get_proc_address(kernel32.GetModuleHandleW("kernel32.dll"), "LoadLibraryA")
        
        if not load_library_a:
            raise RuntimeError("Failed to get LoadLibraryA address")
        
        # Convert to absolute path
        abs_dll_path = os.path.abspath(dll_path)
        dll_path_bytes = abs_dll_path.encode('ascii') + b'\x00'
        
        # Allocate memory in target process for DLL path
        path_size = len(dll_path_bytes)
        remote_path = kernel32.VirtualAllocEx(
            self.handle,
            None,
            path_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE
        )
        
        if not remote_path:
            raise RuntimeError("Failed to allocate memory for DLL path")
        
        # Write DLL path to allocated memory
        bytes_written = ctypes.c_size_t(0)
        result = kernel32.WriteProcessMemory(
            self.handle,
            remote_path,
            dll_path_bytes,
            path_size,
            ctypes.byref(bytes_written)
        )
        
        if not result:
            kernel32.VirtualFreeEx(self.handle, remote_path, 0, 0x8000)
            raise RuntimeError("Failed to write DLL path to memory")
        
        # Create remote thread to call LoadLibraryA
        thread_handle = kernel32.CreateRemoteThread(
            self.handle,
            None,
            0,
            load_library_a,
            remote_path,
            0,
            None
        )
        
        if not thread_handle:
            kernel32.VirtualFreeEx(self.handle, remote_path, 0, 0x8000)
            error = kernel32.GetLastError()
            raise RuntimeError(f"Failed to create remote thread. Error code: {error}")
        
        # Wait for thread to complete
        kernel32.WaitForSingleObject(thread_handle, 5000)
        
        # Clean up
        kernel32.CloseHandle(thread_handle)
        kernel32.VirtualFreeEx(self.handle, remote_path, 0, 0x8000)
        
        print(f"[+] Successfully injected DLL: {abs_dll_path}")
        return True
    
    def eject_dll(self, dll_handle):
        """Eject DLL from target process using FreeLibrary"""
        if not self.handle:
            self.open_process()
        
        kernel32 = ctypes.windll.kernel32
        get_proc_address = kernel32.GetProcAddress
        free_library = get_proc_address(kernel32.GetModuleHandleW("kernel32.dll"), "FreeLibrary")
        
        if not free_library:
            raise RuntimeError("Failed to get FreeLibrary address")
        
        # Create remote thread to call FreeLibrary
        thread_handle = kernel32.CreateRemoteThread(
            self.handle,
            None,
            0,
            free_library,
            ctypes.c_void_p(dll_handle),
            0,
            None
        )
        
        if not thread_handle:
            error = kernel32.GetLastError()
            raise RuntimeError(f"Failed to create remote thread for ejection. Error code: {error}")
        
        # Wait for thread to complete
        kernel32.WaitForSingleObject(thread_handle, 5000)
        kernel32.CloseHandle(thread_handle)
        
        print(f"[+] Successfully ejected DLL")
        return True

def find_roblox_process():
    """Find RobloxPlayerBeta process"""
    if sys.platform != 'win32':
        return None
    
    import psutil
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'RobloxPlayerBeta.exe' in proc.info['name']:
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return None

if __name__ == '__main__':
    # Test injection
    if sys.platform != 'win32':
        print("This script only works on Windows")
    else:
        pid = find_roblox_process()
        if pid:
            print(f"Found Roblox process: {pid}")
            injector = Injector(pid)
            # injector.inject_dll("path/to/bridge.dll")
        else:
            print("Roblox process not found")
