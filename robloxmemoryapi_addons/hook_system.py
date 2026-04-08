"""
Hook System Module — Система inline-хуков для Roblox процесса

Позволяет:
  - Устанавливать JMP/CALL хуки на произвольные адреса
  - NOP-ить функции (отключать)
  - Патчить отдельные байты
  - Выделять RWX память для shellcode
  - Строить x86-64 shellcode (JMP, CALL, RET, PUSH, MOV RCX, MOV RDX, INT3, NOP)
  - Логировать все действия

Принцип:
  EvasiveProcess (RobloxMemoryAPI) использует NT syscalls для чтения/записи
  памяти Roblox. Этот модуль расширяет возможности, позволяя перехватывать
  функции через inline-патчинг (JMP redirect) и записывать shellcode.

Usage:
    from robloxmemoryapi import RobloxGameClient
    from robloxmemoryapi_addons.hook_system import HookManager

    client = RobloxGameClient()
    hm = HookManager(client.memory_module)

    # Выделить память и написать shellcode
    sc_addr = hm.allocate(1024)
    hm.write_shellcode(sc_addr, b'\\xC3')  # RET

    # Установить JMP хук
    hm.install(target_addr=0xdeadbeef, detour_addr=sc_addr)

    # Удалить хук
    hm.uninstall(0xdeadbeef)

    # NOP-ить функцию
    hm.nop_function(0xcafebabe, num_bytes=14)

    # Очистить всё
    hm.cleanup()
"""

import struct
import time
import threading


# ──────────────────────────────────────────────────────────────
# Размеры хуков
# ──────────────────────────────────────────────────────────────

JMP_HOOK_SIZE = 14      # FF 25 00 00 00 00 + 8-byte address
CALL_HOOK_SIZE = 12     # FF 15 02 00 00 00 EB 08 + 8-byte address
NOP_HOOK_MIN = 14       # Минимум байт для NOP (JMP placeholder)

# ──────────────────────────────────────────────────────────────
# Оффсеты для готовых пресетов
# ──────────────────────────────────────────────────────────────

# Updated: 02/04/2026 — version-689e359b09ad43b0 (imtheo.lol)
FAKEDATAMODEL_POINTER = 0x834a988
FAKEDATAMODEL_TO_REAL = 0x1c0

SCRIPT_CONTEXT_OFFSET = 0x3F0
REQUIRE_BYPASS_OFFSET = 0x861

TASK_SCHEDULER_POINTER = 0x8428188
TASK_SCHEDULER_MAX_FPS = 0xB0

WORKSPACE_OFFSET = 0x178
WORLD_OFFSET = 0x400
WORLD_GRAVITY = 0x1D8


# ══════════════════════════════════════════════════════════════
# HookLogger
# ══════════════════════════════════════════════════════════════

class HookLogger:
    """
    Простой потокобезопасный логгер событий хуков.

    Записывает каждое действие (install, uninstall, patch, и т.д.)
    с таймстемпом, адресом и деталями.

    Usage:
        logger = HookLogger()
        logger.log("install", 0x1234, "JMP → 0x5678")
        for entry in logger.get_entries(50):
            print(entry)
    """

    def __init__(self, max_entries: int = 1000):
        self._entries = []
        self._max = max_entries
        self._lock = threading.Lock()

    def log(self, event_type: str, addr: int, details: str = ""):
        """
        Записать событие в лог.

        Args:
            event_type: тип события ("install", "uninstall", "patch", "nop", "error")
            addr: адрес связанный с событием
            details: дополнительное описание
        """
        with self._lock:
            self._entries.append({
                "time": time.time(),
                "type": event_type,
                "addr": addr,
                "details": details,
            })
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max:]

    def get_entries(self, limit: int = 100) -> list:
        """
        Получить последние N записей из лога.

        Returns:
            список словарей {"time", "type", "addr", "details"}
        """
        with self._lock:
            return list(self._entries[-limit:])

    def clear(self):
        """Очистить лог."""
        with self._lock:
            self._entries.clear()

    @property
    def count(self) -> int:
        """Количество записей в логе."""
        with self._lock:
            return len(self._entries)


# ══════════════════════════════════════════════════════════════
# Shellcode Builders (staticmethods)
# ══════════════════════════════════════════════════════════════

