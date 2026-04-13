// KidsWin - Script Executor (Core Execution Engine)
// External memory manipulation + SpoofWith injection technique

#pragma once
#include <windows.h>
#include <string>
#include <vector>
#include <optional>
#include <mutex>
#include <thread>
#include <atomic>
#include "../include/offsets.h"
#include "../include/unc_payload.h"
#include "memory/instance_walker.h"
#include "process/scanner.h"
#include "syscalls/syscall_resolver.h"

// Forward declaration for HTTP server
namespace httplib { class Server; }

struct ModifiedModule {
    uintptr_t moduleAddress;
    uintptr_t originalBytecodePtr;
    size_t originalBytecodeSize;
    uint32_t originalCapabilities;
    uintptr_t embeddedAddress;
};

class ScriptExecutor {
private:
    HANDLE m_hProcess = nullptr;
    DWORD m_pid = 0;
    uintptr_t m_baseAddress = 0;
    uintptr_t m_dataModel = 0;
    
    // Cached navigation addresses
    uintptr_t m_coreGui = 0;
    uintptr_t m_robloxGui = 0;
    uintptr_t m_modules = 0;
    uintptr_t m_playerList = 0;
    uintptr_t m_playerListManager = 0;
    
    // Module tracking
    std::vector<uintptr_t> m_cachedModules;
    size_t m_moduleIndex = 0;
    std::vector<ModifiedModule> m_modifiedModules;
    
    // State
    bool m_initialized = false;
    std::atomic<bool> m_httpServerRunning{false};
    std::unique_ptr<httplib::Server> m_httpServer;
    std::mutex m_scriptQueueMutex;
    std::vector<std::string> m_scriptQueue;
    
    static ScriptExecutor* s_instance;

public:
    static ScriptExecutor* GetInstance() {
        if (!s_instance) s_instance = new ScriptExecutor();
        return s_instance;
    }
    
    bool Execute(HANDLE hProcess, uintptr_t base, uintptr_t dataModel, 
                 const std::string& source, std::string& errorOut);
    
    bool Connect(DWORD pid);
    void Disconnect();
    
    uintptr_t GetDataModel() const { return m_dataModel; }
    DWORD GetPid() const { return m_pid; }
    HANDLE GetProcessHandle() const { return m_hProcess; }
    uintptr_t GetBaseAddress() const { return m_baseAddress; }
    
    void QueueScript(const std::string& script);
    std::string DequeueScript();
    
private:
    bool CacheNavigation(HANDLE hProcess, uintptr_t dataModel, std::string& errorOut);
    std::optional<uintptr_t> FindUnloadedModule(HANDLE hProcess, std::string& outName);
    bool InjectViaSpoof(HANDLE hProcess, const std::string& luaSource, 
                        const std::string& label, std::string& errorOut);
    bool SetBytecode(HANDLE hProcess, uintptr_t moduleScript, 
                     const std::vector<uint8_t>& rsb1Data);
    void SimulateEscKey();
    void RestoreAllModules();
    bool WaitForConfirmation(HANDLE hProcess, int timeoutMs = 4000);
    void StartHttpServer();
    void StopHttpServer();
    
    bool CompileAndSign(const std::string& luaSource, std::vector<uint8_t>& outBytecode);
    bool CompressWithZstd(const std::vector<uint8_t>& input, std::vector<uint8_t>& output);
};

inline ScriptExecutor* ScriptExecutor::s_instance = nullptr;

// Implementation
inline bool ScriptExecutor::Execute(HANDLE hProcess, uintptr_t base, uintptr_t dataModel,
                                     const std::string& source, std::string& errorOut) {
    // Phase 1: First call - initialize session
    if (!m_initialized) {
        // Cache navigation
        if (!CacheNavigation(hProcess, dataModel, errorOut)) {
            return false;
        }
        
        // Start HTTP server
        StartHttpServer();
        
        // Check for existing session recovery (KidsWin folder already in CoreGui)
        auto kidsWinFolder = rblx::FindChildByName(hProcess, m_coreGui, "KidsWin");
        
        if (!kidsWinFolder.has_value()) {
            // Inject init script via spoof
            std::string initScript = GetInitScript();
            if (!InjectViaSpoof(hProcess, initScript, "init", errorOut)) {
                errorOut = "Failed to inject init script: " + errorOut;
                return false;
            }
            
            // Wait for Lua listener to start
            Sleep(3000);
        }
        
        m_initialized = true;
    }
    
    // Phase 2: Every call - queue script for Lua worker
    if (!source.empty()) {
        QueueScript(source);
    }
    
    return true;
}

