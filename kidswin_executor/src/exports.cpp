// KidsWin - Exports Implementation
// Native API implementation for C# P/Invoke

#include "../include/exports.h"
#include "executor.h"
#include "process/scanner.h"
#include "syscalls/syscall_resolver.h"
#include <string>
#include <cstring>

static std::string g_lastError;
static ScriptExecutor* g_executor = nullptr;

KIDSWIN_API bool __stdcall Initialize() {
    return InitializeSyscalls();
}

KIDSWIN_API DWORD __stdcall FindRobloxProcess() {
    auto bestPid = ProcessScanner::FindBestRobloxProcess();
    return bestPid.value_or(0);
}

KIDSWIN_API bool __stdcall Connect(DWORD pid) {
    if (!g_executor) {
        g_executor = ScriptExecutor::GetInstance();
    }
    
    if (!g_executor->Connect(pid)) {
        g_lastError = "Failed to connect to process " + std::to_string(pid);
        return false;
    }
    
    return true;
}

KIDSWIN_API void __stdcall Disconnect() {
    if (g_executor) {
        g_executor->Disconnect();
    }
}

KIDSWIN_API int __stdcall ExecuteScript(const char* source, int length) {
    if (!g_executor) {
        g_lastError = "Not connected to any process";
        return -1;
    }
    
    if (!source || length <= 0) {
        g_lastError = "Invalid script source";
        return -1;
    }
    
    // Validate DataModel is still alive
    uintptr_t dataModel = g_executor->GetDataModel();
    HANDLE hProcess = g_executor->GetProcessHandle();
    
    if (!rblx::IsValidInstance(hProcess, dataModel)) {
        // DataModel destroyed (teleport), need to reconnect
        g_executor->Disconnect();
        g_lastError = "DataModel destroyed (teleport detected)";
        return -2;
    }
    
    std::string errorOut;
    std::string src(source, length);
    
    if (!g_executor->Execute(hProcess, g_executor->GetBaseAddress(), dataModel, src, errorOut)) {
        g_lastError = errorOut;
        return -3;
    }
    
    return 0; // Success
}

KIDSWIN_API uintptr_t __stdcall GetDataModel() {
    return g_executor ? g_executor->GetDataModel() : 0;
}

KIDSWIN_API DWORD __stdcall GetRobloxPid() {
    return g_executor ? g_executor->GetPid() : 0;
}

KIDSWIN_API void __stdcall RedirConsole() {
    AllocConsole();
    FILE* f = nullptr;
    freopen_s(&f, "CONOUT$", "w", stdout);
    freopen_s(&f, "CONIN$", "r", stdin);
}

KIDSWIN_API int __stdcall GetJobCount() {
    if (!g_executor) return 0;
    
    HANDLE hProcess = g_executor->GetProcessHandle();
    uintptr_t base = g_executor->GetBaseAddress();
    
    uintptr_t taskSched = 0;
    if (!ProcessScanner::ReadMemory(hProcess, base + offsets::Pointer::TaskScheduler, taskSched)) {
        return 0;
    }
    
    uintptr_t jobStart = 0, jobEnd = 0;
    ProcessScanner::ReadMemory(hProcess, taskSched + offsets::TaskScheduler::JobStart, jobStart);
    ProcessScanner::ReadMemory(hProcess, taskSched + offsets::TaskScheduler::JobEnd, jobEnd);
    
    return static_cast<int>((jobEnd - jobStart) / 0x8);
}

KIDSWIN_API int __stdcall GetLastExecError(char* buffer, int bufferSize) {
    if (!buffer || bufferSize <= 0) return -1;
    
    size_t copyLen = std::min(g_lastError.size(), static_cast<size_t>(bufferSize - 1));
    memcpy(buffer, g_lastError.c_str(), copyLen);
    buffer[copyLen] = '\0';
    
    return static_cast<int>(copyLen);
}

KIDSWIN_API bool __stdcall ReadMemory(uintptr_t address, void* buffer, size_t size) {
    if (!g_executor) return false;
    return ProcessScanner::ReadBytes(g_executor->GetProcessHandle(), address, buffer, size);
}

KIDSWIN_API bool __stdcall WriteMemory(uintptr_t address, const void* buffer, size_t size) {
    if (!g_executor) return false;
    return ProcessScanner::WriteBytes(g_executor->GetProcessHandle(), address, buffer, size);
}

KIDSWIN_API bool __stdcall GetClientInfo(char* buffer, int bufferSize) {
    // In production: Navigate to Players -> LocalPlayer and read Name, UserId
    // Also get JobId (GUID) and PlaceId from DataModel
    
    if (!buffer || bufferSize <= 0) return false;
    
    std::string info = R"({"name": "Unknown", "userId": 0, "jobId": "", "placeId": 0})";
    
    if (static_cast<int>(info.size()) >= bufferSize) {
        return false;
    }
    
    memcpy(buffer, info.c_str(), info.size() + 1);
    return true;
}
