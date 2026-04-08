#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  HOOK MANAGER — Memory-level hook management for Roblox processes           ║
║                                                                            ║
║  Provides classes and utilities for installing, managing, and removing      ║
║  inline function hooks inside a target Roblox process via ctypes            ║
║  (VirtualProtect, ReadProcessMemory, WriteProcessMemory).                   ║
║                                                                            ║
║  Features:                                                                 ║
║    - MemoryHook: single inline JMP hook with backup/restore                ║
║    - HookManager: centralized registry of all active hooks                 ║
║    - 40 predefined hook presets across 6 categories                        ║
║    - FFlag manager with remote JSON fetching                               ║
║    - Basic x86/x64 shellcode assembler                                     ║
║                                                                            ║
║  Usage:                                                                    ║
║    from hook_manager import HookManager, HOOK_PRESETS, FFlagManager        ║
║    mgr = HookManager(process_handle, base_address)                         ║
║    mgr.install_hook("NoClip", "jmp", {"offset_key": "NoclipFunc"})         ║
║    mgr.uninstall_all()                                                     ║
║                                                                            ║
║  Platform: Windows-only (uses kernel32 via ctypes)                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import struct
import threading
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("hook_manager")

# ═══════════════════════════════════════════════════════════════════════════
#  WINDOWS API — kernel32 bindings via ctypes
# ═══════════════════════════════════════════════════════════════════════════

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- VirtualProtect ---
kernel32.VirtualProtect.argtypes = [
    wintypes.LPVOID,          # lpAddress
    ctypes.c_size_t,          # dwSize
    wintypes.DWORD,           # flNewProtect
    ctypes.POINTER(wintypes.DWORD),  # lpflOldProtect
]
kernel32.VirtualProtect.restype = wintypes.BOOL

# --- ReadProcessMemory ---
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,          # hProcess
    wintypes.LPCVOID,         # lpBaseAddress
    wintypes.LPVOID,          # lpBuffer
    ctypes.c_size_t,          # nSize
    ctypes.POINTER(ctypes.c_size_t),  # lpNumberOfBytesRead
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

# --- WriteProcessMemory ---
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,          # hProcess
    wintypes.LPVOID,          # lpBaseAddress
    wintypes.LPCVOID,         # lpBuffer
    ctypes.c_size_t,          # nSize
    ctypes.POINTER(ctypes.c_size_t),  # lpNumberOfBytesWritten
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

# --- FlushInstructionCache ---
kernel32.FlushInstructionCache.argtypes = [
    wintypes.HANDLE,          # hProcess
    wintypes.LPCVOID,         # lpBaseAddress
    ctypes.c_size_t,          # dwSize
]
kernel32.FlushInstructionCache.restype = wintypes.BOOL

# --- Memory protection constants ---
PAGE_NOACCESS          = 0x01
PAGE_READONLY          = 0x02
PAGE_READWRITE         = 0x04
PAGE_WRITECOPY         = 0x08
PAGE_EXECUTE           = 0x10
PAGE_EXECUTE_READ      = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80

# --- x86/x64 instruction constants ---
OP_NOP  = 0x90
OP_RET  = 0xC3
OP_INT3 = 0xCC
OP_JMP_REL32 = 0xE9  # 5-byte relative JMP (x86)
OP_JMP_ABS64 = b"\xFF\x25\x00\x00\x00\x00"  # 6-byte absolute JMP (x64)


# ═══════════════════════════════════════════════════════════════════════════
#  EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════

class HookError(Exception):
    """Base exception for hook-related errors."""
    pass


class HookAlreadyInstalledError(HookError):
    """Raised when trying to install a hook that is already active."""
    pass


class HookNotInstalledError(HookError):
    """Raised when trying to uninstall a hook that is not active."""
    pass


class HookPresetNotFoundError(HookError):
    """Raised when a requested hook preset name does not exist."""
    pass


class MemoryAccessError(HookError):
    """Raised when a Windows API memory operation fails."""
    pass


class AssemblerError(HookError):
    """Raised when the shellcode assembler encounters an invalid instruction."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
#  LOW-LEVEL MEMORY HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _read_process_memory(handle: int, address: int, size: int) -> bytes:
    """
    Read bytes from a process's memory via ReadProcessMemory.

    Args:
        handle: Open process handle (PROCESS_VM_READ).
        address: Target memory address to read from.
        size: Number of bytes to read.

    Returns:
        Bytes read from the target address.

    Raises:
        MemoryAccessError: If ReadProcessMemory fails.
    """
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    success = kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(address),
        buffer,
        size,
        ctypes.byref(bytes_read),
    )
    if not success or bytes_read.value != size:
        err = ctypes.get_last_error()
        raise MemoryAccessError(
            f"ReadProcessMemory failed at 0x{address:X} "
            f"(size={size}, bytes_read={bytes_read.value}, error={err})"
        )
    return buffer.raw[: size]


def _write_process_memory(handle: int, address: int, data: bytes) -> int:
    """
    Write bytes into a process's memory via WriteProcessMemory.

    Args:
        handle: Open process handle (PROCESS_VM_WRITE | PROCESS_VM_OPERATION).
        address: Target memory address to write to.
        data: Bytes to write.

    Returns:
        Number of bytes actually written.

    Raises:
        MemoryAccessError: If WriteProcessMemory fails.
    """
    size = len(data)
    bytes_written = ctypes.c_size_t(0)
    success = kernel32.WriteProcessMemory(
        handle,
        ctypes.c_void_p(address),
        data,
        size,
        ctypes.byref(bytes_written),
    )
    if not success or bytes_written.value != size:
        err = ctypes.get_last_error()
        raise MemoryAccessError(
            f"WriteProcessMemory failed at 0x{address:X} "
            f"(size={size}, bytes_written={bytes_written.value}, error={err})"
        )
    return bytes_written.value


def _virtual_protect(handle: int, address: int, size: int,
                     new_protect: int) -> int:
    """
    Change memory protection via VirtualProtect.

    Args:
        handle: Process handle (typically not required for VirtualProtect
                on the current process, but included for remote usage).
        address: Base address of the memory region.
        size: Size of the region in bytes.
        new_protect: New memory protection constant (e.g. PAGE_EXECUTE_READWRITE).

    Returns:
        The previous memory protection value.

    Raises:
        MemoryAccessError: If VirtualProtect fails.
    """
    old_protect = wintypes.DWORD(0)
    success = kernel32.VirtualProtect(
        ctypes.c_void_p(address),
        size,
        new_protect,
        ctypes.byref(old_protect),
    )
    if not success:
        err = ctypes.get_last_error()
        raise MemoryAccessError(
            f"VirtualProtect failed at 0x{address:X} "
            f"(size={size}, new_protect=0x{new_protect:X}, error={err})"
        )
    return old_protect.value


def _flush_instruction_cache(handle: int, address: int, size: int) -> bool:
    """
    Flush the instruction cache for a memory region.

    After writing code to a process, the CPU instruction cache may hold stale
    bytes. This ensures the CPU fetches the newly written instructions.

    Args:
        handle: Process handle.
        address: Base address of modified code.
        size: Size of the modified region.

    Returns:
        True on success, False on failure.
    """
    return bool(kernel32.FlushInstructionCache(
        handle, ctypes.c_void_p(address), size
    ))


def _build_jmp_x86(from_addr: int, to_addr: int) -> bytes:
    """
    Build a 5-byte x86 relative JMP instruction.

    JMP rel32:  0xE9 <signed 32-bit displacement>
    Displacement is calculated from the end of the JMP instruction.

    Args:
        from_addr: Address where the JMP will be written.
        to_addr: Target address the JMP should reach.

    Returns:
        5-byte JMP instruction.
    """
    # Displacement is relative to the instruction after the JMP (from_addr + 5)
    rel = to_addr - (from_addr + 5)
    rel_signed = ctypes.c_int32(rel).value  # clamp to signed 32-bit
    return struct.pack("<Bi", OP_JMP_REL32, rel_signed)


def _build_jmp_x64(from_addr: int, to_addr: int) -> bytes:
    """
    Build a 14-byte x64 absolute JMP instruction.

    Uses the FF 25 00 00 00 00 trampoline pattern:
        JMP [RIP+0]   ; 6 bytes
        <8-byte target address>  ; immediately follows

    Args:
        from_addr: Address where the JMP will be written.
        to_addr: Target 64-bit address.

    Returns:
        14-byte absolute JMP instruction.
    """
    return OP_JMP_ABS64 + struct.pack("<Q", to_addr)


def _build_nop_sled(count: int) -> bytes:
    """Build a NOP sled of the given byte count."""
    return bytes([OP_NOP] * count)


def _is_64bit_process(handle: int) -> bool:
    """
    Determine if the target process is 64-bit.

    Falls back to checking the current Python interpreter architecture
    if the process architecture cannot be determined via IsWow64Process.

    Args:
        handle: Process handle.

    Returns:
        True if 64-bit, False if 32-bit.
    """
    try:
        is_wow64 = wintypes.BOOL(False)
        kernel32.IsWow64Process.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        kernel32.IsWow64Process.restype = wintypes.BOOL
        kernel32.IsWow64Process(handle, ctypes.byref(is_wow64))
        # If IsWow64Process returns True on a 64-bit OS,
        # the process is running under WOW64 → it's 32-bit
        return not bool(is_wow64.value)
    except Exception:
        # Fallback: check Python pointer size
        return ctypes.sizeof(ctypes.c_void_p) == 8


# ═══════════════════════════════════════════════════════════════════════════
#  SHELLCODE ASSEMBLER
# ═══════════════════════════════════════════════════════════════════════════

# x86 register encodings for MOV reg32, imm32
_X86_REGISTERS: Dict[str, int] = {
    "eax": 0, "ecx": 1, "edx": 2, "ebx": 3,
    "esp": 4, "ebp": 5, "esi": 6, "edi": 7,
}

# Map of assembler mnemonics to their handler functions
_ASSEMBLER_PATTERNS: Dict[str, Any] = {}


def _asm_nop(tokens: List[str], _line_num: int) -> bytes:
    """Assemble a NOP instruction. Optionally specify repeat count: NOP 5."""
    count = 1
    if len(tokens) > 1:
        try:
            count = max(1, min(256, int(tokens[1])))
        except ValueError:
            raise AssemblerError(f"Invalid NOP count: {tokens[1]}")
    return _build_nop_sled(count)


def _asm_ret(tokens: List[str], _line_num: int) -> bytes:
    """Assemble a RET (return) instruction."""
    return bytes([OP_RET])


def _asm_int3(tokens: List[str], _line_num: int) -> bytes:
    """Assemble an INT 3 (software breakpoint) instruction."""
    return bytes([OP_INT3])


def _asm_jmp_rel32(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble JMP rel32.

    Usage: JMP <address_or_label>
    The address is treated as an absolute target; a placeholder rel32
    is emitted. The caller is responsible for resolving labels.

    Falls back to building a full x86 JMP with relative displacement
    if a from-address hint is given via a comment:  JMP 0x12345 ; from=0x10000
    """
    if len(tokens) < 2:
        raise AssemblerError(f"Line {line_num}: JMP requires a target address")
    target_str = tokens[1].strip()
    try:
        target = int(target_str, 0)
    except ValueError:
        raise AssemblerError(
            f"Line {line_num}: Invalid JMP target: {target_str}"
        )
    # Emit E9 + 4 zero bytes (placeholder; caller patches displacement)
    return struct.pack("<Bi", OP_JMP_REL32, 0)


