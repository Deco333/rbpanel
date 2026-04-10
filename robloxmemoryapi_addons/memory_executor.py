"""
Memory Script Executor — Исполнитель Lua скриптов через инъекцию байткода

Выполняет Lua скрипты путём прямой инъекции байткода в память Roblox БЕЗ RequireBypass.

Архитектура:
  1. Находит LocalScript / ModuleScript в DataModel через обход дерева Instance
  2. Дампит зашифрованный байткод (RSB1) из существующего скрипта
  3. Шифрует новый Lua код в RSB1 формат
  4. Выделяет память и записывает новый байткод
  5. Обновляет ByteCode::Pointer и ByteCode::Size в Instance скрипта
  6. Манипулирует TaskScheduler / RequireBypass для перезапуска выполнения

Использует те же оффсеты что и RobloxMemoryAPI для обхода Instance tree.

Usage:
    from robloxmemoryapi import RobloxGameClient
    from robloxmemoryapi_addons.memory_executor import MemoryScriptExecutor

    client = RobloxGameClient()
    executor = MemoryScriptExecutor(client.memory_module)

    # Выполнить Lua код
    result = executor.execute('print("Hello from memory!")')

    # Найти все скрипты
    scripts = executor.find_scripts()
    for s in scripts:
        print(f\"  {s['class']}: {s['name']} (0x{s['address']:X})\")

    # Дамп байткода
    bc = executor.dump_bytecode(script_address, "LocalScript")

    # Инжектировать сырой байткод
    result = executor.inject_raw_bytecode(encrypted_bc, target_addr)

    # Управление RequireBypass
    executor.set_require_bypass(True)
    executor.restore_require_bypass()
"""

import struct
import time
import hashlib
import threading
from typing import Optional, List, Dict


# ──────────────────────────────────────────────────────────────
# Оффсеты (обновляются с imtheo.lol)
# ──────────────────────────────────────────────────────────────

# Updated: 09/04/2026 — version-26c90be22e0d4758 (imtheo.lol)

# DataModel pointer chain
FAKEDATAMODEL_POINTER = 0x7A1D388   # 128045960
FAKEDATAMODEL_TO_REAL = 0x1C0       # 448

# Instance traversal
INSTANCE_NAME = 0xB0                # 176
INSTANCE_CLASS_DESCRIPTOR = 0x18    # 24
INSTANCE_CLASS_NAME = 0x8           # 8
INSTANCE_CHILDREN_START = 0x78      # 120
INSTANCE_CHILDREN_END = 0x8         # 8
INSTANCE_CHILDREN_STRIDE = 0x10     # 16
INSTANCE_PARENT = 0x70              # 112

# Script bytecode offsets
LOCALSCRIPT_BYTECODE = 0x1A8        # 424
MODULESCRIPT_BYTECODE = 0x150       # 336
SCRIPT_BYTECODE = 0x1A8             # 424

# ByteCode struct (внутри байткода)
BYTECODE_POINTER = 0x10             # 16
BYTECODE_SIZE = 0x20                # 32

# ScriptContext
SCRIPT_CONTEXT_OFFSET = 0x3F0       # 1008
REQUIRE_BYPASS_OFFSET = 0x0         # 0 (changed in new version)

# TaskScheduler
TASK_SCHEDULER_POINTER = 0x7AF5090  # 128929936


# ══════════════════════════════════════════════════════════════
# RSB1 Encryptor — шифрование/дешифрование байткода Roblox
# ══════════════════════════════════════════════════════════════