inline bool ScriptExecutor::Connect(DWORD pid) {
    Disconnect();
    
    m_pid = pid;
    m_hProcess = OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        FALSE, pid
    );
    
    if (!m_hProcess) {
        return false;
    }
    
    m_baseAddress = ProcessScanner::GetProcessBaseAddress(pid);
    if (!m_baseAddress) {
        CloseHandle(m_hProcess);
        m_hProcess = nullptr;
        return false;
    }
    
    // Initialize syscalls
    InitializeSyscalls();
    
    // Find DataModel
    // Method 1: Try FakeDataModelPointer
    uintptr_t fakeDmPtr = 0;
    if (ProcessScanner::ReadMemory(m_hProcess, m_baseAddress + offsets::Pointer::FakeDataModelPointer, fakeDmPtr)) {
        uintptr_t dm = 0;
        if (ProcessScanner::ReadMemory(m_hProcess, fakeDmPtr + 0x1C0, dm)) {
            if (rblx::IsValidInstance(m_hProcess, dm) && 
                rblx::ReadClassName(m_hProcess, dm) == "DataModel") {
                m_dataModel = dm;
            }
        }
    }
    
    // Method 2: Fallback - scan TaskScheduler jobs
    if (!m_dataModel) {
        uintptr_t taskSched = 0;
        if (ProcessScanner::ReadMemory(m_hProcess, m_baseAddress + offsets::Pointer::TaskScheduler, taskSched)) {
            uintptr_t jobStart = 0, jobEnd = 0;
            ProcessScanner::ReadMemory(m_hProcess, taskSched + offsets::TaskScheduler::JobStart, jobStart);
            ProcessScanner::ReadMemory(m_hProcess, taskSched + offsets::TaskScheduler::JobEnd, jobEnd);
            
            for (uintptr_t job = jobStart; job < jobEnd; job += 0x8) {
                uintptr_t jobPtr = 0;
                if (!ProcessScanner::ReadMemory(m_hProcess, job, jobPtr)) continue;
                
                // Scan job for DataModel pointers
                for (size_t i = 0; i < 0x80; ++i) {
                    uintptr_t candidate = 0;
                    if (!ProcessScanner::ReadMemory(m_hProcess, jobPtr + i * 0x8, candidate)) continue;
                    
                    if (rblx::IsValidInstance(m_hProcess, candidate) &&
                        rblx::ReadClassName(m_hProcess, candidate) == "DataModel") {
                        m_dataModel = candidate;
                        break;
                    }
                }
                if (m_dataModel) break;
            }
        }
    }
    
    if (!m_dataModel) {
        CloseHandle(m_hProcess);
        m_hProcess = nullptr;
        return false;
    }
    
    // Execute with empty source to trigger init-only injection
    std::string error;
    return Execute(m_hProcess, m_baseAddress, m_dataModel, "", error);
}

inline void ScriptExecutor::Disconnect() {
    if (m_httpServerRunning) {
        StopHttpServer();
    }
    
    RestoreAllModules();
    
    if (m_hProcess) {
        CloseHandle(m_hProcess);
        m_hProcess = nullptr;
    }
    
    m_pid = 0;
    m_baseAddress = 0;
    m_dataModel = 0;
    m_coreGui = 0;
    m_robloxGui = 0;
    m_modules = 0;
    m_playerList = 0;
    m_playerListManager = 0;
    m_cachedModules.clear();
    m_modifiedModules.clear();
    m_initialized = false;
}

