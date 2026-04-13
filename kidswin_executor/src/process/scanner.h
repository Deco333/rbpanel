// KidsWin - Process Scanner
// Find and interact with Roblox process

#pragma once
#include <windows.h>
#include <tlhelp32.h>
#include <string>
#include <vector>
#include <optional>
#include <algorithm>

struct RobloxProcess {
    DWORD pid;
    uintptr_t baseAddress;
    HANDLE hProcess;
};

namespace ProcessScanner {

// Find all Roblox processes
inline std::vector<DWORD> FindRobloxProcesses() {
    std::vector<DWORD> pids;
    
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) return pids;
    
    PROCESSENTRY32W pe32 = { sizeof(PROCESSENTRY32W) };
    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            std::wstring name(pe32.szExeFile);
            // Check for both standard and Microsoft Store versions
            if (name == L"RobloxPlayerBeta.exe" || 
                name == L"Windows10Universal.exe" ||
                name.find(L"Roblox") != std::wstring::npos) {
                pids.push_back(pe32.th32ProcessID);
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }
    
    CloseHandle(hSnapshot);
    return pids;
}

// Get best Roblox process (the one with most TaskScheduler jobs = actual game client)
inline std::optional<DWORD> FindBestRobloxProcess() {
    auto pids = FindRobloxProcesses();
    if (pids.empty()) return std::nullopt;
    
    if (pids.size() == 1) return pids[0];
    
    // For multiple processes, return the first one
    // In production, you'd scan TaskScheduler jobs to find the real game client
    return pids[0];
}

// Get process base address
inline uintptr_t GetProcessBaseAddress(DWORD pid) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (hSnapshot == INVALID_HANDLE_VALUE) return 0;
    
    MODULEENTRY32W me32 = { sizeof(MODULEENTRY32W) };
    if (Module32FirstW(hSnapshot, &me32)) {
        CloseHandle(hSnapshot);
        return reinterpret_cast<uintptr_t>(me32.modBaseAddr);
    }
    
    CloseHandle(hSnapshot);
    return 0;
}

// Open process and get base address
inline std::optional<RobloxProcess> Connect(DWORD pid) {
    HANDLE hProcess = OpenProcess(
        PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
        FALSE,
        pid
    );
    
    if (!hProcess) return std::nullopt;
    
    uintptr_t base = GetProcessBaseAddress(pid);
    if (!base) {
        CloseHandle(hProcess);
        return std::nullopt;
    }
    
    return RobloxProcess{ pid, base, hProcess };
}

// Read memory from process
template<typename T>
inline bool ReadMemory(HANDLE hProcess, uintptr_t addr, T& out) {
    SIZE_T bytesRead = 0;
    BOOL result = ReadProcessMemory(hProcess, (LPCVOID)addr, &out, sizeof(T), &bytesRead);
    return result && bytesRead == sizeof(T);
}

// Write memory to process
template<typename T>
inline bool WriteMemory(HANDLE hProcess, uintptr_t addr, const T& value) {
    SIZE_T bytesWritten = 0;
    return WriteProcessMemory(hProcess, (LPVOID)addr, &value, sizeof(T), &bytesWritten);
}

// Read bytes
inline bool ReadBytes(HANDLE hProcess, uintptr_t addr, void* buffer, size_t size) {
    SIZE_T bytesRead = 0;
    return ReadProcessMemory(hProcess, (LPCVOID)addr, buffer, size, &bytesRead) && bytesRead == size;
}

// Write bytes
inline bool WriteBytes(HANDLE hProcess, uintptr_t addr, const void* buffer, size_t size) {
    SIZE_T bytesWritten = 0;
    return WriteProcessMemory(hProcess, (LPVOID)addr, buffer, size, &bytesWritten);
}

// Read pointer chain
inline uintptr_t ReadPointerChain(HANDLE hProcess, uintptr_t base, const std::vector<size_t>& offsets) {
    uintptr_t ptr = base;
    for (size_t i = 0; i < offsets.size() - 1; ++i) {
        ptr = ptr + offsets[i];
        if (!ReadMemory(hProcess, ptr, ptr)) return 0;
    }
    return ptr + offsets.back();
}

// Read value at pointer chain
template<typename T>
inline bool ReadAtPointerChain(HANDLE hProcess, uintptr_t base, const std::vector<size_t>& offsets, T& out) {
    uintptr_t addr = ReadPointerChain(hProcess, base, offsets);
    if (!addr) return false;
    return ReadMemory(hProcess, addr, out);
}

} // namespace ProcessScanner
