"""
ScriptContext Module — Контекст скриптов Roblox

Позволяет:
  - Читает ScriptContext::RequireBypass
  - Доступ к ScriptContext через DataModel
"""

import struct


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

SCRIPT_CONTEXT_OFFSETS = {
    "ScriptContext": 0x861,     # DataModel::ScriptContext
    "RequireBypass": 0x8fd,     # ScriptContext::RequireBypass
}


class ScriptContextWrapper:
    """
    Обёртка над ScriptContext Roblox.

    Предоставляет доступ к RequireBypass и другой информации
    о контексте выполнения скриптов.

    Usage:
        sc = ScriptContextWrapper(memory_module, data_model_address)
        print(sc.require_bypass)     # bool
        sc.require_bypass = True     # включает bypass
    """

    def __init__(self, memory_module, data_model_address: int):
        self.mem = memory_module
        self._dm_addr = data_model_address
        self._offsets = SCRIPT_CONTEXT_OFFSETS

    @property
    def address(self) -> int:
        """Адрес ScriptContext."""
        try:
            addr = self._dm_addr + self._offsets["ScriptContext"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    @property
    def require_bypass(self) -> bool:
        """
        ScriptContext::RequireBypass.

        Внутренний флаг Roblox, отвечающий за обработку require().
        """
        try:
            # RequireBypass — булево значение по оффсету от начала ScriptContext
            addr = self.address + self._offsets["RequireBypass"]
            return self.mem.read_bool(addr)
        except Exception:
            return False

    @require_bypass.setter
    def require_bypass(self, value: bool):
        """
        Установить RequireBypass.

        Внимание: изменение этого флага может повлиять на загрузку скриптов.
        """
        try:
            addr = self.address + self._offsets["RequireBypass"]
            self.mem.write_bool(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write RequireBypass: {e}")

    def __repr__(self):
        return f"ScriptContext(address=0x{self.address:X}, require_bypass={self.require_bypass})"