inline bool ScriptExecutor::CacheNavigation(HANDLE hProcess, uintptr_t dataModel, std::string& errorOut) {
    // DataModel -> CoreGui (by ClassName)
    auto coreGui = rblx::FindChildByClassName(hProcess, dataModel, "CoreGui");
    if (!coreGui.has_value()) {
        errorOut = "CoreGui not found";
        return false;
    }
    m_coreGui = coreGui.value();
    
    // CoreGui -> RobloxGui (by Name)
    auto robloxGui = rblx::FindChildByName(hProcess, m_coreGui, "RobloxGui");
    if (!robloxGui.has_value()) {
        errorOut = "RobloxGui not found";
        return false;
    }
    m_robloxGui = robloxGui.value();
    
    // RobloxGui -> Modules (by Name)
    auto modules = rblx::FindChildByName(hProcess, m_robloxGui, "Modules");
    if (!modules.has_value()) {
        errorOut = "Modules not found";
        return false;
    }
    m_modules = modules.value();
    
    // Modules -> PlayerList (by Name)
    auto playerList = rblx::FindChildByName(hProcess, m_modules, "PlayerList");
    if (!playerList.has_value()) {
        // Try alternative name
        playerList = rblx::FindChildByClassName(hProcess, m_modules, "Frame");
    }
    if (!playerList.has_value()) {
        errorOut = "PlayerList not found";
        return false;
    }
    m_playerList = playerList.value();
    
    // PlayerList -> PlayerListManager (by Name)
    auto playerListManager = rblx::FindChildByName(hProcess, m_playerList, "PlayerListManager");
    if (!playerListManager.has_value()) {
        // Try finding any child that could be the manager
        auto children = rblx::GetChildren(hProcess, m_playerList);
        for (auto child : children) {
            std::string name = rblx::ReadInstanceName(hProcess, child);
            if (name.find("Manager") != std::string::npos || 
                name.find("List") != std::string::npos) {
                playerListManager = child;
                break;
            }
        }
    }
    if (!playerListManager.has_value()) {
        errorOut = "PlayerListManager not found";
        return false;
    }
    m_playerListManager = playerListManager.value();
    
    return true;
}

inline std::optional<uintptr_t> ScriptExecutor::FindUnloadedModule(HANDLE hProcess, std::string& outName) {
    // Return cached module if available
    if (!m_cachedModules.empty()) {
        size_t idx = m_moduleIndex % m_cachedModules.size();
        uintptr_t module = m_cachedModules[idx];
        
        if (rblx::IsValidInstance(hProcess, module)) {
            outName = rblx::GetInstancePath(hProcess, module);
            m_moduleIndex++;
            return module;
        }
        
        // Module no longer valid, clear cache
        m_cachedModules.clear();
        m_moduleIndex = 0;
    }
    
    // Scan for unloaded modules
    auto children = rblx::GetChildren(hProcess, m_modules);
    
    for (uintptr_t child : children) {
        std::string className = rblx::ReadClassName(hProcess, child);
        if (className != "ModuleScript") continue;
        
        std::string name = rblx::ReadInstanceName(hProcess, child);
        std::string lowerName = name;
        std::transform(lowerName.begin(), lowerName.end(), lowerName.begin(), ::tolower);
        
        // CRITICAL: Only select modules with jest/test/spec/story in name
        if (lowerName.find("jest") == std::string::npos &&
            lowerName.find("test") == std::string::npos &&
            lowerName.find("spec") == std::string::npos &&
            lowerName.find("story") == std::string::npos) {
            continue;
        }
        
        // Check loadedStatus at +0x188 (must be 0x00)
        uint8_t loadedStatus = 0;
        if (!ProcessScanner::ReadMemory(hProcess, child + offsets::ModuleScript_LoadedStatus, loadedStatus)) {
            continue;
        }
        if (loadedStatus != 0x00) continue;
        
        // Validate parent chain
        uintptr_t parent = 0;
        if (!ProcessScanner::ReadMemory(hProcess, child + offsets::Instance_Parent, parent) || !parent) {
            continue;
        }
        uintptr_t grandParent = 0;
        if (!ProcessScanner::ReadMemory(hProcess, parent + offsets::Instance_Parent, grandParent) || !grandParent) {
            continue;
        }
        
        // Cache this module
        m_cachedModules.push_back(child);
        
        outName = rblx::GetInstancePath(hProcess, child);
        m_moduleIndex++;
        return child;
    }
    
    return std::nullopt;
}