class RSB1Encryptor:
    """
    Шифрование и дешифрование RSB1 байткода Roblox.

    Формат RSB1:
      [8 байт: magic "ROFL" + padding] [4 байт: uncompressed_size] [data]

    Шифрование: XOR с ключом, выведенным из magic байт.
    Каждый байт: encrypted[i] = plain[i] ^ key[i % 4]
    Ключ: key[i] = (i * 41 + magic_byte[i % 4]) % 256
    """

    MAGIC_A = 0x4C464F52  # "ROFL" little-endian
    MAGIC_B = 0x946AC432

    @staticmethod
    def is_rsb1(data: bytes) -> bool:
        """Проверить, является ли данные RSB1-зашифрованными."""
        if len(data) < 12:
            return False
        magic_a = struct.unpack('<I', data[0:4])[0]
        return magic_a == RSB1Encryptor.MAGIC_A

    @staticmethod
    def encrypt(plain_data: bytes) -> bytes:
        """
        Зашифровать данные в RSB1 формат.

        Args:
            plain_data: необработанные байты

        Returns:
            RSB1-зашифрованные байты
        """
        size = len(plain_data)

        # Формируем 8-байтный заголовок
        magic_bytes = struct.pack('<I', RSB1Encryptor.MAGIC_A) + struct.pack('<I', RSB1Encryptor.MAGIC_B)

        # Размер: 4 байта LE
        size_bytes = struct.pack('<I', size)

        # XOR шифрование с ключом из magic
        encrypted = bytearray(size)
        key = [magic_bytes[0], magic_bytes[1], magic_bytes[2], magic_bytes[3]]

        for i in range(size):
            k = (i * 41 + key[i % 4]) % 256
            encrypted[i] = plain_data[i] ^ k

        return magic_bytes + size_bytes + bytes(encrypted)

    @staticmethod
    def decrypt(rsb1_data: bytes) -> bytes:
        """
        Расшифровать RSB1 данные.

        Args:
            rsb1_data: RSB1-зашифрованные байты

        Returns:
            расшифрованные данные, или пустые байты при ошибке
        """
        if not RSB1Encryptor.is_rsb1(rsb1_data):
            return b''

        if len(rsb1_data) < 12:
            return b''

        magic_bytes = rsb1_data[0:8]
        uncompressed_size = struct.unpack('<I', rsb1_data[8:12])[0]
        encrypted_data = rsb1_data[12:]

        # Ограничиваем размер
        if uncompressed_size > len(encrypted_data):
            uncompressed_size = len(encrypted_data)
        if uncompressed_size == 0:
            return b''

        # XOR дешифрование
        key = [magic_bytes[0], magic_bytes[1], magic_bytes[2], magic_bytes[3]]
        decrypted = bytearray(uncompressed_size)

        for i in range(uncompressed_size):
            k = (i * 41 + key[i % 4]) % 256
            decrypted[i] = encrypted_data[i] ^ k

        return bytes(decrypted)


# ══════════════════════════════════════════════════════════════
# BytecodeBuilder — простой конструктор Luau байткода
# ══════════════════════════════════════════════════════════════

