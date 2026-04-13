// KidsWin - Exports Header
// C API for C# P/Invoke bridge

#pragma once
#include <windows.h>

#ifdef KIDSWIN_EXPORTS
#define KIDSWIN_API extern "C" __declspec(dllexport)
#else
#define KIDSWIN_API extern "C" __declspec(dllimport)
#endif

// Initialize syscall resolver
KIDSWIN_API bool __stdcall Initialize();

// Find best Roblox process (most TaskScheduler jobs)
KIDSWIN_API DWORD __stdcall FindRobloxProcess();

// Connect to Roblox process by PID
KIDSWIN_API bool __stdcall Connect(DWORD pid);

// Disconnect from current process
KIDSWIN_API void __stdcall Disconnect();

// Execute Lua script
KIDSWIN_API int __stdcall ExecuteScript(const char* source, int length);

// Get DataModel address
KIDSWIN_API uintptr_t __stdcall GetDataModel();

// Get attached Roblox PID
KIDSWIN_API DWORD __stdcall GetRobloxPid();

// Redirect stdout to parent console
KIDSWIN_API void __stdcall RedirConsole();

// Count TaskScheduler jobs
KIDSWIN_API int __stdcall GetJobCount();

// Get last execution error string
KIDSWIN_API int __stdcall GetLastExecError(char* buffer, int bufferSize);

// Read memory from Roblox
KIDSWIN_API bool __stdcall ReadMemory(uintptr_t address, void* buffer, size_t size);

// Write memory to Roblox
KIDSWIN_API bool __stdcall WriteMemory(uintptr_t address, const void* buffer, size_t size);

// Get client info (player name, userId, jobId, placeId)
KIDSWIN_API bool __stdcall GetClientInfo(char* buffer, int bufferSize);