class Shellcode:
    """
    Набор статических методов для построения x86-64 shellcode.

    Все методы возвращают bytes. Каждый_instruction — это
    правильная x86-64 кодировка которую можно записать в память.

    Инструкции:
      build_jmp_abs(addr)    → 14 байт: FF 25 00 00 00 00 + addr (LE)
      build_call_abs(addr)   → 12 байт: FF 15 02 00 00 00 EB 08 + addr (LE)
      build_ret()            → 1 байт:  C3
      build_int3()           → 1 байт:  CC
      build_nop_sled(n)      → n байт:  90 * n
      build_push(value)      → 5 байт:  68 + value (LE32)
      build_mov_rcx(value)   → 10 байт: 48 B9 + value (LE64)
      build_mov_rdx(value)   → 10 байт: 48 BA + value (LE64)
    """

    @staticmethod
    def build_jmp_abs(addr: int) -> bytes:
        """
        Абсолютный JMP (14 байт).

        Кодировка: FF 25 00 00 00 00 [addr:8]
        Использует RIP-relative indirect jump:
          jmp QWORD PTR [rip+0x0]  → прыгает на addr
        """
        return b'\xFF\x25\x00\x00\x00\x00' + struct.pack('<Q', addr)

    @staticmethod
    def build_call_abs(addr: int) -> bytes:
        """
        Абсолютный CALL через trampoline (12 байт).

        Кодировка: FF 15 02 00 00 00 EB 08 [addr:8]
        call QWORD PTR [rip+0x2]  → вызывает addr
        jmp +8                     → прыгает через addr (возврат)
        """
        return b'\xFF\x15\x02\x00\x00\x00\xEB\x08' + struct.pack('<Q', addr)

    @staticmethod
    def build_ret() -> bytes:
        """RET — возврат из функции (1 байт)."""
        return b'\xC3'

    @staticmethod
    def build_int3() -> bytes:
        """INT3 — breakpoint/остановка (1 байт)."""
        return b'\xCC'

    @staticmethod
    def build_nop_sled(count: int) -> bytes:
        """
        NOP sled — последовательность из N NOP инструкций.

        Args:
            count: количество NOP (1+)
        """
        count = max(1, int(count))
        return b'\x90' * count

    @staticmethod
    def build_push(value: int) -> bytes:
        """
        PUSH imm32 (5 байт).

        Args:
            value: 32-битное значение для push на стек
        """
        return b'\x68' + struct.pack('<I', value & 0xFFFFFFFF)

    @staticmethod
    def build_mov_rcx(value: int) -> bytes:
        """
        MOV RCX, imm64 (10 байт).

        Args:
            value: 64-битное значение
        """
        return b'\x48\xB9' + struct.pack('<Q', value)

    @staticmethod
    def build_mov_rdx(value: int) -> bytes:
        """
        MOV RDX, imm64 (10 байт).

        Args:
            value: 64-битное значение
        """
        return b'\x48\xBA' + struct.pack('<Q', value)

    @staticmethod
    def build_sub_rsp(value: int) -> bytes:
        """
        SUB RSP, imm8 (4 байт) или SUB RSP, imm32 (7 байт).

        Args:
            value: сколько байт отнять от RSP
        """
        if value <= 127:
            return b'\x48\x83\xEC' + struct.pack('<B', value)
        else:
            return b'\x48\x81\xEC' + struct.pack('<I', value)

    @staticmethod
    def build_add_rsp(value: int) -> bytes:
        """
        ADD RSP, imm8 (4 байт) или ADD RSP, imm32 (7 байт).

        Args:
            value: сколько байт добавить к RSP
        """
        if value <= 127:
            return b'\x48\x83\xC4' + struct.pack('<B', value)
        else:
            return b'\x48\x81\xC4' + struct.pack('<I', value)


# ══════════════════════════════════════════════════════════════
# HookManager
# ══════════════════════════════════════════════════════════════