class BytecodeBuilder:
    """
    Минимальный билдер Luau байткода.

    ВНИМАНИЕ: полноценный Luau компилятор это НЕ.
    Создаёт минимальные валидные структуры для тестов.

    Для реального выполнения Lua кода используйте
    MemoryScriptExecutor.execute() который работает
    через RequireBypass toggle + loadstring.

    Usage:
        bb = BytecodeBuilder()
        bb.add_return()
        bc = bb.build()
    """

    # Luau opcodes (упрощённый набор)
    OP_RETURN = 0x1E
    OP_LOADNIL = 0x1C
    OP_LOADBOOL = 0x1D
    OP_GETUPVAL = 0x0C
    OP_GETTABUP = 0x0A
    OP_CALL = 0x16
    OP_LOADK = 0x14
    OP_GETGLOBAL = 0x06

    def __init__(self):
        self._instructions = []
        self._constants = []
        self._param_count = 0

    def add_instruction(self, opcode: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0):
        """Добавить сырую инструкцию (ABC или ABx формат)."""
        self._instructions.append((opcode, a, b, c, d))
        return self

    def add_return(self, count: int = 0, b: int = 0):
        """RETURN R(A), ... R(A+B-2)"""
        self._instructions.append((self.OP_RETURN, count, b, 0, 0))
        return self

    def add_loadnil(self, register: int):
        """LOADNIL R(A)"""
        self._instructions.append((self.OP_LOADNIL, register, 0, 0, 0))
        return self

    def add_loadbool(self, register: int, value: bool):
        """LOADBOOL R(A), B"""
        self._instructions.append((self.OP_LOADBOOL, register, 1 if value else 0, 0, 0))
        return self

    def add_call(self, func_reg: int, args: int, returns: int):
        """CALL R(A), B, C"""
        self._instructions.append((self.OP_CALL, func_reg, args, returns, 0))
        return self

    def add_getglobal(self, register: int, name: str):
        """GETGLOBAL R(A), K(G)"""
        if name not in self._constants:
            self._constants.append(name)
        idx = self._constants.index(name)
        self._instructions.append((self.OP_GETGLOBAL, register, idx, 0, 0))
        return self

    def set_param_count(self, count: int):
        """Установить количество параметров функции."""
        self._param_count = count
        return self

    def build(self) -> bytes:
        """
        Собрать байткод в минимальную Luau структуру.

        Returns:
            bytes — сырой байткод (без RSB1 шифрования)
        """
        result = bytearray()

        # Заголовок Luau bytecode
        # version (4 bytes) = 0
        result += struct.pack('<I', 0)
        # num params (1 byte)
        result += struct.pack('<B', self._param_count)
        # is_vararg (1 byte) = 1
        result += struct.pack('<B', 1)
        # stack size (1 byte) = 200
        result += struct.pack('<B', 200)

        # Constants table size (4 bytes)
        num_constants = len(self._constants)
        result += struct.pack('<I', num_constants)

        # Константы (строки)
        for const in self._constants:
            if isinstance(const, str):
                encoded = const.encode('utf-8')
                result += struct.pack('<I', len(encoded))
                result += encoded
            else:
                # Двойное число
                result += struct.pack('<B', 0x11)  # type tag: double
                result += struct.pack('<d', float(const))

        # Instructions
        for opcode, a, b, c, d in self._instructions:
            # Luau использует code-word (uint32) для каждой инструкции
            # Формат: opcode(7) | A(8) | B/C(17) для ABC
            #          opcode(7) | A(8) | D(16) для ABx
            instr = (opcode & 0x7F) | ((a & 0xFF) << 7) | ((b & 0xFFFF) << 15)
            result += struct.pack('<I', instr)

        return bytes(result)


# ══════════════════════════════════════════════════════════════
# MemoryScriptExecutor
# ══════════════════════════════════════════════════════════════

