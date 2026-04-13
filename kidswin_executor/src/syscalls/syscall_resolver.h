// KidsWin - Syscall Resolver (for stealth)
// Resolve Nt* syscalls for direct syscall execution

#pragma once
#include <windows.h>
#include <winternl.h>
#include <cstdint>

// NTSTATUS codes
#define STATUS_SUCCESS 0x00000000
#define STATUS_INFO_LENGTH_MISMATCH 0xC0000004

// Process access flags
#define PROCESS_VM_READ 0x0010
#define PROCESS_VM_WRITE 0x0020
#define PROCESS_VM_OPERATION 0x0008
#define PROCESS_QUERY_INFORMATION 0x0400

// Memory protection constants
#define PAGE_READWRITE 0x04
#define PAGE_EXECUTE_READWRITE 0x40
#define MEM_COMMIT 0x1000
#define MEM_RESERVE 0x2000
#define MEM_RELEASE 0x8000

typedef NTSTATUS(NTAPI* pfnNtOpenProcess)(
    PHANDLE ProcessHandle,
    ACCESS_MASK DesiredAccess,
    POBJECT_ATTRIBUTES ObjectAttributes,
    PCLIENT_ID ClientId
);

typedef NTSTATUS(NTAPI* pfnNtReadVirtualMemory)(
    HANDLE ProcessHandle,
    PVOID BaseAddress,
    PVOID Buffer,
    SIZE_T NumberOfBytesToRead,
    PSIZE_T NumberOfBytesReaded
);

typedef NTSTATUS(NTAPI* pfnNtWriteVirtualMemory)(
    HANDLE ProcessHandle,
    PVOID BaseAddress,
    PVOID Buffer,
    SIZE_T NumberOfBytesToWrite,
    PSIZE_T NumberOfBytesWritten
);

typedef NTSTATUS(NTAPI* pfnNtAllocateVirtualMemory)(
    HANDLE ProcessHandle,
    PVOID* BaseAddress,
    ULONG_PTR ZeroBits,
    PSIZE_T RegionSize,
    ULONG AllocationType,
    ULONG Protect
);

typedef NTSTATUS(NTAPI* pfnNtFreeVirtualMemory)(
    HANDLE ProcessHandle,
    PVOID* BaseAddress,
    PSIZE_T RegionSize,
    ULONG FreeType
);

typedef NTSTATUS(NTAPI* pfnNtClose)(
    HANDLE Handle
);

typedef NTSTATUS(NTAPI* pfnNtQueryInformationProcess)(
    HANDLE ProcessHandle,
    ULONG ProcessInformationClass,
    PVOID ProcessInformation,
    ULONG ProcessInformationLength,
    PULONG ReturnLength
);

class SyscallResolver {
private:
    HMODULE hNtdll = nullptr;
    pfnNtOpenProcess NtOpenProcess = nullptr;
    pfnNtReadVirtualMemory NtReadVirtualMemory = nullptr;
    pfnNtWriteVirtualMemory NtWriteVirtualMemory = nullptr;
    pfnNtAllocateVirtualMemory NtAllocateVirtualMemory = nullptr;
    pfnNtFreeVirtualMemory NtFreeVirtualMemory = nullptr;
    pfnNtClose NtClose = nullptr;
    pfnNtQueryInformationProcess NtQueryInformationProcess = nullptr;

public:
    bool Initialize() {
        hNtdll = GetModuleHandleA("ntdll.dll");
        if (!hNtdll) return false;

        NtOpenProcess = (pfnNtOpenProcess)GetProcAddress(hNtdll, "NtOpenProcess");
        NtReadVirtualMemory = (pfnNtReadVirtualMemory)GetProcAddress(hNtdll, "NtReadVirtualMemory");
        NtWriteVirtualMemory = (pfnNtWriteVirtualMemory)GetProcAddress(hNtdll, "NtWriteVirtualMemory");
        NtAllocateVirtualMemory = (pfnNtAllocateVirtualMemory)GetProcAddress(hNtdll, "NtAllocateVirtualMemory");
        NtFreeVirtualMemory = (pfnNtFreeVirtualMemory)GetProcAddress(hNtdll, "NtFreeVirtualMemory");
        NtClose = (pfnNtClose)GetProcAddress(hNtdll, "NtClose");
        NtQueryInformationProcess = (pfnNtQueryInformationProcess)GetProcAddress(hNtdll, "NtQueryInformationProcess");

        return NtOpenProcess && NtReadVirtualMemory && NtWriteVirtualMemory &&
               NtAllocateVirtualMemory && NtFreeVirtualMemory && NtClose;
    }

