// KidsWin External Executor - Offsets Header
// Memory offsets for Roblox Player (external execution)
// Source: https://github.com/NtReadVirtualMemory/Roblox-Offsets-Website

#pragma once
#include <cstdint>

namespace offsets {
    // Instance offsets
    constexpr size_t Instance_Children = 0x70;
    constexpr size_t Instance_Parent = 0x68;
    constexpr size_t Instance_ClassDescriptor = 0x18;
    constexpr size_t Instance_Name = 0xB0;
    constexpr size_t Instance_InstanceCapabilities = 0x208;
    
    // ModuleScript offsets
    constexpr size_t ModuleScript_ModuleScriptByteCode = 0x150;
    constexpr size_t ModuleScript_LoadedStatus = 0x188;
    
    // PlayerListManager offsets
    constexpr size_t PlayerListManager_SpoofTarget = 0x8;
    
    // ClassDescriptor offsets
    constexpr size_t ClassDescriptor_Name = 0x8;
    
    // Pointer globals (base-relative)
    namespace Pointer {
        constexpr size_t TaskScheduler = 0x4E8A000;      // Updated per version
        constexpr size_t FakeDataModelPointer = 0x4E8B000; // Updated per version
    }
    
    // TaskScheduler offsets
    namespace TaskScheduler {
        constexpr size_t JobStart = 0x1D0;
        constexpr size_t JobEnd = 0x1D8;
    }
    
    // Embedded bytecode pointer offsets
    namespace Embedded {
        constexpr size_t BytecodePointer = 0x10;
        constexpr size_t BytecodeSize = 0x20;
    }
}
