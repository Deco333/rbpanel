// KidsWin - Instance Walker Helpers
// Navigate Roblox instance tree externally

#pragma once
#include <windows.h>
#include <vector>
#include <string>
#include <optional>
#include "../include/offsets.h"

namespace rblx {

// Read a pointer from memory
inline uintptr_t ReadPointer(HANDLE hProcess, uintptr_t addr) {
    uintptr_t ptr = 0;
    ReadProcessMemory(hProcess, (LPCVOID)addr, &ptr, sizeof(ptr), nullptr);
    return ptr;
}

// Read an std::string (MSVC SSO-aware)
inline std::string ReadString(HANDLE hProcess, uintptr_t addr) {
    if (!addr) return "";
    
    // Read first 24 bytes to get string structure
    char buffer[24] = { 0 };
    if (!ReadProcessMemory(hProcess, (LPCVOID)addr, buffer, sizeof(buffer), nullptr)) {
        return "";
    }
    
    // MSVC std::string layout:
    // [0-7]: pointer to heap OR inline data (if capacity <= 15)
    // [8-15]: unused in SSO mode
    // [16-19]: size
    // [20-23]: capacity
    
    uint32_t size = *reinterpret_cast<uint32_t*>(buffer + 16);
    uint32_t capacity = *reinterpret_cast<uint32_t*>(buffer + 20);
    
    std::string result;
    result.resize(size);
    
    if (capacity <= 15) {
        // Short String Optimization - data is inline
        memcpy(&result[0], buffer, size);
    } else {
        // Heap-allocated string
        uintptr_t heapPtr = *reinterpret_cast<uintptr_t*>(buffer);
        ReadProcessMemory(hProcess, (LPCVOID)heapPtr, &result[0], size, nullptr);
    }
    
    return result;
}

// Check if an address is a valid instance
inline bool IsValidInstance(HANDLE hProcess, uintptr_t addr) {
    if (!addr || addr < 0x10000) return false;
    
    // Try to read ClassDescriptor at +0x18
    uintptr_t classDesc = ReadPointer(hProcess, addr + offsets::Instance_ClassDescriptor);
    if (!classDesc || classDesc < 0x10000) return false;
    
    // Validate class descriptor by reading its name pointer
    uintptr_t namePtr = ReadPointer(hProcess, classDesc + offsets::ClassDescriptor_Name);
    if (!namePtr || namePtr < 0x10000) return false;
    
    return true;
}

// Get children of an instance
inline std::vector<uintptr_t> GetChildren(HANDLE hProcess, uintptr_t instance) {
    std::vector<uintptr_t> children;
    
    if (!instance) return children;
    
    // Read children vector start and end pointers
    uintptr_t childrenStart = ReadPointer(hProcess, instance + offsets::Instance_Children);
    uintptr_t childrenEnd = ReadPointer(hProcess, instance + offsets::Instance_Children + 0x8);
    
    if (!childrenStart || !childrenEnd) return children;
    
    // Iterate through child pointers
    for (uintptr_t ptr = childrenStart; ptr < childrenEnd; ptr += 0x8) {
        uintptr_t child = ReadPointer(hProcess, ptr);
        if (child && IsValidInstance(hProcess, child)) {
            children.push_back(child);
        }
    }
    
    return children;
}

// Read class name from instance
inline std::string ReadClassName(HANDLE hProcess, uintptr_t instance) {
    if (!instance) return "";
    
    uintptr_t classDesc = ReadPointer(hProcess, instance + offsets::Instance_ClassDescriptor);
    if (!classDesc) return "";
    
    uintptr_t namePtr = ReadPointer(hProcess, classDesc + offsets::ClassDescriptor_Name);
    if (!namePtr) return "";
    
    return ReadString(hProcess, namePtr);
}

// Read instance name
inline std::string ReadInstanceName(HANDLE hProcess, uintptr_t instance) {
    if (!instance) return "";
    return ReadString(hProcess, instance + offsets::Instance_Name);
}

// Find child by name
inline std::optional<uintptr_t> FindChildByName(HANDLE hProcess, uintptr_t parent, const std::string& name) {
    auto children = GetChildren(hProcess, parent);
    for (uintptr_t child : children) {
        if (ReadInstanceName(hProcess, child) == name) {
            return child;
        }
    }
    return std::nullopt;
}

// Find child by class name
inline std::optional<uintptr_t> FindChildByClassName(HANDLE hProcess, uintptr_t parent, const std::string& className) {
    auto children = GetChildren(hProcess, parent);
    for (uintptr_t child : children) {
        if (ReadClassName(hProcess, child) == className) {
            return child;
        }
    }
    return std::nullopt;
}

// Build full instance path (e.g., "CoreGui.RobloxGui.Modules")
inline std::string GetInstancePath(HANDLE hProcess, uintptr_t instance) {
    std::vector<std::string> parts;
    uintptr_t current = instance;
    
    while (current && IsValidInstance(hProcess, current)) {
        std::string name = ReadInstanceName(hProcess, current);
        if (name.empty()) {
            name = ReadClassName(hProcess, current);
        }
        parts.insert(parts.begin(), name);
        
        current = ReadPointer(hProcess, current + offsets::Instance_Parent);
    }
    
    std::string path;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) path += ".";
        path += parts[i];
    }
    return path;
}

} // namespace rblx