class HookManager:
    """
    Менеджер inline-хуков для Roblox процесса.

    Позволяет перехватывать функции в Roblox через inline-патчинг.
    Работает поверх EvasiveProcess из RobloxMemoryAPI.

    Поддерживаемые типы хуков:
      - JMP (absolute): перенаправляет выполнение на detour адрес
      - CALL (absolute): вызывает detour и продолжает оригинальную функцию
      - NOP: отключает функцию (заполняет NOP)
      - PATCH: патчит один байт (с сохранением оригинала)

    Usage:
        hm = HookManager(memory_module)

        # 1. Выделить память для shellcode
        shellcode_addr = hm.allocate(256)

        # 2. Записать shellcode (например RET)
        hm.write_shellcode(shellcode_addr, Shellcode.build_ret())

        # 3. Установить хук
        hm.install(target_addr, shellcode_addr)

        # 4. Когда нужно — удалить
        hm.uninstall(target_addr)

        # 5. Или всё разом
        hm.cleanup()  # удалит все хуки и освободит память
    """

    def __info__(self):
        """Мета-информация о менеджере."""
        return "HookManager v1.0 — inline hooks + shellcode for RobloxMemoryAPI"

    def __init__(self, memory_module):
        """
        Args:
            memory_module: EvasiveProcess из RobloxMemoryAPI
                          (объект с методами read/write/virtual_alloc/base)
        """
        self.mem = memory_module
        self.base = memory_module.base

        # Трекинг установленных хуков: {target_addr: {"original": bytes, "size": int, "type": str, "detour": int}}
        self._hooks = {}
        self._hooks_lock = threading.Lock()

        # Трекинг аллокаций: {addr: size}
        self._allocations = {}
        self._alloc_lock = threading.Lock()

        # Логгер
        self.logger = HookLogger()

    # ── Аллокация памяти ─────────────────────────────────────

    def allocate(self, size: int) -> int:
        """
        Выделить RWX (Read-Write-Execute) страницу в процессе Roblox.

        Args:
            size: размер в байтах (округляется до PAGE_SIZE)

        Returns:
            адрес выделенной памяти, или 0 при ошибке
        """
        try:
            addr = self.mem.virtual_alloc(0, size)
            if addr and addr != 0:
                with self._alloc_lock:
                    self._allocations[addr] = size
                self.logger.log("alloc", addr, f"allocated {size} bytes")
            return addr if addr else 0
        except Exception as e:
            self.logger.log("error", 0, f"alloc failed: {e}")
            return 0

    def free(self, addr: int):
        """
        Освободить ранее выделенную память.
        (EvasiveProcess может не поддерживать free — тогда просто удаляем из трекинга)
        """
        with self._alloc_lock:
            if addr in self._allocations:
                del self._allocations[addr]
        self.logger.log("free", addr, "memory freed from tracking")

    # ── Чтение / Запись ──────────────────────────────────────

    def read_at(self, addr: int, size: int) -> bytes:
        """Прочитать байты по адресу."""
        try:
            return self.mem.read(addr, size)
        except Exception as e:
            self.logger.log("error", addr, f"read failed: {e}")
            return b''

    def write_at(self, addr: int, data: bytes) -> bool:
        """Записать байты по адресу."""
        try:
            self.mem.write(addr, data)
            return True
        except Exception as e:
            self.logger.log("error", addr, f"write failed: {e}")
            return False

    def write_shellcode(self, addr: int, shellcode: bytes) -> bool:
        """
        Записать shellcode по адресу.
        Обычно используется вместе с allocate().
        """
        return self.write_at(addr, shellcode)

    def nop(self, addr: int, count: int):
        """Записать NOP sled (count байт) по адресу."""
        self.write_at(addr, b'\x90' * max(1, count))

    # ── Установка хуков ──────────────────────────────────────

    def install(self, target_addr: int, detour_addr: int, restore_size: int = 14):
        """
        Установить JMP хук на функцию.

        Записывает 14-байтовый абсолютный JMP по адресу target_addr,
        который перенаправляет выполнение на detour_addr.
        Оригинальные байты сохраняются для восстановления.

        Args:
            target_addr: адрес начала функции (где ставим хук)
            detour_addr: адрес куда перенаправляем (shellcode)
            restore_size: сколько байт сохранить (минимум 14)

        Returns:
            True при успехе
        """
        try:
            with self._hooks_lock:
                if target_addr in self._hooks:
                    self.logger.log("error", target_addr, "hook already exists")
                    return False

                # Читаем оригинальные байты
                original = self.mem.read(target_addr, restore_size)

                # Пишем JMP хук
                jmp_code = Shellcode.build_jmp_abs(detour_addr)
                self.mem.write(target_addr, jmp_code)

                # Сохраняем в трекинг
                self._hooks[target_addr] = {
                    "original": original,
                    "size": restore_size,
                    "type": "jmp",
                    "detour": detour_addr,
                }

                self.logger.log("install", target_addr,
                    f"JMP → 0x{detour_addr:X} ({restore_size} bytes saved)")
                return True

        except Exception as e:
            self.logger.log("error", target_addr, f"install jmp failed: {e}")
            return False

    def install_call_hook(self, target_addr: int, detour_addr: int, restore_size: int = 12):
        """
        Установить CALL хук на функцию.

        В отличие от JMP, CALL вызывает detour и продолжает
        выполнение оригинальной функции после возврата.

        Args:
            target_addr: адрес начала функции
            detour_addr: адрес callable shellcode
            restore_size: сколько байт сохранить (минимум 12)

        Returns:
            True при успехе
        """
        try:
            with self._hooks_lock:
                if target_addr in self._hooks:
                    return False

                original = self.mem.read(target_addr, restore_size)
                call_code = Shellcode.build_call_abs(detour_addr)
                self.mem.write(target_addr, call_code)

                self._hooks[target_addr] = {
                    "original": original,
                    "size": restore_size,
                    "type": "call",
                    "detour": detour_addr,
                }

                self.logger.log("install", target_addr,
                    f"CALL → 0x{detour_addr:X} ({restore_size} bytes saved)")
                return True

        except Exception as e:
            self.logger.log("error", target_addr, f"install call failed: {e}")
            return False

    def uninstall(self, target_addr: int) -> bool:
        """
        Удалить хук и восстановить оригинальные байты.

        Args:
            target_addr: адрес функции с хуком

        Returns:
            True если хук был найден и удалён
        """
        try:
            with self._hooks_lock:
                info = self._hooks.pop(target_addr, None)
                if info is None:
                    return False

                # Восстанавливаем оригинальные байты
                self.mem.write(target_addr, info["original"])

                self.logger.log("uninstall", target_addr,
                    f"restored {len(info['original'])} bytes ({info['type']})")
                return True

        except Exception as e:
            # Если запись не удалась — возвращаем хук в трекинг
            self.logger.log("error", target_addr, f"uninstall failed: {e}")
            with self._hooks_lock:
                self._hooks[target_addr] = info  # noqa: possibly unbound
            return False

    def uninstall_all(self):
        """Удалить все установленные хуки (оставить аллокации)."""
        with self._hooks_lock:
            addrs = list(self._hooks.keys())
        for addr in addrs:
            self.uninstall(addr)

    # ── Шаблоны хуков ────────────────────────────────────────

    def nop_function(self, addr: int, num_bytes: int = 14):
        """
        NOP-нуть функцию (отключить).

        Заполняет первые num_bytes NOP инструкциями (0x90).
        Оригинальные байты сохраняются для восстановления.

        Args:
            addr: адрес начала функции
            num_bytes: сколько байт NOP-ить (по умолчанию 14 = JMP_HOOK_SIZE)
        """
        try:
            with self._hooks_lock:
                if addr in self._hooks:
                    return

                original = self.mem.read(addr, num_bytes)
                self.mem.write(addr, b'\x90' * num_bytes)

                self._hooks[addr] = {
                    "original": original,
                    "size": num_bytes,
                    "type": "nop",
                    "detour": 0,
                }

                self.logger.log("nop", addr, f"NOP'd {num_bytes} bytes")
        except Exception as e:
            self.logger.log("error", addr, f"nop failed: {e}")

    def patch_byte(self, addr: int, new_byte: int, original_byte: int = None):
        """
        Патчить один байт по адресу.

        Args:
            addr: адрес байта
            new_byte: новое значение (0-255)
            original_byte: оригинальное значение (если None — прочитает автоматически)
        """
        try:
            with self._hooks_lock:
                if original_byte is None:
                    original_byte = self.mem.read_int(addr) & 0xFF

                self.mem.write_int(addr, new_byte)

                self._hooks[addr] = {
                    "original": bytes([original_byte]),
                    "size": 1,
                    "type": "patch",
                    "detour": 0,
                }

                self.logger.log("patch", addr,
                    f"byte 0x{original_byte:02X} → 0x{new_byte:02X}")
        except Exception as e:
            self.logger.log("error", addr, f"patch failed: {e}")

    def patch_dword(self, addr: int, new_value: int):
        """
        Патчить 4 байта (DWORD) по адресу.

        Args:
            addr: адрес
            new_value: новое 32-битное значение
        """
        try:
            with self._hooks_lock:
                if addr in self._hooks:
                    return

                original = self.mem.read(addr, 4)
                self.mem.write_int(addr, new_value)

                self._hooks[addr] = {
                    "original": original,
                    "size": 4,
                    "type": "patch_dword",
                    "detour": 0,
                }

                self.logger.log("patch", addr,
                    f"dword → 0x{new_value:08X}")
        except Exception as e:
            self.logger.log("error", addr, f"patch dword failed: {e}")

    # ── Состояние ─────────────────────────────────────────────

    def is_hooked(self, target_addr: int) -> bool:
        """Проверить, установлен ли хук по адресу."""
        with self._hooks_lock:
            return target_addr in self._hooks

    def get_hooks(self) -> dict:
        """Получить копию словаря всех установленных хуков."""
        with self._hooks_lock:
            return dict(self._hooks)

    @property
    def hook_count(self) -> int:
        """Количество установленных хуков."""
        with self._hooks_lock:
            return len(self._hooks)

    @property
    def allocation_count(self) -> int:
        """Количество активных аллокаций."""
        with self._alloc_lock:
            return len(self._allocations)

    def get_allocations(self) -> dict:
        """Получить копию словаря аллокаций."""
        with self._alloc_lock:
            return dict(self._allocations)

    # ── Очистка ───────────────────────────────────────────────

    def cleanup(self):
        """
        Полная очистка: удалить все хуки + освободить все аллокации.

        Вызывать при закрытии приложения!
        """
        self.uninstall_all()

        with self._alloc_lock:
            freed = len(self._allocations)
            self._allocations.clear()

        self.logger.log("cleanup", 0,
            f"hooks cleared, {freed} allocations released")

    # ── Готовые пресеты (быстрый доступ к частым операциям) ──

    def preset_require_bypass(self, enabled: bool) -> bool:
        """
        Быстрый пресет: переключить RequireBypass через прямую запись.

        Args:
            enabled: True = включить, False = выключить

        Returns:
            True при успехе
        """
        try:
            fake_dm_ptr = self.base + FAKEDATAMODEL_POINTER
            fake_dm_addr = self.mem.get_pointer(fake_dm_ptr)
            if fake_dm_addr == 0:
                return False
            dm_addr = self.mem.get_pointer(fake_dm_addr + FAKEDATAMODEL_TO_REAL)
            if dm_addr == 0:
                return False
            sc_addr = self.mem.get_pointer(dm_addr + SCRIPT_CONTEXT_OFFSET)
            if sc_addr == 0:
                return False

            self.mem.write_bool(sc_addr + REQUIRE_BYPASS_OFFSET, enabled)
            state = "ON" if enabled else "OFF"
            self.logger.log("preset", sc_addr, f"RequireBypass → {state}")
            return True
        except Exception as e:
            self.logger.log("error", 0, f"require_bypass preset: {e}")
            return False

    def preset_max_fps(self, fps: float) -> bool:
        """
        Быстрый пресет: установить MaxFPS.

        Args:
            fps: значение FPS (999 = снять лимит)

        Returns:
            True при успехе
        """
        try:
            ts_ptr = self.base + TASK_SCHEDULER_POINTER
            ts_addr = self.mem.get_pointer(ts_ptr)
            if ts_addr == 0:
                return False
            self.mem.write_float(ts_addr + TASK_SCHEDULER_MAX_FPS, float(fps))
            self.logger.log("preset", ts_addr, f"MaxFPS → {fps}")
            return True
        except Exception as e:
            self.logger.log("error", 0, f"max_fps preset: {e}")
            return False

    def preset_gravity(self, gravity: float) -> bool:
        """
        Быстрый пресет: изменить гравитацию.

        Args:
            gravity: значение (196.2 = default, 0 = невесомость)

        Returns:
            True при успехе
        """
        try:
            fake_dm_ptr = self.base + FAKEDATAMODEL_POINTER
            fake_dm_addr = self.mem.get_pointer(fake_dm_ptr)
            if fake_dm_addr == 0:
                return False
            dm_addr = self.mem.get_pointer(fake_dm_addr + FAKEDATAMODEL_TO_REAL)
            if dm_addr == 0:
                return False
            ws_addr = self.mem.get_pointer(dm_addr + WORKSPACE_OFFSET)
            if ws_addr == 0:
                return False
            world_addr = self.mem.get_pointer(ws_addr + WORLD_OFFSET)
            if world_addr == 0:
                return False

            self.mem.write_float(world_addr + WORLD_GRAVITY, float(gravity))
            self.logger.log("preset", world_addr, f"Gravity → {gravity}")
            return True
        except Exception as e:
            self.logger.log("error", 0, f"gravity preset: {e}")
            return False

    def __repr__(self):
        return (f"HookManager(base=0x{self.base:X}, "
                f"hooks={self.hook_count}, "
                f"allocs={self.allocation_count})")
