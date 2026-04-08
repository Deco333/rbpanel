"""
VisualEngine Module — Движок рендеринга Roblox

Позволяет:
  - Читать ViewMatrix (4x4) для World-to-Screen проекций
  - Получать размеры вьюпорта (Dimensions)
  - Доступ к RenderView, DeviceD3D11
  - World-to-Screen (W2S) преобразования для ESP/aimbot
"""

import struct
import math


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

VISUAL_ENGINE_OFFSETS = {
    "Pointer": 0x7ef81d8,
    "Dimensions": 0xa60,     # Vec2 (ширина, высота)
    "ViewMatrix": 0x130,     # 4x4 float matrix (64 bytes)
    "RenderView": 0xb40,
    "FakeDataModel": 0xa40,
}

RENDER_VIEW_OFFSETS = {
    "LightingValid": 0x148,
    "SkyValid": 0x0,
    "VisualEngine": 0x10,
    "DeviceD3D11": 0x8,
}


class VisualEngine:
    """
    Обёртка над VisualEngine Roblox.

    Usage:
        ve = VisualEngine(memory_module)
        print(ve.dimensions)          # (1920, 1080)
        print(ve.view_matrix)          # [[...], ...]
        w2s = W2SHelper(ve)
        screen_pos = w2s.world_to_screen(Vector3(100, 50, 200))
    """

    def __init__(self, memory_module):
        self.mem = memory_module
        self.base = memory_module.base
        self._engine_ptr = self.base + VISUAL_ENGINE_OFFSETS["Pointer"]
        self._engine_addr = self.mem.get_pointer(self._engine_ptr)
        self._offsets = VISUAL_ENGINE_OFFSETS

    @property
    def address(self) -> int:
        return self._engine_addr

    # ── Dimensions ──────────────────────────────────────────

    @property
    def dimensions(self) -> tuple:
        """
        Размеры вьюпорта (ширина, высота) в пикселях.

        Returns:
            tuple[float, float]
        """
        try:
            addr = self._engine_addr + self._offsets["Dimensions"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            return (x, y)
        except Exception:
            return (0.0, 0.0)

    @dimensions.setter
    def dimensions(self, value: tuple):
        """Установить размеры вьюпорта."""
        try:
            addr = self._engine_addr + self._offsets["Dimensions"]
            self.mem.write_float(addr, float(value[0]))
            self.mem.write_float(addr + 4, float(value[1]))
        except Exception as e:
            raise RuntimeError(f"Failed to write Dimensions: {e}")

    @property
    def width(self) -> float:
        """Ширина вьюпорта."""
        return self.dimensions[0]

    @property
    def height(self) -> float:
        """Высота вьюпорта."""
        return self.dimensions[1]

    # ── ViewMatrix ──────────────────────────────────────────

    @property
    def view_matrix(self) -> list[list[float]]:
        """
        Матрица вида (ViewMatrix) 4x4.

        Returns:
            list из 4 списков по 4 float — строки матрицы.

        Формат в памяти: column-major (OpenGL стиль), 16 consecutive floats.
        """
        try:
            addr = self._engine_addr + self._offsets["ViewMatrix"]
            raw = self.mem.read_floats(addr, 16)

            # Roblox хранит column-major, конвертируем в row-major
            # raw[i] = column (i%4), row (i//4)
            matrix = [[0.0] * 4 for _ in range(4)]
            for i in range(4):
                for j in range(4):
                    matrix[j][i] = raw[i * 4 + j]

            return matrix
        except Exception:
            return [[0.0] * 4 for _ in range(4)]

    @property
    def view_matrix_raw(self) -> list[float]:
        """Сырая view matrix (16 float, column-major)."""
        try:
            addr = self._engine_addr + self._offsets["ViewMatrix"]
            return self.mem.read_floats(addr, 16)
        except Exception:
            return [0.0] * 16

    # ── RenderView ──────────────────────────────────────────

    @property
    def render_view(self) -> "RenderView":
        """Возвращает RenderView обёртку."""
        return RenderView(self.mem, self._engine_addr)

    @property
    def render_view_address(self) -> int:
        """Адрес RenderView."""
        try:
            addr = self._engine_addr + self._offsets["RenderView"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    # ── LightingValid / SkyValid ────────────────────────────

    @property
    def lighting_valid(self) -> bool:
        """Проверяет валидность лайтинга в RenderView."""
        try:
            rv_addr = self.render_view_address
            if rv_addr == 0:
                return False
            addr = rv_addr + RENDER_VIEW_OFFSETS["LightingValid"]
            return self.mem.read_bool(addr)
        except Exception:
            return False

    @property
    def sky_valid(self) -> bool:
        """Проверяет валидность скайбокса в RenderView."""
        try:
            rv_addr = self.render_view_address
            if rv_addr == 0:
                return False
            addr = rv_addr + RENDER_VIEW_OFFSETS["SkyValid"]
            return self.mem.read_bool(addr)
        except Exception:
            return False

    # ── Refresh ─────────────────────────────────────────────

    def refresh(self):
        """Переобновить адрес VisualEngine."""
        self._engine_addr = self.mem.get_pointer(self._engine_ptr)

    def __repr__(self):
        return (
            f"VisualEngine(address=0x{self._engine_addr:X}, "
            f"dimensions={self.dimensions})"
        )


class RenderView:
    """
    Обёртка над RenderView Roblox.

    Attributes:
        address: адрес RenderView
        lighting_valid: валиден ли лайтинг
        sky_valid: валиден ли скайбокс
    """

    def __init__(self, memory_module, visual_engine_addr: int):
        self.mem = memory_module
        self._ve_addr = visual_engine_addr
        self._offsets = RENDER_VIEW_OFFSETS

    @property
    def address(self) -> int:
        try:
            addr = self._ve_addr + VISUAL_ENGINE_OFFSETS["RenderView"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    @property
    def lighting_valid(self) -> bool:
        try:
            rv = self.address
            if rv == 0:
                return False
            return self.mem.read_bool(rv + self._offsets["LightingValid"])
        except Exception:
            return False

    @property
    def sky_valid(self) -> bool:
        try:
            rv = self.address
            if rv == 0:
                return False
            return self.mem.read_bool(rv + self._offsets["SkyValid"])
        except Exception:
            return False

    @property
    def device_d3d11_address(self) -> int:
        """Адрес D3D11 Device (для продвинутых задач)."""
        try:
            rv = self.address
            if rv == 0:
                return 0
            return self.mem.get_pointer(rv + self._offsets["DeviceD3D11"])
        except Exception:
            return 0

    def __repr__(self):
        return (
            f"RenderView(address=0x{self.address:X}, "
            f"lighting_valid={self.lighting_valid}, "
            f"sky_valid={self.sky_valid})"
        )


class W2SHelper:
    """
    World-to-Screen преобразователь.

    Использует ViewMatrix из VisualEngine для перевода
    3D мировых координат в 2D экранные.

    Usage:
        ve = VisualEngine(memory_module)
        w2s = W2SHelper(ve)
        result = w2s.world_to_screen(Vector3(100, 50, 200))
        if result.on_screen:
            print(f"Screen: {result.x}, {result.y}")

    Attributes:
        visual_engine: VisualEngine instance
    """

    def __init__(self, visual_engine: VisualEngine):
        self.ve = visual_engine

    def world_to_screen(self, world_pos) -> "W2SResult":
        """
        Преобразует 3D позицию в 2D экранные координаты.

        Args:
            world_pos: Vector3, tuple (x,y,z) или list [x,y,z]

        Returns:
            W2SResult с полями:
              - x (float): экранный X
              - y (float): экранный Y
              - on_screen (bool): виден ли на экране
              - depth (float): глубина (Z в clip space)
        """
        # Извлекаем координаты
        if hasattr(world_pos, "X"):
            px, py, pz = world_pos.X, world_pos.Y, world_pos.Z
        elif isinstance(world_pos, (tuple, list)):
            px, py, pz = float(world_pos[0]), float(world_pos[1]), float(world_pos[2])
        else:
            raise TypeError(f"Expected Vector3 or tuple/list, got {type(world_pos)}")

        view_matrix = self.ve.view_matrix

        # Clip space transform: clip = Matrix * (x, y, z, 1)
        clip_x = (
            view_matrix[0][0] * px
            + view_matrix[1][0] * py
            + view_matrix[2][0] * pz
            + view_matrix[3][0]
        )
        clip_y = (
            view_matrix[0][1] * px
            + view_matrix[1][1] * py
            + view_matrix[2][1] * pz
            + view_matrix[3][1]
        )
        clip_w = (
            view_matrix[0][3] * px
            + view_matrix[1][3] * py
            + view_matrix[2][3] * pz
            + view_matrix[3][3]
        )

        # Проверяем, что точка перед камерой
        on_screen = clip_w > 0.1

        if not on_screen:
            return W2SResult(0, 0, False, clip_w)

        # NDC (Normalized Device Coordinates)
        ndc_x = clip_x / clip_w
        ndc_y = clip_y / clip_w

        # Screen coordinates
        screen_w, screen_h = self.ve.dimensions
        screen_x = (screen_w * 0.5) * (1.0 + ndc_x)
        screen_y = (screen_h * 0.5) * (1.0 - ndc_y)

        # Дополнительная проверка — в пределах экрана с небольшим запасом
        margin = 100
        on_screen = (
            -margin <= screen_x <= screen_w + margin
            and -margin <= screen_y <= screen_h + margin
        )

        return W2SResult(screen_x, screen_y, on_screen, clip_w)

    def world_to_screen_many(self, positions: list) -> list:
        """
        Batch W2S для множества позиций.

        Args:
            positions: список Vector3, tuple или list

        Returns:
            список W2SResult
        """
        return [self.world_to_screen(pos) for pos in positions]

    def is_visible(self, world_pos, margin: float = 100.0) -> bool:
        """
        Быстрая проверка видимости точки (без создания W2SResult).

        Args:
            world_pos: Vector3, tuple или list
            margin: запас в пикселях за краем экрана

        Returns:
            bool: видна ли точка на экране
        """
        result = self.world_to_screen(world_pos)
        if not result.on_screen:
            return False
        w, h = self.ve.dimensions
        return (
            -margin <= result.x <= w + margin
            and -margin <= result.y <= h + margin
        )

    def world_distance_to_screen_size(
        self, world_pos, world_size: float = 1.0
    ) -> float:
        """
        Вычисляет размер в пикселях для заданного мирового размера
        на данной дистанции. Полезно для ESP box sizing.

        Args:
            world_pos: позиция объекта
            world_size: размер объекта в студийных единицах

        Returns:
            float: размер в пикселях
        """
        # Вычисляем distance через clip_w
        if hasattr(world_pos, "X"):
            px, py, pz = world_pos.X, world_pos.Y, world_pos.Z
        elif isinstance(world_pos, (tuple, list)):
            px, py, pz = world_pos[0], world_pos[1], world_pos[2]
        else:
            return 0.0

        view_matrix = self.ve.view_matrix
        clip_w = (
            view_matrix[0][3] * px
            + view_matrix[1][3] * py
            + view_matrix[2][3] * pz
            + view_matrix[3][3]
        )

        if clip_w < 0.1:
            return 0.0

        h = self.ve.height
        if h <= 0:
            return 0.0

        return abs(world_size / clip_w * h)


class W2SResult:
    """
    Результат World-to-Screen преобразования.

    Attributes:
        x (float): экранный X
        y (float): экранный Y
        on_screen (bool): видна ли точка
        depth (float): глубина в clip space (w component)
    """

    __slots__ = ("x", "y", "on_screen", "depth")

    def __init__(self, x: float, y: float, on_screen: bool, depth: float):
        self.x = x
        self.y = y
        self.on_screen = on_screen
        self.depth = depth

    def __repr__(self):
        status = "VISIBLE" if self.on_screen else "OFFSCREEN"
        return f"W2SResult(x={self.x:.1f}, y={self.y:.1f}, {status}, depth={self.depth:.2f})"

    def to_tuple(self) -> tuple:
        """Возвращает (x, y, on_screen)."""
        return (self.x, self.y, self.on_screen)