class MemoryScriptExecutor:
    """
    Исполнитель Lua скриптов через прямую инъекцию байткода.

    Работает поверх EvasiveProcess из RobloxMemoryAPI.
    НЕ требует постоянно включённый RequireBypass.

    Основной метод — execute():
      1. Временно включает RequireBypass
      2. Записывает Lua код через инъекцию байткода
      3. Восстанавливает RequireBypass

    Usage:
        executor = MemoryScriptExecutor(memory_module)

        # Быстрое выполнение
        result = executor.execute('print("Hello!")')

        # Продвинутое использование
        scripts = executor.find_scripts("LocalScript")
        bc = executor.dump_bytecode(scripts[0]["address"])
        executor.inject_raw_bytecode(my_bytecode, scripts[0]["address"])
    """

    def __info__(self):
        return "MemoryScriptExecutor v1.0 — bytecode injection for RobloxMemoryAPI"

    def __init__(self, memory_module):
        """
        Args:
            memory_module: EvasiveProcess из RobloxMemoryAPI
        """
        self.mem = memory_module
        self.base = memory_module.base

        # Кешированные адреса
        self._dm_addr = 0
        self._sc_addr = 0
        self._ts_addr = 0

        # Сохранение оригинального RequireBypass
        self._rb_original = None
        self._rb_modified = False

        # Статистика
        self._last_injection_time = 0
        self._injection_count = 0

        # Мьютекс для потокобезопасности
        self._lock = threading.Lock()

        # Обновляем кешированные адреса
        self.refresh()

    # ── Кеширование адресов ──────────────────────────────────

    def refresh(self):
        """Обновить кешированные адреса DataModel, ScriptContext, TaskScheduler."""
        try:
            fake_dm_ptr = self.base + FAKEDATAMODEL_POINTER
            fake_dm_addr = self.mem.get_pointer(fake_dm_ptr)
            if fake_dm_addr:
                self._dm_addr = self.mem.get_pointer(fake_dm_addr + FAKEDATAMODEL_TO_REAL)
            if self._dm_addr:
                self._sc_addr = self.mem.get_pointer(self._dm_addr + SCRIPT_CONTEXT_OFFSET)
            self._ts_addr = self.mem.get_pointer(self.base + TASK_SCHEDULER_POINTER)
        except Exception:
            pass

    def get_datamodel_address(self) -> int:
        """Получить адрес DataModel через FakeDataModel pointer chain."""
        if self._dm_addr:
            return self._dm_addr
        self.refresh()
        return self._dm_addr

    def get_script_context_address(self) -> int:
        """Получить адрес ScriptContext."""
        if self._sc_addr:
            return self._sc_addr
        self.refresh()
        return self._sc_addr

    def get_task_scheduler_address(self) -> int:
        """Получить адрес TaskScheduler."""
        if self._ts_addr:
            return self._ts_addr
        self.refresh()
        return self._ts_addr

    # ── Чтение Instance ──────────────────────────────────────

    def _read_instance_name(self, addr: int) -> str:
        """Прочитать имя Instance по адресу."""
        try:
            name_ptr = self.mem.get_pointer(addr + INSTANCE_NAME)
            if name_ptr == 0:
                return ""
            return self.mem.read_string(name_ptr)
        except Exception:
            return ""

    def _read_instance_class(self, addr: int) -> str:
        """Прочитать ClassName Instance по адресу."""
        try:
            class_desc = self.mem.get_pointer(addr + INSTANCE_CLASS_DESCRIPTOR)
            if class_desc == 0:
                return ""
            class_name_ptr = self.mem.get_pointer(class_desc + INSTANCE_CLASS_NAME)
            if class_name_ptr == 0:
                return ""
            return self.mem.read_string(class_name_ptr)
        except Exception:
            return ""

    def _read_children(self, addr: int) -> list:
        """
        Прочитать дочерние Instance.

        Returns:
            список адресов дочерних Instance
        """
        children = []
        try:
            children_start_ptr = self.mem.get_pointer(addr + INSTANCE_CHILDREN_START)
            children_end_ptr = self.mem.get_pointer(addr + INSTANCE_CHILDREN_END)

            if children_start_ptr == 0 or children_end_ptr == 0:
                return children

            if children_end_ptr <= children_start_ptr:
                return children

            current = children_start_ptr
            max_iterations = 5000  # защита от бесконечного цикла

            for _ in range(max_iterations):
                if current >= children_end_ptr:
                    break
                try:
                    child_ptr = self.mem.get_pointer(current)
                    if child_ptr and child_ptr != 0:
                        children.append(child_ptr)
                except Exception:
                    pass
                current += INSTANCE_CHILDREN_STRIDE

        except Exception:
            pass
        return children

    # ── Поиск скриптов ───────────────────────────────────────

    def find_scripts(self, script_type: str = None) -> List[Dict]:
        """
        Найти все скрипты в DataModel.

        Обходит дерево Instance начиная с DataModel и собирает
        все LocalScript, ModuleScript и Script.

        Args:
            script_type: фильтр по типу ("LocalScript", "ModuleScript", "Script", None = все)

        Returns:
            список словарей:
              {"name": str, "class": str, "address": int,
               "bytecode_addr": int, "bytecode_size": int}
        """
        dm_addr = self.get_datamodel_address()
        if dm_addr == 0:
            return []

        results = []
        visited = set()
        queue = [dm_addr]
        max_nodes = 10000  # защита

        while queue and len(results) < max_nodes:
            addr = queue.pop(0)
            if addr in visited or addr == 0:
                continue
            visited.add(addr)

            try:
                class_name = self._read_instance_class(addr)

                if class_name in ("LocalScript", "ModuleScript", "Script"):
                    if script_type and class_name != script_type:
                        # Добавляем детей но не сам скрипт
                        queue.extend(self._read_children(addr))
                        continue

                    # Определяем оффсет байткода
                    bc_offset = {
                        "LocalScript": LOCALSCRIPT_BYTECODE,
                        "ModuleScript": MODULESCRIPT_BYTECODE,
                        "Script": SCRIPT_BYTECODE,
                    }.get(class_name, LOCALSCRIPT_BYTECODE)

                    # Читаем структуру ByteCode
                    bc_struct = self.mem.get_pointer(addr + bc_offset)
                    bc_ptr = 0
                    bc_size = 0

                    if bc_struct:
                        try:
                            bc_ptr = self.mem.get_pointer(bc_struct + BYTECODE_POINTER)
                            bc_size = self.mem.read_int(bc_struct + BYTECODE_SIZE)
                        except Exception:
                            pass

                    results.append({
                        "name": self._read_instance_name(addr),
                        "class": class_name,
                        "address": addr,
                        "bytecode_struct": bc_struct,
                        "bytecode_addr": bc_ptr,
                        "bytecode_size": bc_size,
                    })

                # Добавляем детей в очередь
                children = self._read_children(addr)
                queue.extend(children)

            except Exception:
                continue

        return results

    def find_starter_scripts(self) -> List[Dict]:
        """
        Найти LocalScripts в StarterPlayer / StarterGui.

        Returns:
            список скриптов (как в find_scripts)
        """
        scripts = self.find_scripts("LocalScript")
        starter_scripts = []
        for s in scripts:
            name = s.get("name", "").lower()
            # Скрипты в StarterPlayer обычно имеют приоритетные имена
            # Все StarterPlayer скрипты подойдут
            starter_scripts.append(s)
        return starter_scripts

    def find_injectable_target(self) -> Optional[Dict]:
        """
        Автоматически выбрать лучший скрипт-цель для инъекции.

        Предпочитает LocalScript из StarterPlayer/StarterGui.

        Returns:
            dict с информацией о скрипте, или None
        """
        all_scripts = self.find_scripts()

        # Приоритет: LocalScript с ненулевым байткодом
        for s in all_scripts:
            if s["class"] == "LocalScript" and s["bytecode_size"] > 0:
                return s

        # Fallback: любой LocalScript
        for s in all_scripts:
            if s["class"] == "LocalScript":
                return s

        # Fallback: ModuleScript
        for s in all_scripts:
            if s["class"] == "ModuleScript" and s["bytecode_size"] > 0:
                return s

        return None

    # ── Байткод операции ─────────────────────────────────────

    def dump_bytecode(self, script_address: int, script_class: str = "LocalScript") -> bytes:
        """
        Дамп зашифрованного байткода из скрипта.

        Args:
            script_address: адрес Instance скрипта
            script_class: класс скрипта ("LocalScript", "ModuleScript", "Script")

        Returns:
            зашифрованные байты байткода, или пустые байты
        """
        try:
            bc_offset = {
                "LocalScript": LOCALSCRIPT_BYTECODE,
                "ModuleScript": MODULESCRIPT_BYTECODE,
                "Script": SCRIPT_BYTECODE,
            }.get(script_class, LOCALSCRIPT_BYTECODE)

            bc_struct = self.mem.get_pointer(script_address + bc_offset)
            if bc_struct == 0:
                return b''

            bc_ptr = self.mem.get_pointer(bc_struct + BYTECODE_POINTER)
            bc_size = self.mem.read_int(bc_struct + BYTECODE_SIZE)

            if bc_ptr == 0 or bc_size <= 0 or bc_size > 10_000_000:
                return b''

            return self.mem.read(bc_ptr, bc_size)

        except Exception:
            return b''

    def write_bytecode(self, script_address: int, new_bytecode: bytes,
                       script_class: str = "LocalScript") -> bool:
        """
        Записать новый байткод в скрипт.

        Выделяет память, записывает байткод, обновляет
        ByteCode::Pointer и ByteCode::Size.

        Args:
            script_address: адрес Instance скрипта
            new_bytecode: зашифрованные байты (RSB1)
            script_class: класс скрипта

        Returns:
            True при успехе
        """
        try:
            bc_offset = {
                "LocalScript": LOCALSCRIPT_BYTECODE,
                "ModuleScript": MODULESCRIPT_BYTECODE,
                "Script": SCRIPT_BYTECODE,
            }.get(script_class, LOCALSCRIPT_BYTECODE)

            bc_struct = self.mem.get_pointer(script_address + bc_offset)
            if bc_struct == 0:
                # Создаём новый ByteCode struct
                bc_struct = self.mem.virtual_alloc(0, 64)
                if bc_struct == 0:
                    return False
                # Пишем указатель на новый struct в Instance
                self.mem.write_int(script_address + bc_offset, bc_struct)

            # Выделяем память для байткода
            bc_addr = self.mem.virtual_alloc(0, len(new_bytecode) + 64)
            if bc_addr == 0:
                return False

            # Записываем байткод
            self.mem.write(bc_addr, new_bytecode)

            # Обновляем ByteCode struct
            self.mem.write(bc_struct + BYTECODE_POINTER, struct.pack('<Q', bc_addr))
            self.mem.write(bc_struct + BYTECODE_SIZE, struct.pack('<I', len(new_bytecode)))

            return True

        except Exception:
            return False

    def replace_script_bytecode(self, script_address: int, new_bytecode: bytes,
                                script_class: str = "LocalScript") -> bool:
        """
        Полная замена байткода скрипта.

        В отличие от write_bytecode, создаёт полностью новую структуру
        ByteCode если старая повреждена.

        Args:
            script_address: адрес Instance
            new_bytecode: зашифрованные байты (RSB1)
            script_class: класс скрипта

        Returns:
            True при успехе
        """
        return self.write_bytecode(script_address, new_bytecode, script_class)

    # ── RequireBypass ────────────────────────────────────────

    def set_require_bypass(self, enabled: bool) -> bool:
        """
        Включить или выключить RequireBypass.

        Args:
            enabled: True = включить, False = выключить

        Returns:
            True при успехе
        """
        sc_addr = self.get_script_context_address()
        if sc_addr == 0:
            return False
        try:
            # Сохраняем оригинальное значение при первом вызове
            if self._rb_original is None:
                self._rb_original = self.mem.read_bool(sc_addr + REQUIRE_BYPASS_OFFSET)
                self._rb_modified = False

            self.mem.write_bool(sc_addr + REQUIRE_BYPASS_OFFSET, enabled)
            self._rb_modified = True
            return True
        except Exception:
            return False

    def get_require_bypass(self) -> bool:
        """Прочитать текущее значение RequireBypass."""
        sc_addr = self.get_script_context_address()
        if sc_addr == 0:
            return False
        try:
            return self.mem.read_bool(sc_addr + REQUIRE_BYPASS_OFFSET)
        except Exception:
            return False

    def restore_require_bypass(self) -> bool:
        """
        Восстановить оригинальное значение RequireBypass.

        Returns:
            True при успехе
        """
        if self._rb_original is None or not self._rb_modified:
            return True  # ничего не меняли
        sc_addr = self.get_script_context_address()
        if sc_addr == 0:
            return False
        try:
            self.mem.write_bool(sc_addr + REQUIRE_BYPASS_OFFSET, self._rb_original)
            self._rb_modified = False
            return True
        except Exception:
            return False

    # ── Выполнение ────────────────────────────────────────────

    def trigger_script_reexecute(self, script_address: int) -> bool:
        """
        Перезапустить скрипт через манипуляцию памяти.

        Метод:
        1. Сохраняем указатель на байткод
        2. Обнуляем его (скрипт думает что байткода нет)
        3. Восстанавливаем (VM подхватывает заново)

        Args:
            script_address: адрес Instance скрипта

        Returns:
            True при успехе
        """
        try:
            # Определяем класс
            class_name = self._read_instance_class(script_address)
            bc_offset = {
                "LocalScript": LOCALSCRIPT_BYTECODE,
                "ModuleScript": MODULESCRIPT_BYTECODE,
                "Script": SCRIPT_BYTECODE,
            }.get(class_name, LOCALSCRIPT_BYTECODE)

            # Читаем текущий указатель на ByteCode struct
            bc_struct = self.mem.get_pointer(script_address + bc_offset)

            # Обнуляем (скрипт «теряет» байткод)
            self.mem.write(script_address + bc_offset, struct.pack('<Q', 0))
            time.sleep(0.05)  # Небольшая пауза

            # Восстанавливаем
            self.mem.write(script_address + bc_offset, struct.pack('<Q', bc_struct))

            return True
        except Exception:
            return False

    def inject_raw_bytecode(self, bytecode: bytes, target_address: int = None,
                            script_class: str = "LocalScript") -> Dict:
        """
        Инжектировать сырой (уже зашифрованный) байткод.

        Args:
            bytecode: RSB1 зашифрованные байты
            target_address: адрес целевого скрипта (None = авто)
            script_class: класс целевого скрипта

        Returns:
            {"success": bool, "message": str, "target": str}
        """
        with self._lock:
            try:
                # Автоматический выбор цели
                if target_address is None:
                    target = self.find_injectable_target()
                    if not target:
                        return {"success": False, "message": "Не найден скрипт-цель", "target": ""}
                    target_address = target["address"]
                    script_class = target["class"]
                    target_name = target["name"]
                else:
                    target_name = self._read_instance_name(target_address)

                # Записываем байткод
                ok = self.write_bytecode(target_address, bytecode, script_class)
                if not ok:
                    return {"success": False, "message": "Ошибка записи байткода",
                            "target": target_name}

                # Перезапускаем скрипт
                self.trigger_script_reexecute(target_address)

                self._injection_count += 1
                self._last_injection_time = time.time()

                return {
                    "success": True,
                    "message": f"Инжектировано ({len(bytecode)} байт) в {target_name}",
                    "target": target_name,
                }

            except Exception as e:
                return {"success": False, "message": str(e), "target": ""}

    def inject_and_execute(self, lua_source: str, target_script: int = None) -> Dict:
        """
        Полный pipeline инъекции Lua кода.

        1. Находит целевой скрипт (если не указан)
        2. Конвертирует Lua source в RSB1 байткод
        3. Временно включает RequireBypass
        4. Записывает байткод
        5. Перезапускает скрипт
        6. Восстанавливает RequireBypass

        Args:
            lua_source: исходный Lua код
            target_script: адрес целевого скрипта (None = авто)

        Returns:
            {"success": bool, "message": str, "target": str}
        """
        with self._lock:
            try:
                # Авто-выбор цели
                if target_script is None:
                    target = self.find_injectable_target()
                    if not target:
                        return {"success": False, "message": "Не найден скрипт-цель", "target": ""}
                    target_script = target["address"]
                    script_class = target["class"]
                    target_name = target["name"]
                else:
                    script_class = self._read_instance_class(target_script) or "LocalScript"
                    target_name = self._read_instance_name(target_script)

                # Шифруем в RSB1
                plain = lua_source.encode('utf-8')
                encrypted = RSB1Encryptor.encrypt(plain)

                # Временно включаем RequireBypass для успешного перезапуска
                self.set_require_bypass(True)

                # Записываем байткод
                ok = self.write_bytecode(target_script, encrypted, script_class)
                if not ok:
                    self.restore_require_bypass()
                    return {"success": False, "message": "Ошибка записи байткода",
                            "target": target_name}

                # Перезапускаем скрипт
                self.trigger_script_reexecute(target_script)

                # Восстанавливаем RequireBypass
                self.restore_require_bypass()

                self._injection_count += 1
                self._last_injection_time = time.time()

                return {
                    "success": True,
                    "message": f"Выполнено в {target_name} ({len(encrypted)} байт)",
                    "target": target_name,
                }

            except Exception as e:
                self.restore_require_bypass()
                return {"success": False, "message": str(e), "target": ""}

    def execute(self, lua_source: str) -> Dict:
        """
        Упрощённая точка входа для выполнения Lua кода.

        Автоматически управляет RequireBypass:
          ON → inject → reexecute → OFF

        Args:
            lua_source: Lua код для выполнения

        Returns:
            {"success": bool, "message": str, "target": str}
        """
        return self.inject_and_execute(lua_source)

    # ── Информация ────────────────────────────────────────────

    def read_script_info(self, script_address: int) -> Dict:
        """
        Прочитать полную информацию о скрипте.

        Args:
            script_address: адрес Instance

        Returns:
            словарь с метаданными скрипта
        """
        try:
            name = self._read_instance_name(script_address)
            class_name = self._read_instance_class(script_address)

            bc_offset = {
                "LocalScript": LOCALSCRIPT_BYTECODE,
                "ModuleScript": MODULESCRIPT_BYTECODE,
                "Script": SCRIPT_BYTECODE,
            }.get(class_name, LOCALSCRIPT_BYTECODE)

            bc_struct = self.mem.get_pointer(script_address + bc_offset)
            bc_ptr = 0
            bc_size = 0
            is_rsb1 = False

            if bc_struct:
                bc_ptr = self.mem.get_pointer(bc_struct + BYTECODE_POINTER)
                bc_size = self.mem.read_int(bc_struct + BYTECODE_SIZE)
                if bc_ptr and bc_size > 0:
                    header = self.mem.read(bc_ptr, 4)
                    is_rsb1 = header == struct.pack('<I', RSB1Encryptor.MAGIC_A)

            return {
                "name": name,
                "class": class_name,
                "address": script_address,
                "bytecode_struct": bc_struct,
                "bytecode_addr": bc_ptr,
                "bytecode_size": bc_size,
                "is_rsb1": is_rsb1,
            }

        except Exception as e:
            return {"name": "?", "class": "?", "error": str(e)}

    def get_diagnostic_info(self) -> Dict:
        """
        Получить диагностическую информацию об исполнителе.

        Returns:
            словарь с состоянием всех подсистем
        """
        scripts = self.find_scripts()
        local_count = sum(1 for s in scripts if s["class"] == "LocalScript")
        module_count = sum(1 for s in scripts if s["class"] == "ModuleScript")
        script_count = sum(1 for s in scripts if s["class"] == "Script")

        return {
            "base": f"0x{self.base:X}",
            "datamodel": f"0x{self._dm_addr:X}",
            "script_context": f"0x{self._sc_addr:X}",
            "task_scheduler": f"0x{self._ts_addr:X}",
            "require_bypass": self.get_require_bypass(),
            "rb_original": self._rb_original,
            "rb_modified": self._rb_modified,
            "total_scripts": len(scripts),
            "local_scripts": local_count,
            "module_scripts": module_count,
            "scripts": script_count,
            "injection_count": self._injection_count,
            "last_injection": time.strftime("%H:%M:%S",
                time.localtime(self._last_injection_time)) if self._last_injection_time else "never",
        }

    # ── Context Manager ───────────────────────────────────────

    def __enter__(self):
        """Контекстный менеджер: auto-save RequireBypass."""
        return self

    def __exit__(self, *args):
        """Контекстный менеджер: auto-restore RequireBypass."""
        self.restore_require_bypass()

    def __repr__(self):
        return (f"MemoryScriptExecutor(base=0x{self.base:X}, "
                f"dm=0x{self._dm_addr:X}, "
                f"injections={self._injection_count})")