inline bool ScriptExecutor::InjectViaSpoof(HANDLE hProcess, const std::string& luaSource,
                                            const std::string& label, std::string& errorOut) {
    // Find a target module
    std::string moduleName;
    auto targetModule = FindUnloadedModule(hProcess, moduleName);
    if (!targetModule.has_value()) {
        errorOut = "No suitable unloaded module found";
        return false;
    }
    
    // Wrap the Lua source
    std::string wrappedSource = 
        "task.spawn(function() " + luaSource + "\nend);\n"
        "return setmetatable({}, {__index = function() return function() end end})";
    
    // Compile, sign, compress, encode
    std::vector<uint8_t> bytecode;
    if (!CompileAndSign(wrappedSource, bytecode)) {
        errorOut = "Failed to compile Lua source";
        return false;
    }
    
    // Write bytecode to module
    if (!SetBytecode(hProcess, targetModule.value(), bytecode)) {
        errorOut = "Failed to write bytecode";
        return false;
    }
    
    // Save original SpoofTarget pointer
    uintptr_t originalSpoofTarget = 0;
    uintptr_t spoofTargetAddr = m_playerListManager + offsets::PlayerListManager_SpoofTarget;
    ProcessScanner::ReadMemory(hProcess, spoofTargetAddr, originalSpoofTarget);
    
    // Write target module address into SpoofTarget
    ProcessScanner::WriteMemory(hProcess, spoofTargetAddr, targetModule.value());
    
    // Simulate ESC key to trigger require()
    SimulateEscKey();
    
    // Wait for confirmation (KidsWin folder appearing)
    if (!WaitForConfirmation(hProcess, 4000)) {
        // Restore immediately on failure
        ProcessScanner::WriteMemory(hProcess, spoofTargetAddr, originalSpoofTarget);
        errorOut = "Timeout waiting for confirmation";
        return false;
    }
    
    // Close menu with another ESC
    SimulateEscKey();
    
    // Restore SpoofTarget pointer immediately
    ProcessScanner::WriteMemory(hProcess, spoofTargetAddr, originalSpoofTarget);
    
    return true;
}