    // Open process using syscall
    HANDLE OpenProcessSyscall(DWORD pid) {
        if (!NtOpenProcess) return nullptr;

        HANDLE hProcess = nullptr;
        OBJECT_ATTRIBUTES oa = { sizeof(OBJECT_ATTRIBUTES) };
        CLIENT_ID cid = { nullptr };
        cid.UniqueProcess = reinterpret_cast<HANDLE>(static_cast<uintptr_t>(pid));

        NTSTATUS status = NtOpenProcess(&hProcess, 
            PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
            &oa, &cid);

        if (status != STATUS_SUCCESS) {
            return nullptr;
        }

        return hProcess;
    }

    // Read memory using syscall
    bool ReadMemorySyscall(HANDLE hProcess, uintptr_t addr, void* buffer, size_t size) {
        if (!NtReadVirtualMemory) return false;

        SIZE_T bytesRead = 0;
        NTSTATUS status = NtReadVirtualMemory(hProcess, 
            reinterpret_cast<PVOID>(addr), 
            buffer, 
            size, 
            &bytesRead);

        return status == STATUS_SUCCESS && bytesRead == size;
    }

    // Write memory using syscall
    bool WriteMemorySyscall(HANDLE hProcess, uintptr_t addr, const void* buffer, size_t size) {
        if (!NtWriteVirtualMemory) return false;

        SIZE_T bytesWritten = 0;
        NTSTATUS status = NtWriteVirtualMemory(hProcess,
            reinterpret_cast<PVOID>(addr),
            const_cast<void*>(buffer),
            size,
            &bytesWritten);

        return status == STATUS_SUCCESS && bytesWritten == size;
    }

    // Allocate memory using syscall
    void* AllocateMemorySyscall(HANDLE hProcess, size_t size) {
        if (!NtAllocateVirtualMemory) return nullptr;

        PVOID baseAddress = nullptr;
        SIZE_T regionSize = size;
        NTSTATUS status = NtAllocateVirtualMemory(
            hProcess,
            &baseAddress,
            0,
            &regionSize,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE
        );

        return status == STATUS_SUCCESS ? baseAddress : nullptr;
    }

    // Free memory using syscall
    bool FreeMemorySyscall(HANDLE hProcess, void* address) {
        if (!NtFreeVirtualMemory) return false;

        PVOID baseAddress = address;
        SIZE_T regionSize = 0;
        NTSTATUS status = NtFreeVirtualMemory(
            hProcess,
            &baseAddress,
            &regionSize,
            MEM_RELEASE
        );

        return status == STATUS_SUCCESS;
    }

    // Close handle using syscall
    bool CloseHandleSyscall(HANDLE handle) {
        if (!NtClose) return false;
        return NtClose(handle) == STATUS_SUCCESS;
    }

    // Function pointers for direct use
    pfnNtOpenProcess GetNtOpenProcess() const { return NtOpenProcess; }
    pfnNtReadVirtualMemory GetNtReadVirtualMemory() const { return NtReadVirtualMemory; }
    pfnNtWriteVirtualMemory GetNtWriteVirtualMemory() const { return NtWriteVirtualMemory; }
    pfnNtAllocateVirtualMemory GetNtAllocateVirtualMemory() const { return NtAllocateVirtualMemory; }
    pfnNtFreeVirtualMemory GetNtFreeVirtualMemory() const { return NtFreeVirtualMemory; }
    pfnNtClose GetNtClose() const { return NtClose; }
};

// Global syscall resolver instance
inline SyscallResolver g_SyscallResolver;

inline bool InitializeSyscalls() {
    return g_SyscallResolver.Initialize();
}