def _asm_mov_reg_imm32(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble MOV reg32, imm32.

    Usage: MOV <reg>, <value>
    Encoding: B8+rd <imm32>
    Example: MOV EAX, 0x12345678 → B8 78 56 34 12
    """
    if len(tokens) < 4 or tokens[2].strip() != ",":
        raise AssemblerError(
            f"Line {line_num}: MOV syntax: MOV <reg>, <imm32>"
        )
    reg_name = tokens[1].strip().lower()
    imm_str = tokens[3].strip()

    if reg_name not in _X86_REGISTERS:
        raise AssemblerError(
            f"Line {line_num}: Unknown register '{reg_name}'. "
            f"Valid: {', '.join(_X86_REGISTERS.keys())}"
        )

    try:
        imm = int(imm_str, 0) & 0xFFFFFFFF
    except ValueError:
        raise AssemblerError(
            f"Line {line_num}: Invalid immediate value: {imm_str}"
        )

    reg_code = _X86_REGISTERS[reg_name]
    opcode = 0xB8 + reg_code
    return struct.pack("<BI", opcode, imm)


def _asm_mov_reg_imm16(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble MOV reg16, imm16.

    Usage: MOV <reg>16, <value>
    Encoding: 66 B8+rd <imm16>
    Example: MOV AX, 0x1234 → 66 B8 34 12
    """
    if len(tokens) < 4 or tokens[2].strip() != ",":
        raise AssemblerError(
            f"Line {line_num}: MOV16 syntax: MOV <reg16>, <imm16>"
        )
    reg_name = tokens[1].strip().lower().rstrip("16")
    imm_str = tokens[3].strip()

    if reg_name not in _X86_REGISTERS:
        raise AssemblerError(
            f"Line {line_num}: Unknown register '{reg_name}'. "
            f"Valid: {', '.join(_X86_REGISTERS.keys())}"
        )

    try:
        imm = int(imm_str, 0) & 0xFFFF
    except ValueError:
        raise AssemblerError(
            f"Line {line_num}: Invalid immediate value: {imm_str}"
        )

    reg_code = _X86_REGISTERS[reg_name]
    return struct.pack("<BBH", 0x66, 0xB8 + reg_code, imm)


def _asm_mov_reg_imm8(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble MOV reg8, imm8.

    Usage: MOV <reg8>, <value>
    Encoding: B0+rd <imm8>
    Example: MOV AL, 0x42 → B0 42
    """
    if len(tokens) < 4 or tokens[2].strip() != ",":
        raise AssemblerError(
            f"Line {line_num}: MOV8 syntax: MOV <reg8>, <imm8>"
        )
    reg_name = tokens[1].strip().lower().rstrip("8l")

    _X86_REG8 = {"al": 0, "cl": 1, "dl": 2, "bl": 3,
                 "ah": 4, "ch": 5, "dh": 6, "bh": 7}

    if reg_name not in _X86_REG8:
        raise AssemblerError(
            f"Line {line_num}: Unknown 8-bit register '{reg_name}'. "
            f"Valid: {', '.join(_X86_REG8.keys())}"
        )

    try:
        imm = int(tokens[3].strip(), 0) & 0xFF
    except ValueError:
        raise AssemblerError(
            f"Line {line_num}: Invalid immediate value: {tokens[3]}"
        )

    return struct.pack("<BB", 0xB0 + _X86_REG8[reg_name], imm)


def _asm_push(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble PUSH reg32 or PUSH imm8/imm32.

    Usage: PUSH <reg|value>
    Encoding: 50+rd for register, 68 <imm32> for immediate, 6A <imm8> for small imm.
    """
    if len(tokens) < 2:
        raise AssemblerError(f"Line {line_num}: PUSH requires an operand")

    operand = tokens[1].strip()

    # Register push
    if operand.lower() in _X86_REGISTERS:
        reg_code = _X86_REGISTERS[operand.lower()]
        return bytes([0x50 + reg_code])

    # Immediate push
    try:
        val = int(operand, 0)
        if -128 <= val <= 127:
            return struct.pack("<Bb", 0x6A, val & 0xFF)
        else:
            return struct.pack("<BI", 0x68, val & 0xFFFFFFFF)
    except ValueError:
        raise AssemblerError(f"Line {line_num}: Invalid PUSH operand: {operand}")


def _asm_pop(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble POP reg32.

    Usage: POP <reg>
    Encoding: 58+rd
    """
    if len(tokens) < 2:
        raise AssemblerError(f"Line {line_num}: POP requires an operand")

    operand = tokens[1].strip().lower()
    if operand not in _X86_REGISTERS:
        raise AssemblerError(
            f"Line {line_num}: Unknown register '{operand}' for POP"
        )
    return bytes([0x58 + _X86_REGISTERS[operand]])


def _asm_xor(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble XOR reg32, reg32.

    Usage: XOR <reg>, <reg>
    Encoding: 31 /r  (ModR/M: 11 src dst)
    """
    if len(tokens) < 4 or tokens[2].strip() != ",":
        raise AssemblerError(f"Line {line_num}: XOR syntax: XOR <reg>, <reg>")

    dst = tokens[1].strip().lower()
    src = tokens[3].strip().lower()

    if dst not in _X86_REGISTERS or src not in _X86_REGISTERS:
        raise AssemblerError(
            f"Line {line_num}: Invalid registers for XOR: {dst}, {src}"
        )

    modrm = 0xC0 | (_X86_REGISTERS[src] << 3) | _X86_REGISTERS[dst]
    return bytes([0x31, modrm])


def _asm_inc(tokens: List[str], line_num: int) -> bytes:
    """Assemble INC reg32 (40+rd)."""
    if len(tokens) < 2:
        raise AssemblerError(f"Line {line_num}: INC requires an operand")
    reg = tokens[1].strip().lower()
    if reg not in _X86_REGISTERS:
        raise AssemblerError(f"Line {line_num}: Unknown register: {reg}")
    return bytes([0x40 + _X86_REGISTERS[reg]])


def _asm_dec(tokens: List[str], line_num: int) -> bytes:
    """Assemble DEC reg32 (48+rd)."""
    if len(tokens) < 2:
        raise AssemblerError(f"Line {line_num}: DEC requires an operand")
    reg = tokens[1].strip().lower()
    if reg not in _X86_REGISTERS:
        raise AssemblerError(f"Line {line_num}: Unknown register: {reg}")
    return bytes([0x48 + _X86_REGISTERS[reg]])


def _asm_mov_dword_ptr(tokens: List[str], line_num: int) -> bytes:
    """
    Assemble MOV DWORD PTR [addr], imm32.

    Usage: MOV DWORD PTR [0x12345678], 0xDEADBEEF
    Encoding: C7 05 <addr32> <imm32>
    """
    if len(tokens) < 8:
        raise AssemblerError(
            f"Line {line_num}: Syntax: MOV DWORD PTR [<addr>], <imm32>"
        )

    addr_str = tokens[3].strip().rstrip("]").lstrip("[")
    try:
        addr = int(addr_str, 0) & 0xFFFFFFFF
    except ValueError:
        raise AssemblerError(f"Line {line_num}: Invalid address: {addr_str}")

    imm_str = tokens[5].strip() if len(tokens) > 5 else tokens[-1].strip()
    try:
        imm = int(imm_str, 0) & 0xFFFFFFFF
    except ValueError:
        raise AssemblerError(f"Line {line_num}: Invalid immediate: {imm_str}")

    return struct.pack("<BBIi", 0xC7, 0x05, addr, imm)


# Register assembler dispatch table
_ASSEMBLER_DISPATCH = {
    "nop": _asm_nop,
    "ret": _asm_ret,
    "int3": _asm_int3,
    "jmp": _asm_jmp_rel32,
    "push": _asm_push,
    "pop": _asm_pop,
    "xor": _asm_xor,
    "inc": _asm_inc,
    "dec": _asm_dec,
}


def assemble(assembly_text: str) -> bytes:
    """
    Basic x86/x64 shellcode assembler.

    Takes a multiline string of assembly instructions and returns the
    assembled machine code bytes. Supports a subset of common x86
    instructions sufficient for writing hook trampolines and patches.

    Supported instructions:
        NOP [count]               - No-operation sled
        RET                       - Return (0xC3)
        INT3                      - Software breakpoint (0xCC)
        JMP <address>             - Relative JMP (placeholder displacement)
        MOV <reg32>, <imm32>      - Load 32-bit immediate into register
        MOV <reg16>, <imm16>      - Load 16-bit immediate into register
        MOV <reg8>, <imm8>        - Load 8-bit immediate into register
        MOV DWORD PTR [<addr>], <imm32> - Write immediate to memory
        PUSH <reg32|imm>          - Push register or immediate
        POP <reg32>               - Pop into register
        XOR <reg>, <reg>          - XOR two registers
        INC <reg>                 - Increment register
        DEC <reg>                 - Decrement register

    Lines starting with ';' or '#' are treated as comments and ignored.
    Empty lines are skipped. Labels (ending with ':') are noted but not
    resolved (the caller must patch jump targets manually).

    Args:
        assembly_text: Multiline string of assembly instructions.

    Returns:
        Concatenated bytes of assembled instructions.

    Raises:
        AssemblerError: If an unrecognized instruction is encountered.
    """
    result = bytearray()
    labels: Dict[str, int] = {}

    for line_num, raw_line in enumerate(assembly_text.strip().splitlines(), 1):
        line = raw_line.strip()

        # Skip empty lines and comments
        if not line or line.startswith(";") or line.startswith("#"):
            continue

        # Label tracking (for future use)
        if line.endswith(":"):
            label_name = line.rstrip(":").strip()
            labels[label_name] = len(result)
            continue

        # Tokenize: split on whitespace and commas
        tokens = []
        current = ""
        for ch in line:
            if ch in (" ", "\t"):
                if current:
                    tokens.append(current)
                    current = ""
            elif ch == ",":
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(",")
            elif ch == ";":
                break  # Inline comment
            else:
                current += ch
        if current:
            tokens.append(current)

        if not tokens:
            continue

        mnemonic = tokens[0].lower()

        # Special handling for MOV variants based on operand types
        if mnemonic == "mov":
            if len(tokens) >= 2 and "dword" in tokens[1].lower() and "ptr" in tokens[1].lower():
                chunk = _asm_mov_dword_ptr(tokens, line_num)
            elif len(tokens) >= 2 and tokens[1].strip().lower().rstrip("16") in _X86_REGISTERS:
                if tokens[1].strip().lower().endswith("16"):
                    chunk = _asm_mov_reg_imm16(tokens, line_num)
                elif tokens[1].strip().lower().endswith("8") or tokens[1].strip().lower().endswith("l"):
                    chunk = _asm_mov_reg_imm8(tokens, line_num)
                else:
                    chunk = _asm_mov_reg_imm32(tokens, line_num)
            else:
                raise AssemblerError(
                    f"Line {line_num}: Unrecognized MOV variant: {' '.join(tokens)}"
                )
        elif mnemonic in _ASSEMBLER_DISPATCH:
            handler = _ASSEMBLER_DISPATCH[mnemonic]
            chunk = handler(tokens, line_num)
        else:
            raise AssemblerError(
                f"Line {line_num}: Unrecognized instruction: {mnemonic}. "
                f"Supported: {', '.join(_ASSEMBLER_DISPATCH.keys())}, MOV"
            )

        result.extend(chunk)

    return bytes(result)


def assemble_hex(hex_string: str) -> bytes:
    """
    Convert a hex string (e.g. "90 90 C3" or "9090C3") to raw bytes.

    Args:
        hex_string: Space-separated or contiguous hex bytes.

    Returns:
        Raw bytes.

    Raises:
        ValueError: If the hex string contains invalid characters.
    """
    cleaned = hex_string.replace(" ", "").replace("\n", "").replace("\t", "")
    if len(cleaned) % 2 != 0:
        raise ValueError(f"Hex string has odd length: {len(cleaned)}")
    return bytes.fromhex(cleaned)


# ═══════════════════════════════════════════════════════════════════════════
#  MEMORY HOOK CLASS
# ═══════════════════════════════════════════════════════════════════════════

class MemoryHook:
    """
    Represents a single inline memory hook on a target function.

    Patches the first bytes of a target function with a JMP instruction
    that redirects execution to a custom hook function. The original
    bytes are backed up so they can be restored when the hook is removed.

    The hook operates at the process memory level using Windows API calls
    (VirtualProtect, ReadProcessMemory, WriteProcessMemory).

    For x86 (32-bit):
        Writes a 5-byte E9 relative JMP (JMP rel32).

    For x64 (64-bit):
        Writes a 14-byte absolute JMP using the FF 25 trampoline.

    Attributes:
        process_handle: Handle to the target process.
        target_address: Address of the function to hook.
        hook_function_address: Address of the hook handler function.
        original_bytes_backup: Original bytes overwritten by the JMP.
        hook_size: Size of the patch in bytes (5 for x86, 14 for x64).
        is_installed: Whether the hook is currently active.
        is_64bit: Whether the target process is 64-bit.
        name: Optional human-readable name for this hook.
    """

    def __init__(
        self,
        process_handle: int,
        target_address: int,
        hook_function_address: int,
        original_bytes_backup: bytes,
        name: Optional[str] = None,
        is_64bit: bool = False,
    ):
        """
        Initialize a MemoryHook instance.

        Args:
            process_handle: Valid handle to the target process with
                PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
                access rights.
            target_address: Absolute address of the function entry point
                to be hooked.
            hook_function_address: Absolute address of the detour function
                that will receive control when the hook is triggered.
            original_bytes_backup: Pre-saved copy of the original bytes at
                target_address. Must be at least hook_size bytes long.
            name: Optional descriptive name (e.g. "NoClip", "SpeedHack").
            is_64bit: Whether the target process is 64-bit.
        """
        self.process_handle = process_handle
        self.target_address = target_address
        self.hook_function_address = hook_function_address
        self.original_bytes_backup = original_bytes_backup
        self.name = name or f"Hook@0x{target_address:X}"
        self.is_64bit = is_64bit
        self._installed = False

        # Determine patch size based on architecture
        self.hook_size = 14 if is_64bit else 5

        # Validate backup size
        if len(original_bytes_backup) < self.hook_size:
            raise HookError(
                f"Original bytes backup ({len(original_bytes_backup)} bytes) "
                f"is smaller than required hook size ({self.hook_size} bytes)"
            )

    @property
    def is_installed(self) -> bool:
        """Return True if the hook is currently installed/active."""
        return self._installed

    def install(self) -> None:
        """
        Install the hook by writing a JMP instruction at the target address.

        Steps:
            1. Change memory protection to PAGE_EXECUTE_READWRITE.
            2. Read and verify current bytes at target_address.
            3. Write the JMP trampoline to redirect to hook_function_address.
            4. Restore original memory protection.
            5. Flush the CPU instruction cache.

        Raises:
            HookAlreadyInstalledError: If the hook is already installed.
            MemoryAccessError: If any memory operation fails.
            HookError: If the target bytes have been modified since backup.
        """
        if self._installed:
            raise HookAlreadyInstalledError(
                f"Hook '{self.name}' is already installed at 0x{self.target_address:X}"
            )

        logger.debug(
            f"Installing hook '{self.name}' at 0x{self.target_address:X} "
            f"-> 0x{self.hook_function_address:X} "
            f"({'x64' if self.is_64bit else 'x86'}, patch={self.hook_size} bytes)"
        )

        try:
            # Step 1: Make memory writable + executable
            old_protect = _virtual_protect(
                self.process_handle,
                self.target_address,
                self.hook_size,
                PAGE_EXECUTE_READWRITE,
            )

            try:
                # Step 2: Verify current bytes match backup (optional safety check)
                current_bytes = _read_process_memory(
                    self.process_handle,
                    self.target_address,
                    self.hook_size,
                )

                # Step 3: Build the JMP trampoline
                if self.is_64bit:
                    jmp_code = _build_jmp_x64(
                        self.target_address, self.hook_function_address
                    )
                else:
                    jmp_code = _build_jmp_x86(
                        self.target_address, self.hook_function_address
                    )

                # Step 4: Write the JMP instruction
                written = _write_process_memory(
                    self.process_handle,
                    self.target_address,
                    jmp_code,
                )

                # Step 5: Flush instruction cache
                _flush_instruction_cache(
                    self.process_handle,
                    self.target_address,
                    self.hook_size,
                )

            finally:
                # Always restore protection, even on failure
                _virtual_protect(
                    self.process_handle,
                    self.target_address,
                    self.hook_size,
                    old_protect,
                )

            self._installed = True
            logger.info(
                f"Hook '{self.name}' installed successfully "
                f"(overwrote {self.hook_size} bytes, previous: "
                f"{current_bytes.hex()})"
            )

        except MemoryAccessError as e:
            raise HookError(
                f"Failed to install hook '{self.name}': {e}"
            ) from e

    def uninstall(self) -> None:
        """
        Remove the hook by restoring the original function bytes.

        Steps:
            1. Change memory protection to PAGE_EXECUTE_READWRITE.
            2. Write back the original bytes from the backup.
            3. Restore original memory protection.
            4. Flush the CPU instruction cache.

        Raises:
            HookNotInstalledError: If the hook is not currently installed.
            MemoryAccessError: If any memory operation fails.
        """
        if not self._installed:
            raise HookNotInstalledError(
                f"Hook '{self.name}' is not installed"
            )

        logger.debug(
            f"Uninstalling hook '{self.name}' at 0x{self.target_address:X}"
        )

        try:
            old_protect = _virtual_protect(
                self.process_handle,
                self.target_address,
                self.hook_size,
                PAGE_EXECUTE_READWRITE,
            )

            try:
                _write_process_memory(
                    self.process_handle,
                    self.target_address,
                    self.original_bytes_backup[: self.hook_size],
                )
                _flush_instruction_cache(
                    self.process_handle,
                    self.target_address,
                    self.hook_size,
                )
            finally:
                _virtual_protect(
                    self.process_handle,
                    self.target_address,
                    self.hook_size,
                    old_protect,
                )

            self._installed = False
            logger.info(f"Hook '{self.name}' uninstalled successfully")

        except MemoryAccessError as e:
            raise HookError(
                f"Failed to uninstall hook '{self.name}': {e}"
            ) from e

    def __repr__(self) -> str:
        status = "ACTIVE" if self._installed else "INACTIVE"
        arch = "x64" if self.is_64bit else "x86"
        return (
            f"MemoryHook(name={self.name!r}, "
            f"target=0x{self.target_address:X}, "
            f"hook=0x{self.hook_function_address:X}, "
            f"{arch}, {status})"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  HOOK PRESETS — 40 predefined hook configurations
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HookPreset:
    """
    A predefined hook configuration.

    Attributes:
        name: Unique identifier for the hook (e.g. "RequireBypass").
        description: Human-readable description of what the hook does.
        offset_key: Key used to look up the target function address
            from the offset database.
        hook_type: Type of hook to install ("jmp", "nop", "ret", "patch").
        default_action: Default action when the hook fires
            ("bypass", "enable", "disable", "log", "modify").
        category: Category group for UI organization.
        patch_bytes: Optional custom patch bytes (if hook_type is "patch").
        risk_level: Risk assessment ("low", "medium", "high", "critical").
    """
    name: str
    description: str
    offset_key: str
    hook_type: str           # "jmp", "nop", "ret", "patch"
    default_action: str      # "bypass", "enable", "disable", "log", "modify"
    category: str = ""
    patch_bytes: Optional[str] = None  # hex string for "patch" type
    risk_level: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the preset to a dictionary."""
        d = {
            "name": self.name,
            "description": self.description,
            "offset_key": self.offset_key,
            "type": self.hook_type,
            "default_action": self.default_action,
            "category": self.category,
            "risk_level": self.risk_level,
        }
        if self.patch_bytes is not None:
            d["patch_bytes"] = self.patch_bytes
        return d


def _build_presets() -> List[HookPreset]:
    """
    Build the complete list of 40 hook presets organized by category.

    Categories:
        - Anti-Cheat Bypass (8 hooks)
        - Performance (6 hooks)
        - Movement (6 hooks)
        - Visual (6 hooks)
        - Utility (8 hooks)
        - Network (6 hooks)

    Returns:
        List of 40 HookPreset instances.
    """

    # ── ANTI-CHEAT BYPASS (8) ──────────────────────────────────────────
    anticheat = [
        HookPreset(
            name="RequireBypass",
            description="Bypass the require() security check to allow "
                        "loading modules from arbitrary paths",
            offset_key="requireCheckFunc",
            hook_type="nop",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="high",
        ),
        HookPreset(
            name="AntiKick",
            description="Prevent the server from kicking the local player "
                        "by patching the kick handler",
            offset_key="kickHandler",
            hook_type="ret",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="high",
        ),
        HookPreset(
            name="AntiTeleport",
            description="Disable the server-side teleport validation that "
                        "rejects rapid position changes",
            offset_key="teleportCheckFunc",
            hook_type="nop",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="high",
        ),
        HookPreset(
            name="CrashReporter",
            description="Suppress the crash reporter dialog to prevent "
                        "error popups and potential detection",
            offset_key="crashReporterInit",
            hook_type="ret",
            default_action="disable",
            category="Anti-Cheat",
            risk_level="low",
        ),
        HookPreset(
            name="ScriptContextValidation",
            description="Bypass ScriptContext security validation to allow "
                        "cross-context script execution",
            offset_key="scriptContextValidate",
            hook_type="nop",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="critical",
        ),
        HookPreset(
            name="SecurityCheckBypass",
            description="Patch the security integrity check that validates "
                        "code signing and module hashes",
            offset_key="securityCheckFunc",
            hook_type="nop",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="critical",
        ),
        HookPreset(
            name="HttpCheckBypass",
            description="Allow HTTP (non-HTTPS) requests by disabling "
                        "the HTTP security check",
            offset_key="httpCheckEnabled",
            hook_type="patch",
            default_action="bypass",
            category="Anti-Cheat",
            patch_bytes="B8 01 00 00 00 90 90",  # MOV EAX, 1; NOP; NOP
            risk_level="medium",
        ),
        HookPreset(
            name="ContentProviderValidation",
            description="Bypass ContentProvider asset hash validation "
                        "to allow modified or unsigned assets",
            offset_key="contentProviderVerify",
            hook_type="nop",
            default_action="bypass",
            category="Anti-Cheat",
            risk_level="medium",
        ),
    ]

    # ── PERFORMANCE (6) ─────────────────────────────────────────────────
    performance = [
        HookPreset(
            name="MaxFPSUnlock",
            description="Remove the 60 FPS cap by patching the frame "
                        "limiter's VSync/throttle function",
            offset_key="frameLimiterFunc",
            hook_type="ret",
            default_action="enable",
            category="Performance",
            risk_level="low",
        ),
        HookPreset(
            name="MemoryOptimizer",
            description="Hook the memory allocation path to reduce "
                        "fragmentation and pool small allocations",
            offset_key="memoryAllocFunc",
            hook_type="jmp",
            default_action="modify",
            category="Performance",
            risk_level="medium",
        ),
        HookPreset(
            name="GCPauseBypass",
            description="Bypass the Lua garbage collector's auto-pause "
                        "threshold to reduce stuttering",
            offset_key="gcPauseCheck",
            hook_type="nop",
            default_action="enable",
            category="Performance",
            risk_level="medium",
        ),
        HookPreset(
            name="TextureQualityOverride",
            description="Force maximum texture quality regardless of "
                        "GraphicsQuality level settings",
            offset_key="textureQualityCheck",
            hook_type="patch",
            default_action="modify",
            category="Performance",
            patch_bytes="B8 0A 00 00 00 90",  # MOV EAX, 10; NOP (max quality)
            risk_level="low",
        ),
        HookPreset(
            name="ShadowDisable",
            description="Disable dynamic shadow rendering to improve "
                        "FPS on lower-end hardware",
            offset_key="shadowRenderFunc",
            hook_type="ret",
            default_action="disable",
            category="Performance",
            risk_level="low",
        ),
        HookPreset(
            name="ParticleDisable",
            description="Disable particle emitter rendering to improve "
                        "FPS in particle-heavy games",
            offset_key="particleRenderFunc",
            hook_type="ret",
            default_action="disable",
            category="Performance",
            risk_level="low",
        ),
    ]

    # ── MOVEMENT (6) ────────────────────────────────────────────────────
    movement = [
        HookPreset(
            name="NoClip",
            description="Disable collision detection for the local "
                        "character, allowing free movement through walls",
            offset_key="canCollideCheck",
            hook_type="nop",
            default_action="enable",
            category="Movement",
            risk_level="medium",
        ),
        HookPreset(
            name="SpeedHack",
            description="Hook the walkspeed validation to bypass the "
                        "server clamp on character movement speed",
            offset_key="walkSpeedClamp",
            hook_type="nop",
            default_action="enable",
            category="Movement",
            risk_level="high",
        ),
        HookPreset(
            name="FlyHack",
            description="Patch the physics gravity application to allow "
                        "free-flight mode in the 3D world",
            offset_key="gravityApplyFunc",
            hook_type="jmp",
            default_action="enable",
            category="Movement",
            risk_level="high",
        ),
        HookPreset(
            name="GravityLock",
            description="Lock gravity to a custom value by patching the "
                        "workspace gravity read path",
            offset_key="gravityGetter",
            hook_type="patch",
            default_action="modify",
            category="Movement",
            patch_bytes="B8 2A C4 8E 3E 90 90",  # MOV EAX, ~196.2f; NOP; NOP
            risk_level="medium",
        ),
        HookPreset(
            name="InfiniteJump",
            description="Bypass the grounded/airborne state check to "
                        "allow jumping while in mid-air",
            offset_key="jumpStateCheck",
            hook_type="nop",
            default_action="enable",
            category="Movement",
            risk_level="medium",
        ),
        HookPreset(
            name="TeleportBypass",
            description="Disable the anti-teleport validation that "
                        "detects and rejects position teleportation",
            offset_key="antiTeleportCheck",
            hook_type="nop",
            default_action="bypass",
            category="Movement",
            risk_level="high",
        ),
    ]

    # ── VISUAL (6) ──────────────────────────────────────────────────────
    visual = [
        HookPreset(
            name="ESPEnable",
            description="Enable ESP (Extra Sensory Perception) overlay "
                        "by hooking the render pipeline to draw highlights",
            offset_key="renderPostProcess",
            hook_type="jmp",
            default_action="enable",
            category="Visual",
            risk_level="medium",
        ),
        HookPreset(
            name="ChamsEnable",
            description="Enable chams (colored material override) for "
                        "player/NPC models by hooking the material binder",
            offset_key="materialBinderFunc",
            hook_type="jmp",
            default_action="enable",
            category="Visual",
            risk_level="medium",
        ),
        HookPreset(
            name="Fullbright",
            description="Force full ambient lighting by patching the "
                        "lighting calculation to return maximum brightness",
            offset_key="lightingCalcFunc",
            hook_type="patch",
            default_action="enable",
            category="Visual",
            patch_bytes="B8 00 00 80 3F 90 90",  # MOV EAX, 1.0f; NOP; NOP
            risk_level="low",
        ),
        HookPreset(
            name="RemoveFog",
            description="Disable atmospheric fog rendering by returning "
                        "early from the fog update function",
            offset_key="fogUpdateFunc",
            hook_type="ret",
            default_action="disable",
            category="Visual",
            risk_level="low",
        ),
        HookPreset(
            name="RemoveBloom",
            description="Disable bloom post-processing effect to "
                        "improve visual clarity and performance",
            offset_key="bloomRenderFunc",
            hook_type="ret",
            default_action="disable",
            category="Visual",
            risk_level="low",
        ),
        HookPreset(
            name="XRay",
            description="Enable wall transparency (X-ray vision) by "
                        "patching the occlusion/depth test in rendering",
            offset_key="depthTestFunc",
            hook_type="nop",
            default_action="enable",
            category="Visual",
            risk_level="medium",
        ),
    ]

    # ── UTILITY (8) ─────────────────────────────────────────────────────
    utility = [
        HookPreset(
            name="RemoteSpy",
            description="Hook the RemoteEvent/RemoteFunction dispatch "
                        "to log all network call arguments and targets",
            offset_key="remoteDispatchFunc",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="medium",
        ),
        HookPreset(
            name="NamecallHook",
            description="Hook __namecall metamethod to intercept and log "
                        "method calls on Roblox instances",
            offset_key="namecallHandler",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="medium",
        ),
        HookPreset(
            name="PrintHook",
            description="Hook the print/output functions to capture and "
                        "redirect all Lua stdout to the panel console",
            offset_key="luaPrintFunc",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="low",
        ),
        HookPreset(
            name="ErrorHook",
            description="Hook the error handler to capture and display "
                        "Lua errors with full stack traces in the panel",
            offset_key="luaErrorHandler",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="low",
        ),
        HookPreset(
            name="HttpLogger",
            description="Intercept HTTP requests to log all URLs, methods, "
                        "and response data for debugging and inspection",
            offset_key="httpRequestFunc",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="medium",
        ),
        HookPreset(
            name="AssetCache",
            description="Hook the asset loading pipeline to cache assets "
                        "locally and reduce redundant downloads",
            offset_key="assetLoadFunc",
            hook_type="jmp",
            default_action="modify",
            category="Utility",
            risk_level="low",
        ),
        HookPreset(
            name="ScriptDebugger",
            description="Attach a debug hook to the Lua VM to enable "
                        "step-through debugging of game scripts",
            offset_key="luaDebugHook",
            hook_type="jmp",
            default_action="enable",
            category="Utility",
            risk_level="high",
        ),
        HookPreset(
            name="ConsoleOutput",
            description="Redirect Roblox's internal console output to the "
                        "panel's console tab for real-time log viewing",
            offset_key="consoleOutputFunc",
            hook_type="jmp",
            default_action="log",
            category="Utility",
            risk_level="low",
        ),
    ]

    # ── NETWORK (6) ─────────────────────────────────────────────────────
    network = [
        HookPreset(
            name="PacketLogger",
            description="Log all incoming/outgoing network packets "
                        "including their serialized data and metadata",
            offset_key="packetSendFunc",
            hook_type="jmp",
            default_action="log",
            category="Network",
            risk_level="medium",
        ),
        HookPreset(
            name="LagSwitch",
            description="Toggle network packet sending on/off to simulate "
                        "lag switch for desync exploits",
            offset_key="packetSendGate",
            hook_type="jmp",
            default_action="enable",
            category="Network",
            risk_level="high",
        ),
        HookPreset(
            name="Desync",
            description="Introduce deliberate client-server desync by "
                        "delaying outgoing position updates",
            offset_key="positionUpdateFunc",
            hook_type="jmp",
            default_action="modify",
            category="Network",
            risk_level="high",
        ),
        HookPreset(
            name="PingSpoof",
            description="Spoof the client's reported ping to the server "
                        "to mask actual network latency",
            offset_key="pingReportFunc",
            hook_type="jmp",
            default_action="modify",
            category="Network",
            risk_level="high",
        ),
        HookPreset(
            name="NetworkSimulator",
            description="Simulate various network conditions (latency, "
                        "packet loss, jitter) by hooking the send/receive path",
            offset_key="networkIOFunc",
            hook_type="jmp",
            default_action="modify",
            category="Network",
            risk_level="high",
        ),
        HookPreset(
            name="PacketModifier",
            description="Intercept and modify network packet contents "
                        "before transmission to alter game behavior",
            offset_key="packetSerializeFunc",
            hook_type="jmp",
            default_action="modify",
            category="Network",
            risk_level="critical",
        ),
    ]

    return anticheat + performance + movement + visual + utility + network


# Build the global preset list and lookup dictionary
HOOK_PRESETS: List[HookPreset] = _build_presets()
_HOOK_PRESET_MAP: Dict[str, HookPreset] = {p.name: p for p in HOOK_PRESETS}


def get_preset(name: str) -> HookPreset:
    """
    Look up a hook preset by name.

    Args:
        name: The preset name (e.g. "NoClip", "SpeedHack").

    Returns:
        The matching HookPreset instance.

    Raises:
        HookPresetNotFoundError: If no preset with the given name exists.
    """
    preset = _HOOK_PRESET_MAP.get(name)
    if preset is None:
        available = ", ".join(sorted(_HOOK_PRESET_MAP.keys()))
        raise HookPresetNotFoundError(
            f"Unknown hook preset '{name}'. Available: {available}"
        )
    return preset


def get_presets_by_category(category: str) -> List[HookPreset]:
    """
    Get all hook presets belonging to a specific category.

    Args:
        category: Category name (e.g. "Anti-Cheat", "Movement", "Visual").

    Returns:
        List of HookPreset instances in the given category.
    """
    return [p for p in HOOK_PRESETS if p.category == category]


def get_all_categories() -> List[str]:
    """
    Get a list of all unique hook preset categories.

    Returns:
        Sorted list of category names.
    """
    return sorted(set(p.category for p in HOOK_PRESETS))


def get_presets_summary() -> Dict[str, Any]:
    """
    Get a summary of all hook presets organized by category.

    Returns:
        Dictionary with category names as keys and lists of preset
        dicts as values, plus total count.
    """
    summary: Dict[str, List[Dict[str, Any]]] = {}
    for preset in HOOK_PRESETS:
        cat = preset.category
        if cat not in summary:
            summary[cat] = []
        summary[cat].append(preset.to_dict())
    return {
        "total": len(HOOK_PRESETS),
        "categories": summary,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  FFLAG MANAGER
# ═══════════════════════════════════════════════════════════════════════════

# Default FFlag presets: list of (name, default_value, modified_value) tuples
FFLAG_PRESETS: Dict[str, List[Dict[str, str]]] = {
    "performance": [
        {"name": "FFlagDebugGraphicsDisableLeanUI", "default": "False", "value": "True"},
        {"name": "FFlagDebugGraphicsPreferD3D11", "default": "False", "value": "True"},
        {"name": "FIntTaskSchedulerTargetFps", "default": "60", "value": "0"},
    ],
    "anti_cheat_bypass": [
        {"name": "FFlagDebugEnableNewConstraintSolver", "default": "True", "value": "False"},
        {"name": "DFIntCullRate", "default": "256", "value": "0"},
    ],
    "rendering": [
        {"name": "FFlagDebugGraphicsForceFuture", "default": "False", "value": "True"},
        {"name": "FFlagEnableShadowShift", "default": "True", "value": "False"},
        {"name": "FFlagDisablePostFX", "default": "False", "value": "True"},
    ],
    "network": [
        {"name": "FFlagDebugNetworkPhysicsOptimizations", "default": "False", "value": "True"},
        {"name": "DFIntNetworkPhysicsSendRate", "default": "20", "value": "60"},
    ],
}

# Remote FFlag JSON source
FFLAG_REMOTE_URL = "https://imtheo.lol/Offsets/FFlags.json"


class FFlagManager:
    """
    Manages Roblox Fast Flags (FFlags) — runtime configuration variables
    that control engine behavior.

    Provides functionality to:
        - Apply predefined FFlag presets (set specific flags to new values)
        - Reset modified FFlags back to their defaults
        - Fetch the latest FFlag database from a remote JSON source
        - Get/set individual FFlag values

    FFlags are typically stored as string key-value pairs in memory and can
    be modified to alter Roblox engine behavior at runtime.

    Attributes:
        current_flags: Dictionary of currently loaded FFlag name -> value pairs.
        modified_flags: Set of flag names that have been modified from defaults.
        defaults: Dictionary of original default values for modified flags.
    """

    def __init__(self):
        """Initialize the FFlag manager with empty state."""
        self.current_flags: Dict[str, str] = {}
        self.modified_flags: Dict[str, str] = {}  # name -> original value
        self.defaults: Dict[str, str] = {}
        self._lock = threading.Lock()

    def load_flags(self, flags: Dict[str, str]) -> None:
        """
        Load a complete set of FFlags from a dictionary.

        Args:
            flags: Dictionary mapping FFlag names to their string values.
        """
        with self._lock:
            self.current_flags = dict(flags)
            logger.info(f"Loaded {len(flags)} FFlags")

    def get_flag(self, name: str, default: str = "") -> str:
        """
        Get the current value of an FFlag.

        Args:
            name: The FFlag name.
            default: Default value if the flag is not found.

        Returns:
            The flag's current value, or the default.
        """
        with self._lock:
            return self.current_flags.get(name, default)

    def set_flag(self, name: str, value: str) -> bool:
        """
        Set an FFlag to a new value, recording the original if this is
        the first modification.

        Args:
            name: The FFlag name.
            value: The new string value.

        Returns:
            True if the flag was set (or was already set to this value).
        """
        with self._lock:
            if name not in self.current_flags:
                logger.warning(f"FFlag '{name}' not found in current flags")
                return False

            if name not in self.modified_flags:
                self.modified_flags[name] = self.current_flags[name]
                logger.debug(f"FFlag '{name}' original value: {self.current_flags[name]}")

            self.current_flags[name] = value
            logger.info(f"FFlag '{name}' set to '{value}'")
            return True

    def apply_preset(self, preset_name: str) -> Dict[str, bool]:
        """
        Apply a named FFlag preset by setting each flag to its preset value.

        Args:
            preset_name: Name of the preset (e.g. "performance", "rendering").

        Returns:
            Dictionary mapping each flag name to whether it was set successfully.

        Raises:
            ValueError: If the preset name is not recognized.
        """
        if preset_name not in FFLAG_PRESETS:
            available = ", ".join(FFLAG_PRESETS.keys())
            raise ValueError(
                f"Unknown FFlag preset '{preset_name}'. Available: {available}"
            )

        preset = FFLAG_PRESETS[preset_name]
        results: Dict[str, bool] = {}

        for entry in preset:
            success = self.set_flag(entry["name"], entry["value"])
            results[entry["name"]] = success

        applied_count = sum(1 for v in results.values() if v)
        logger.info(
            f"Applied preset '{preset_name}': "
            f"{applied_count}/{len(preset)} flags set"
        )
        return results

    def reset_flag(self, name: str) -> bool:
        """
        Reset a single FFlag to its original default value.

        Args:
            name: The FFlag name to reset.

        Returns:
            True if the flag was reset, False if it wasn't previously modified.
        """
        with self._lock:
            if name not in self.modified_flags:
                logger.warning(f"FFlag '{name}' was not modified, nothing to reset")
                return False

            original = self.modified_flags.pop(name)
            self.current_flags[name] = original
            logger.info(f"FFlag '{name}' reset to '{original}'")
            return True

    def reset_all(self) -> int:
        """
        Reset all modified FFlags back to their original default values.

        Returns:
            The number of flags that were reset.
        """
        with self._lock:
            count = len(self.modified_flags)
            for name, original in self.modified_flags.items():
                self.current_flags[name] = original
                logger.debug(f"Reset FFlag '{name}' to '{original}'")

            self.modified_flags.clear()
            logger.info(f"Reset {count} FFlags to defaults")
            return count

    def get_modifications(self) -> Dict[str, Dict[str, str]]:
        """
        Get a summary of all currently modified flags.

        Returns:
            Dictionary mapping flag names to {"original": str, "current": str}.
        """
        with self._lock:
            return {
                name: {
                    "original": original,
                    "current": self.current_flags.get(name, ""),
                }
                for name, original in self.modified_flags.items()
            }

    def fetch_remote(self, url: str = FFLAG_REMOTE_URL,
                     timeout: float = 10.0) -> Dict[str, str]:
        """
        Fetch FFlags from a remote JSON source.

        The remote JSON should be a flat dictionary mapping FFlag names
        to their string values.

        Args:
            url: URL of the JSON file to fetch.
            timeout: Request timeout in seconds.

        Returns:
            Dictionary of fetched FFlag name -> value pairs.

        Raises:
            urllib.error.URLError: If the fetch fails.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        logger.info(f"Fetching FFlags from {url}...")
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RobloxPanel/4.0 (HookManager)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)

        # Accept both flat dict and nested structures
        if isinstance(data, dict):
            flags: Dict[str, str] = {}
            for key, value in data.items():
                if isinstance(value, str):
                    flags[key] = value
                elif isinstance(value, (int, float, bool)):
                    flags[key] = str(value)
                elif isinstance(value, dict):
                    # Nested: flatten one level
                    for sub_key, sub_val in value.items():
                        if isinstance(sub_val, str):
                            flags[sub_key] = sub_val
                        elif isinstance(sub_val, (int, float, bool)):
                            flags[sub_key] = str(sub_val)
            self.load_flags(flags)
            return flags
        else:
            raise ValueError(f"Expected JSON dict, got {type(data).__name__}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the FFlag manager state to a dictionary.

        Returns:
            Dictionary with current flags, modifications, and metadata.
        """
        with self._lock:
            return {
                "total_flags": len(self.current_flags),
                "modified_count": len(self.modified_flags),
                "modifications": self.get_modifications(),
                "available_presets": list(FFLAG_PRESETS.keys()),
            }


# ═══════════════════════════════════════════════════════════════════════════
#  HOOK MANAGER CLASS
# ═══════════════════════════════════════════════════════════════════════════

class HookManager:
    """
    Centralized manager for all memory hooks in the target Roblox process.

    Provides a high-level interface for installing, uninstalling, and
    querying hooks. Manages a registry of active MemoryHook instances
    and coordinates with the offset database to resolve target addresses.

    The HookManager supports multiple hook types:
        - "jmp": Write a JMP trampoline to redirect execution.
        - "nop": Overwrite the target with NOP instructions.
        - "ret": Overwrite the target with a RET instruction.
        - "patch": Write custom bytes from a patch_bytes hex string.

    Attributes:
        process_handle: Handle to the target Roblox process.
        base_address: Base address of the Roblox executable module.
        hooks: Dictionary of installed MemoryHook instances keyed by name.
        is_loaded: Whether the manager has been initialized with a valid
            process handle and base address.
        is_64bit: Whether the target process is 64-bit.
    """

    # Default hook patch sizes by type (minimum bytes to overwrite)
    _MIN_PATCH_SIZES: Dict[str, int] = {
        "jmp": 5,    # Minimum for x86 JMP rel32
        "nop": 1,    # Minimum for a single NOP
        "ret": 1,    # Minimum for a single RET
        "patch": 1,  # Depends on patch_bytes content
    }

    def __init__(self, process_handle: int, base_address: int):
        """
        Initialize the HookManager.

        Args:
            process_handle: Valid handle to the Roblox process with
                PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
                access rights. Pass 0 or None for a "dry run" manager
                (hooks can be configured but not installed).
            base_address: Base address of the RobloxPlayerBeta.exe module
                in the target process. Used to calculate absolute addresses
                from relative offsets.
        """
        self.process_handle = process_handle or 0
        self.base_address = base_address or 0
        self._hooks: Dict[str, MemoryHook] = {}
        self._is_loaded = bool(process_handle and base_address)
        self._is_64bit = False
        self._lock = threading.Lock()

        # Detect architecture if we have a valid handle
        if self._is_loaded:
            try:
                self._is_64bit = _is_64bit_process(self.process_handle)
                logger.info(
                    f"HookManager initialized: base=0x{self.base_address:X}, "
                    f"arch={'x64' if self._is_64bit else 'x86'}"
                )
            except Exception as e:
                logger.warning(f"Could not detect process architecture: {e}")
                # Default to 64-bit on modern systems
                self._is_64bit = True

    @property
    def is_loaded(self) -> bool:
        """Return True if the manager has a valid process handle."""
        return self._is_loaded

    @property
    def is_64bit(self) -> bool:
        """Return True if the target process is 64-bit."""
        return self._is_64bit

    def resolve_address(self, offset_key: str, offsets: Optional[Dict[str, Any]] = None
                        ) -> int:
        """
        Resolve an offset key to an absolute memory address.

        Looks up the offset value from the provided offsets dictionary
        (or the global RawOffsets if none is provided) and adds it to
        the base address.

        Args:
            offset_key: Key to look up in the offsets dict.
            offsets: Optional offsets dictionary. If None, uses a flat
                lookup strategy.

        Returns:
            Absolute address (base_address + offset).

        Raises:
            HookError: If the offset key cannot be resolved.
        """
        if offsets is None:
            offsets = {}

        # Try direct key lookup
        if offset_key in offsets:
            offset = offsets[offset_key]
            if isinstance(offset, int):
                return self.base_address + offset
            elif isinstance(offset, dict):
                # Some offsets are nested dicts, try common sub-keys
                for sub_key in ("offset", "address", "addr", "ptr"):
                    if sub_key in offset and isinstance(offset[sub_key], int):
                        return self.base_address + offset[sub_key]

        # Try case-insensitive lookup
        for key, value in offsets.items():
            if key.lower() == offset_key.lower():
                if isinstance(value, int):
                    return self.base_address + value

        raise HookError(
            f"Cannot resolve offset key '{offset_key}'. "
            f"Ensure the offset exists in the offsets database."
        )

    def install_hook(
        self,
        target_name: str,
        hook_type: str,
        hook_data: Dict[str, Any],
        offsets: Optional[Dict[str, Any]] = None,
    ) -> MemoryHook:
        """
        Install a named hook.

        Resolves the target address from the offset database, backs up
        the original bytes, and installs the appropriate patch.

        Args:
            target_name: Unique name for this hook (e.g. "NoClip").
            hook_type: Type of hook to install:
                "jmp"  - JMP trampoline (requires hook_data["hook_address"])
                "nop"  - NOP sled (requires hook_data["nop_count"] or uses default)
                "ret"  - RET instruction
                "patch" - Custom bytes (requires hook_data["patch_bytes"])
            hook_data: Dictionary containing hook-specific data:
                - offset_key: Key to look up the target address.
                - hook_address: For "jmp" type, the address to jump to.
                - nop_count: For "nop" type, number of NOPs (default: 5).
                - patch_bytes: For "patch" type, hex string of custom bytes.
            offsets: Optional offsets database for address resolution.

        Returns:
            The installed MemoryHook instance.

        Raises:
            HookAlreadyInstalledError: If a hook with this name exists.
            HookError: If installation fails.
        """
        with self._lock:
            if target_name in self._hooks:
                raise HookAlreadyInstalledError(
                    f"Hook '{target_name}' is already installed"
                )

            if not self._is_loaded:
                raise HookError(
                    "HookManager is not loaded (invalid process handle or "
                    "base address). Cannot install hooks."
                )

            # Resolve target address
            offset_key = hook_data.get("offset_key", "")
            if offset_key:
                target_address = self.resolve_address(offset_key, offsets)
            elif "target_address" in hook_data:
                target_address = hook_data["target_address"]
            else:
                raise HookError(
                    f"Cannot install hook '{target_name}': no offset_key "
                    f"or target_address provided"
                )

            logger.debug(
                f"Installing hook '{target_name}': type={hook_type}, "
                f"target=0x{target_address:X}"
            )

            # Determine patch size and build patch bytes
            hook_type = hook_type.lower()

            if hook_type == "jmp":
                hook_address = hook_data.get("hook_address", 0)
                if not hook_address:
                    raise HookError(
                        f"JMP hook '{target_name}' requires 'hook_address'"
                    )
                patch_size = 14 if self._is_64bit else 5

            elif hook_type == "nop":
                nop_count = hook_data.get("nop_count", 5)
                patch_size = max(1, int(nop_count))

            elif hook_type == "ret":
                patch_size = 1

            elif hook_type == "patch":
                patch_hex = hook_data.get("patch_bytes", "")
                if not patch_hex:
                    raise HookError(
                        f"Patch hook '{target_name}' requires 'patch_bytes'"
                    )
                patch_bytes = assemble_hex(patch_hex)
                patch_size = len(patch_bytes)

            else:
                raise HookError(
                    f"Unknown hook type '{hook_type}'. "
                    f"Supported: jmp, nop, ret, patch"
                )

            # Back up original bytes
            try:
                original_bytes = _read_process_memory(
                    self.process_handle, target_address, patch_size
                )
            except MemoryAccessError as e:
                raise HookError(
                    f"Failed to read original bytes for hook '{target_name}': {e}"
                ) from e

            # Create the MemoryHook instance
            hook_addr_for_trampoline = (
                hook_data.get("hook_address", 0) if hook_type == "jmp" else 0
            )

            hook = MemoryHook(
                process_handle=self.process_handle,
                target_address=target_address,
                hook_function_address=hook_addr_for_trampoline,
                original_bytes_backup=original_bytes,
                name=target_name,
                is_64bit=self._is_64bit,
            )

            # Install the hook
            hook.install()

            # For non-JMP hooks, also apply the specific patch
            if hook_type == "nop":
                self._apply_nop_patch(hook, hook_data.get("nop_count", 5))
            elif hook_type == "ret":
                self._apply_ret_patch(hook)
            elif hook_type == "patch":
                self._apply_custom_patch(hook, assemble_hex(patch_hex))

            self._hooks[target_name] = hook
            logger.info(
                f"Hook '{target_name}' installed at 0x{target_address:X} "
                f"(type={hook_type}, size={patch_size})"
            )
            return hook

    def _apply_nop_patch(self, hook: MemoryHook, count: int) -> None:
        """
        Apply a NOP sled over the hooked region.

        Args:
            hook: The MemoryHook instance (already has memory unprotected
                from the JMP install).
            count: Number of NOP bytes to write.
        """
        nop_bytes = _build_nop_sled(count)
        old_protect = _virtual_protect(
            hook.process_handle, hook.target_address,
            len(nop_bytes), PAGE_EXECUTE_READWRITE,
        )
        try:
            _write_process_memory(
                hook.process_handle, hook.target_address, nop_bytes
            )
            _flush_instruction_cache(
                hook.process_handle, hook.target_address, len(nop_bytes)
            )
        finally:
            _virtual_protect(
                hook.process_handle, hook.target_address,
                len(nop_bytes), old_protect,
            )

    def _apply_ret_patch(self, hook: MemoryHook) -> None:
        """
        Apply a RET instruction at the hooked address.

        Args:
            hook: The MemoryHook instance.
        """
        ret_bytes = bytes([OP_RET])
        old_protect = _virtual_protect(
            hook.process_handle, hook.target_address,
            len(ret_bytes), PAGE_EXECUTE_READWRITE,
        )
        try:
            _write_process_memory(
                hook.process_handle, hook.target_address, ret_bytes
            )
            _flush_instruction_cache(
                hook.process_handle, hook.target_address, len(ret_bytes)
            )
        finally:
            _virtual_protect(
                hook.process_handle, hook.target_address,
                len(ret_bytes), old_protect,
            )

    def _apply_custom_patch(self, hook: MemoryHook, patch_bytes: bytes) -> None:
        """
        Apply custom patch bytes at the hooked address.

        Args:
            hook: The MemoryHook instance.
            patch_bytes: Raw bytes to write.
        """
        old_protect = _virtual_protect(
            hook.process_handle, hook.target_address,
            len(patch_bytes), PAGE_EXECUTE_READWRITE,
        )
        try:
            _write_process_memory(
                hook.process_handle, hook.target_address, patch_bytes
            )
            _flush_instruction_cache(
                hook.process_handle, hook.target_address, len(patch_bytes)
            )
        finally:
            _virtual_protect(
                hook.process_handle, hook.target_address,
                len(patch_bytes), old_protect,
            )

    def uninstall_hook(self, target_name: str) -> bool:
        """
        Uninstall a named hook by restoring its original bytes.

        Args:
            target_name: Name of the hook to uninstall.

        Returns:
            True if the hook was successfully uninstalled.

        Raises:
            HookNotInstalledError: If no hook with this name exists.
        """
        with self._lock:
            hook = self._hooks.get(target_name)
            if hook is None:
                raise HookNotInstalledError(
                    f"Hook '{target_name}' is not installed"
                )

            hook.uninstall()
            del self._hooks[target_name]
            logger.info(f"Hook '{target_name}' uninstalled and removed")
            return True

    def uninstall_all(self) -> int:
        """
        Uninstall all active hooks.

        Hooks are uninstalled in reverse order of installation (LIFO)
        to minimize the chance of leaving dangling JMP targets.

        Returns:
            The number of hooks that were uninstalled.
        """
        with self._lock:
            count = 0
            names = list(self._hooks.keys())
            for name in reversed(names):
                try:
                    hook = self._hooks[name]
                    hook.uninstall()
                    count += 1
                except HookError as e:
                    logger.error(f"Failed to uninstall hook '{name}': {e}")
            self._hooks.clear()
            logger.info(f"Uninstalled {count} hooks (cleaned all)")
            return count

    def get_installed_hooks(self) -> List[Dict[str, Any]]:
        """
        Get information about all currently installed hooks.

        Returns:
            List of dictionaries, each containing:
                - name: Hook name
                - target_address: Target function address (hex string)
                - hook_address: Hook function address (hex string)
                - is_installed: Whether the hook is active
                - is_64bit: Architecture flag
        """
        with self._lock:
            return [
                {
                    "name": hook.name,
                    "target_address": f"0x{hook.target_address:X}",
                    "hook_address": f"0x{hook.hook_function_address:X}",
                    "is_installed": hook.is_installed,
                    "is_64bit": hook.is_64bit,
                    "hook_size": hook.hook_size,
                }
                for hook in self._hooks.values()
            ]

    def is_hook_installed(self, target_name: str) -> bool:
        """
        Check if a specific hook is currently installed.

        Args:
            target_name: Name of the hook to check.

        Returns:
            True if the hook exists and is installed.
        """
        with self._lock:
            hook = self._hooks.get(target_name)
            return hook is not None and hook.is_installed

    def install_preset(
        self,
        preset_name: str,
        hook_function_address: int = 0,
        offsets: Optional[Dict[str, Any]] = None,
    ) -> MemoryHook:
        """
        Install a hook from a predefined preset.

        Convenience method that looks up the preset configuration and
        calls install_hook with the appropriate parameters.

        Args:
            preset_name: Name of the hook preset (e.g. "NoClip").
            hook_function_address: For "jmp" presets, the address of the
                detour function.
            offsets: Optional offsets database.

        Returns:
            The installed MemoryHook instance.

        Raises:
            HookPresetNotFoundError: If the preset name doesn't exist.
            HookError: If installation fails.
        """
        preset = get_preset(preset_name)
        hook_data = {
            "offset_key": preset.offset_key,
            "hook_address": hook_function_address,
        }

        if preset.hook_type == "patch" and preset.patch_bytes:
            hook_data["patch_bytes"] = preset.patch_bytes

        if preset.hook_type == "nop":
            hook_data["nop_count"] = 5  # Default NOP count for presets

        return self.install_hook(
            target_name=preset.name,
            hook_type=preset.hook_type,
            hook_data=hook_data,
            offsets=offsets,
        )

    def get_hook(self, target_name: str) -> Optional[MemoryHook]:
        """
        Get a MemoryHook instance by name.

        Args:
            target_name: Name of the hook.

        Returns:
            The MemoryHook instance, or None if not found.
        """
        with self._lock:
            return self._hooks.get(target_name)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the HookManager state to a dictionary.

        Returns:
            Dictionary with manager metadata and installed hook info.
        """
        return {
            "is_loaded": self._is_loaded,
            "is_64bit": self._is_64bit,
            "base_address": f"0x{self.base_address:X}",
            "process_handle": self.process_handle,
            "installed_count": len(self._hooks),
            "hooks": self.get_installed_hooks(),
            "available_presets": get_presets_summary(),
        }

    def __repr__(self) -> str:
        return (
            f"HookManager(loaded={self._is_loaded}, "
            f"base=0x{self.base_address:X}, "
            f"hooks={len(self._hooks)}, "
            f"arch={'x64' if self._is_64bit else 'x86'})"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def quick_nop_patch(handle: int, address: int, count: int = 5) -> bytes:
    """
    Quick utility: overwrite `count` bytes at `address` with NOPs.

    This is a one-shot function that doesn't create a MemoryHook — the
    caller is responsible for saving and restoring original bytes.

    Args:
        handle: Process handle.
        address: Target memory address.
        count: Number of NOP bytes to write.

    Returns:
        The original bytes that were overwritten.
    """
    original = _read_process_memory(handle, address, count)
    nop_bytes = _build_nop_sled(count)

    old_protect = _virtual_protect(handle, address, count, PAGE_EXECUTE_READWRITE)
    try:
        _write_process_memory(handle, address, nop_bytes)
        _flush_instruction_cache(handle, address, count)
    finally:
        _virtual_protect(handle, address, count, old_protect)

    return original


def quick_ret_patch(handle: int, address: int) -> bytes:
    """
    Quick utility: overwrite the byte at `address` with RET (0xC3).

    One-shot function — caller manages original byte backup.

    Args:
        handle: Process handle.
        address: Target memory address.

    Returns:
        The original byte that was overwritten.
    """
    original = _read_process_memory(handle, address, 1)
    ret_bytes = bytes([OP_RET])

    old_protect = _virtual_protect(handle, address, 1, PAGE_EXECUTE_READWRITE)
    try:
        _write_process_memory(handle, address, ret_bytes)
        _flush_instruction_cache(handle, address, 1)
    finally:
        _virtual_protect(handle, address, 1, old_protect)

    return original


def quick_bytes_patch(handle: int, address: int, patch_bytes: bytes) -> bytes:
    """
    Quick utility: write arbitrary bytes at `address`.

    One-shot function — caller manages original byte backup.

    Args:
        handle: Process handle.
        address: Target memory address.
        patch_bytes: Bytes to write.

    Returns:
        The original bytes that were overwritten.
    """
    size = len(patch_bytes)
    original = _read_process_memory(handle, address, size)

    old_protect = _virtual_protect(handle, address, size, PAGE_EXECUTE_READWRITE)
    try:
        _write_process_memory(handle, address, patch_bytes)
        _flush_instruction_cache(handle, address, size)
    finally:
        _virtual_protect(handle, address, size, old_protect)

    return original


def create_hook_manager_from_client(client) -> HookManager:
    """
    Create a HookManager from a RobloxGameClient instance.

    Extracts the process handle and base address from the client object
    and initializes a ready-to-use HookManager.

    Args:
        client: A RobloxGameClient instance from the robloxmemoryapi library.

    Returns:
        An initialized HookManager instance.

    Raises:
        HookError: If the client doesn't have the required attributes.
    """
    if not hasattr(client, "process"):
        raise HookError("Client has no 'process' attribute")
    if not hasattr(client, "base"):
        raise HookError("Client has no 'base' attribute")

    process_handle = 0
    base_address = client.base

    # Try to get the process handle from the memory module
    if hasattr(client.process, "handle"):
        process_handle = client.process.handle
    elif hasattr(client.process, "hProcess"):
        process_handle = client.process.hProcess
    elif hasattr(client.process, "_handle"):
        process_handle = client.process._handle

    if not process_handle:
        raise HookError("Could not extract process handle from client")

    return HookManager(process_handle, base_address)


# ═══════════════════════════════════════════════════════════════════════════
#  MODULE SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════

def _self_test() -> bool:
    """
    Run basic self-tests on the assembler and preset system.

    Tests:
        1. Assembler produces correct bytes for common instructions.
        2. All 40 presets are defined and accessible.
        3. Preset categories are correct.
        4. FFlag preset structure is valid.

    Returns:
        True if all tests pass, False otherwise.
    """
    passed = 0
    failed = 0

    def check(name: str, condition: bool):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    print("Hook Manager self-test:")
    print("-" * 50)

    # Test 1: NOP assembly
    nop_result = assemble("NOP")
    check("NOP assembles to 0x90", nop_result == b"\x90")

    nop_5 = assemble("NOP 5")
    check("NOP 5 assembles to 5x 0x90", nop_5 == b"\x90" * 5)

    # Test 2: RET assembly
    ret_result = assemble("RET")
    check("RET assembles to 0xC3", ret_result == b"\xC3")

    # Test 3: INT3 assembly
    int3_result = assemble("INT3")
    check("INT3 assembles to 0xCC", int3_result == b"\xCC")

    # Test 4: MOV EAX, imm32
    mov_result = assemble("MOV EAX, 0x12345678")
    check(
        "MOV EAX, 0x12345678",
        mov_result == b"\xB8\x78\x56\x34\x12",
    )

    # Test 5: MOV ECX, 0
    mov_ecx_result = assemble("MOV ECX, 0")
    check(
        "MOV ECX, 0",
        mov_ecx_result == b"\xB9\x00\x00\x00\x00",
    )

    # Test 6: XOR EAX, EAX
    xor_result = assemble("XOR EAX, EAX")
    check("XOR EAX, EAX", xor_result == b"\x31\xC0")

    # Test 7: PUSH/POP
    push_result = assemble("PUSH EBP")
    check("PUSH EBP", push_result == b"\x55")

    pop_result = assemble("POP EBP")
    check("POP EBP", pop_result == b"\x5D")

    # Test 8: Multi-line assembly
    multi = assemble("""
        PUSH EBP
        MOV EBP, ESP
        XOR EAX, EAX
        POP EBP
        RET
    """)
    check(
        "Multi-line assembly (prologue + RET)",
        multi == b"\x55\x89\xE5\x31\xC0\x5D\xC3",
    )

    # Test 9: Comments and labels
    commented = assemble("""
        ; This is a comment
        # This is also a comment
        NOP
        my_label:
        RET
    """)
    check("Comments and labels are skipped", commented == b"\x90\xC3")

    # Test 10: Preset count
    check(f"Total presets = {len(HOOK_PRESETS)} (expected 40)",
          len(HOOK_PRESETS) == 40)

    # Test 11: Preset categories
    categories = get_all_categories()
    expected_cats = ["Anti-Cheat", "Movement", "Network", "Performance", "Utility", "Visual"]
    check("All expected categories present", set(categories) == set(expected_cats))

    # Test 12: Category sizes
    check("Anti-Cheat has 8 presets", len(get_presets_by_category("Anti-Cheat")) == 8)
    check("Performance has 6 presets", len(get_presets_by_category("Performance")) == 6)
    check("Movement has 6 presets", len(get_presets_by_category("Movement")) == 6)
    check("Visual has 6 presets", len(get_presets_by_category("Visual")) == 6)
    check("Utility has 8 presets", len(get_presets_by_category("Utility")) == 8)
    check("Network has 6 presets", len(get_presets_by_category("Network")) == 6)

    # Test 13: Preset lookup
    noclip = get_preset("NoClip")
    check("NoClip preset found", noclip is not None)
    check("NoClip category is Movement", noclip.category == "Movement")
    check("NoClip type is nop", noclip.hook_type == "nop")

    # Test 14: Preset to_dict
    d = noclip.to_dict()
    check("Preset serializes with correct keys",
          all(k in d for k in ("name", "description", "offset_key", "type",
                                "default_action", "category")))

    # Test 15: Preset summary
    summary = get_presets_summary()
    check("Summary has 'total' key", "total" in summary)
    check("Summary total = 40", summary["total"] == 40)
    check("Summary has all categories", len(summary["categories"]) == 6)

    # Test 16: FFlag presets structure
    check("FFlag presets have 4 categories", len(FFLAG_PRESETS) == 4)
    for cat_name, flags in FFLAG_PRESETS.items():
        for flag in flags:
            check(
                f"FFlag '{flag['name']}' has required keys",
                all(k in flag for k in ("name", "default", "value")),
            )

    # Test 17: FFlagManager basics
    fm = FFlagManager()
    fm.load_flags({"FFlagTest1": "False", "FFlagTest2": "60"})
    check("FFlag get returns correct value", fm.get_flag("FFlagTest1") == "False")
    fm.set_flag("FFlagTest1", "True")
    check("FFlag set updates value", fm.get_flag("FFlagTest1") == "True")
    reset_count = fm.reset_all()
    check("FFlag reset_all returns count", reset_count == 1)
    check("FFlag reset restores original", fm.get_flag("FFlagTest1") == "False")

    # Test 18: HookManager creation (dry run)
    dry_mgr = HookManager(0, 0)
    check("Dry-run HookManager is not loaded", not dry_mgr.is_loaded)
    check("Dry-run has no hooks", len(dry_mgr.get_installed_hooks()) == 0)

    # Test 19: assemble_hex
    hex_result = assemble_hex("90 90 C3")
    check("assemble_hex works", hex_result == b"\x90\x90\xC3")

    # Test 20: JMP building
    jmp = _build_jmp_x86(0x1000, 0x2000)
    check("JMP x86 is 5 bytes", len(jmp) == 5)
    check("JMP x86 starts with 0xE9", jmp[0] == 0xE9)

    jmp64 = _build_jmp_x64(0x100000, 0x200000)
    check("JMP x64 is 14 bytes", len(jmp64) == 14)
    check("JMP x64 starts with FF 25 00", jmp64[:3] == b"\xFF\x25\x00")

    # Summary
    print("-" * 50)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    return failed == 0


# ═══════════════════════════════════════════════════════════════════════════
#  MODULE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Run self-tests
    success = _self_test()
    exit(0 if success else 1)