inline bool ScriptExecutor::SetBytecode(HANDLE hProcess, uintptr_t moduleScript,
                                         const std::vector<uint8_t>& rsb1Data) {
    // Read embedded pointer at moduleScript + 0x150
    uintptr_t embeddedPtr = 0;
    if (!ProcessScanner::ReadMemory(hProcess, moduleScript + offsets::ModuleScript_ModuleScriptByteCode, embeddedPtr)) {
        return false;
    }
    
    // Save originals
    ModifiedModule mod;
    mod.moduleAddress = moduleScript;
    mod.embeddedAddress = embeddedPtr;
    
    uintptr_t origBytecodePtr = 0;
    size_t origBytecodeSize = 0;
    uint32_t origCapabilities = 0;
    
    ProcessScanner::ReadMemory(hProcess, embeddedPtr + offsets::Embedded::BytecodePointer, origBytecodePtr);
    ProcessScanner::ReadMemory(hProcess, embeddedPtr + offsets::Embedded::BytecodeSize, origBytecodeSize);
    ProcessScanner::ReadMemory(hProcess, moduleScript + offsets::Instance_InstanceCapabilities, origCapabilities);
    
    mod.originalBytecodePtr = origBytecodePtr;
    mod.originalBytecodeSize = origBytecodeSize;
    mod.originalCapabilities = origCapabilities;
    
    m_modifiedModules.push_back(mod);
    
    // Allocate remote memory
    void* remoteMem = g_SyscallResolver.AllocateMemorySyscall(hProcess, rsb1Data.size());
    if (!remoteMem) {
        // Fallback to VirtualAllocEx
        remoteMem = VirtualAllocEx(hProcess, nullptr, rsb1Data.size(), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    }
    if (!remoteMem) return false;
    
    // Write RSB1 data
    if (!g_SyscallResolver.WriteMemorySyscall(hProcess, reinterpret_cast<uintptr_t>(remoteMem),
                                               rsb1Data.data(), rsb1Data.size())) {
        return false;
    }
    
    // Overwrite embedded + 0x10 (BytecodePointer)
    uintptr_t remoteAddr = reinterpret_cast<uintptr_t>(remoteMem);
    ProcessScanner::WriteMemory(hProcess, embeddedPtr + offsets::Embedded::BytecodePointer, remoteAddr);
    
    // Overwrite embedded + 0x20 (BytecodeSize)
    size_t newSize = rsb1Data.size();
    ProcessScanner::WriteMemory(hProcess, embeddedPtr + offsets::Embedded::BytecodeSize, newSize);
    
    // Overwrite InstanceCapabilities to 0x3FFFFFFF (max privileges, Identity 8)
    uint32_t maxCaps = 0x3FFFFFFF;
    ProcessScanner::WriteMemory(hProcess, moduleScript + offsets::Instance_InstanceCapabilities, maxCaps);
    
    return true;
}

inline void ScriptExecutor::SimulateEscKey() {
    // Find Roblox window
    HWND hwnd = nullptr;
    EnumWindows([](HWND hWnd, LPARAM lParam) -> BOOL {
        DWORD pid = 0;
        GetWindowThreadProcessId(hWnd, &pid);
        if (pid == *reinterpret_cast<DWORD*>(lParam)) {
            *reinterpret_cast<HWND*>(lParam + sizeof(DWORD)) = hWnd;
            return FALSE;
        }
        return TRUE;
    }, reinterpret_cast<LPARAM>(&m_pid));
    
    // Retry loop for SetForegroundWindow
    for (int i = 0; i < 5; ++i) {
        if (hwnd) {
            SetForegroundWindow(hwnd);
            Sleep(50);
            
            INPUT inputs[2] = {};
            inputs[0].type = INPUT_KEYBOARD;
            inputs[0].ki.wVk = VK_ESCAPE;
            inputs[0].ki.dwFlags = 0;
            inputs[1].type = INPUT_KEYBOARD;
            inputs[1].ki.wVk = VK_ESCAPE;
            inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
            
            SendInput(2, inputs, sizeof(INPUT));
            break;
        }
        Sleep(100);
    }
}

inline void ScriptExecutor::RestoreAllModules() {
    for (const auto& mod : m_modifiedModules) {
        if (!rblx::IsValidInstance(m_hProcess, mod.moduleAddress)) {
            continue; // DataModel already destroyed
        }
        
        // Restore BytecodePointer
        ProcessScanner::WriteMemory(m_hProcess, mod.embeddedAddress + offsets::Embedded::BytecodePointer,
                                     mod.originalBytecodePtr);
        
        // Restore BytecodeSize
        ProcessScanner::WriteMemory(m_hProcess, mod.embeddedAddress + offsets::Embedded::BytecodeSize,
                                     mod.originalBytecodeSize);
        
        // Restore InstanceCapabilities
        ProcessScanner::WriteMemory(m_hProcess, mod.moduleAddress + offsets::Instance_InstanceCapabilities,
                                     mod.originalCapabilities);
    }
    
    m_modifiedModules.clear();
}

inline bool ScriptExecutor::WaitForConfirmation(HANDLE hProcess, int timeoutMs) {
    int iterations = timeoutMs / 100;
    for (int i = 0; i < iterations; ++i) {
        auto kidsWinFolder = rblx::FindChildByName(hProcess, m_coreGui, "KidsWin");
        if (kidsWinFolder.has_value()) {
            return true;
        }
        Sleep(100);
    }
    return false;
}

inline void ScriptExecutor::QueueScript(const std::string& script) {
    std::lock_guard<std::mutex> lock(m_scriptQueueMutex);
    m_scriptQueue.push_back(script);
}

inline std::string ScriptExecutor::DequeueScript() {
    std::lock_guard<std::mutex> lock(m_scriptQueueMutex);
    if (m_scriptQueue.empty()) return "";
    std::string script = m_scriptQueue.front();
    m_scriptQueue.erase(m_scriptQueue.begin());
    return script;
}

// Placeholder implementations for compilation
inline bool ScriptExecutor::CompileAndSign(const std::string& luaSource, std::vector<uint8_t>& outBytecode) {
    // In production: Use LuauCompiler::Compile() + BLAKE3 signature
    // For now, just copy source as placeholder
    outBytecode.assign(luaSource.begin(), luaSource.end());
    return true;
}

inline bool ScriptExecutor::CompressWithZstd(const std::vector<uint8_t>& input, std::vector<uint8_t>& output) {
    // In production: Use ZSTD_compress
    output = input;
    return true;
}

inline void ScriptExecutor::StartHttpServer() {
    if (m_httpServerRunning) return;
    // In production: Initialize httplib server with /poll, /ls, /req, /cleanup endpoints
    m_httpServerRunning = true;
}

inline void ScriptExecutor::StopHttpServer() {
    if (!m_httpServerRunning) return;
    m_httpServerRunning = false;
    // In production: Stop httplib server
}
