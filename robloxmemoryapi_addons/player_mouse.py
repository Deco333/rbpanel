"""
PlayerMouse Module — Мышь игрока Roblox

Позволяет:
  - Доступ к PlayerMouse инстансу через Player
  - Чтение/запись Icon (текстура курсора)
  - Доступ к Workspace через PlayerMouse
"""


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

PLAYER_MOUSE_OFFSETS = {
    "Mouse": 0xf90,          # Player::Mouse
    "Workspace": 0x168,      # PlayerMouse::Workspace
    "Icon": 0xe0,            # PlayerMouse::Icon (от начала объекта)
}


class PlayerMouseWrapper:
    """
    Обёртка над PlayerMouse Roblox.

    PlayerMouse — объект, возвращаемый Player:GetMouse() в Lua.

    Usage:
        # player — PlayerClass RBXInstance
        mouse = PlayerMouseWrapper(player)
        print(mouse.icon)           # текущая иконка курсора
        mouse.icon = "rbxassetid://12345"   # сменить курсор
    """

    def __init__(self, player_instance):
        """
        Args:
            player_instance: RBXInstance (Player)
        """
        self.player = player_instance
        self.mem = player_instance.memory_module
        self._offsets = PLAYER_MOUSE_OFFSETS

    @property
    def address(self) -> int:
        """Адрес PlayerMouse."""
        try:
            addr = self.player.address + self._offsets["Mouse"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    @property
    def is_valid(self) -> bool:
        """Валиден ли PlayerMouse (Character загружен)."""
        return self.address != 0

    # ── Icon ────────────────────────────────────────────────

    @property
    def icon(self) -> str:
        """
        Текущая иконка (текстура) курсора.

        В Roblox это строка типа "rbxassetid://..." или пустая строка.
        """
        try:
            # Icon оффсет 0x0 — от начала PlayerMouse объекта
            addr = self.address + self._offsets["Icon"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @icon.setter
    def icon(self, value: str):
        """
        Установить иконку курсора.

        Args:
            value: Asset ID (rbxassetid://...) или пустая строка
        """
        try:
            addr = self.address + self._offsets["Icon"]
            self.mem.write_string(addr, str(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Icon: {e}")

    # ── Workspace reference ─────────────────────────────────

    @property
    def workspace_address(self) -> int:
        """Адрес Workspace, на который ссылается PlayerMouse."""
        try:
            addr = self.address + self._offsets["Workspace"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    @property
    def workspace(self):
        """Workspace инстанс, на который ссылается PlayerMouse."""
        try:
            ws_addr = self.workspace_address
            if ws_addr == 0:
                return None
            from ...instance import RBXInstance
            return RBXInstance(ws_addr, self.mem)
        except Exception:
            return None

    def __repr__(self):
        if self.is_valid:
            return f"PlayerMouse(icon={self.icon!r})"
        return "PlayerMouse(invalid — no character loaded)"
