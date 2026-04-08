"""
Terrain Module — Террейн Roblox

Позволяет:
  - Управлять водой (Reflectance, Transparency, WaveSize, WaveSpeed, Color)
  - Читать/писать MaterialColors (22 материала)
  - Управлять травой (GrassLength)
  - Работать с World (Primitives count, etc.)
"""

import struct


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

TERRAIN_OFFSETS = {
    "GrassLength": 0x1f8,
    "WaterReflectance": 0x200,
    "WaterTransparency": 0x204,
    "WaterWaveSize": 0x208,
    "WaterWaveSpeed": 0x20c,
    "WaterColor": 0x1e8,
    "MaterialColors": 0x290,
}

MATERIAL_COLORS_OFFSETS = {
    "Asphalt": 0x30,
    "Basalt": 0x27,
    "Brick": 0xf,
    "Cobblestone": 0x33,
    "Concrete": 0xc,
    "CrackedLava": 0x2d,
    "Glacier": 0x1b,
    "Grass": 0x6,
    "Ground": 0x2a,
    "Ice": 0x36,
    "LeafyGrass": 0x39,
    "Limestone": 0x3f,
    "Mud": 0x24,
    "Pavement": 0x42,
    "Rock": 0x18,
    "Salt": 0x3c,
    "Sand": 0x12,
    "Sandstone": 0x21,
    "Slate": 0x9,
    "Snow": 0x1e,
    "WoodPlanks": 0x15,
}

WORLD_OFFSETS = {
    "Gravity": 0x1d8,
    "worldStepsPerSec": 0x668,
    "FallenPartsDestroyHeight": 0x1d0,
    "AirProperties": 0x1e0,
    "Primitives": 0x248,
}


class TerrainWrapper:
    """
    Обёртка над Terrain (инстанс).

    Usage:
        # Предполагается, что terrain — RBXInstance с ClassName "Terrain"
        terrain = TerrainWrapper(terrain_instance)
        print(terrain.water_color)
        terrain.water_transparency = 0.5
    """

    def __init__(self, instance):
        """
        Args:
            instance: RBXInstance — инстанс Terrain
        """
        self.instance = instance
        self.mem = instance.memory_module
        self._offsets = TERRAIN_OFFSETS

    # ── Water ───────────────────────────────────────────────

    @property
    def water_color(self):
        """Цвет воды (Color3)."""
        from ..datastructures import Color3

        try:
            addr = self.instance.address + self._offsets["WaterColor"]
            r = self.mem.read_int(addr) / 255.0
            g = self.mem.read_int(addr + 4) / 255.0
            b = self.mem.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            from ..datastructures import Color3
            return Color3()

    @water_color.setter
    def water_color(self, value):
        """Установить цвет воды."""
        from ..datastructures import Color3

        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")

        try:
            addr = self.instance.address + self._offsets["WaterColor"]
            self.mem.write_int(addr, int(r * 255))
            self.mem.write_int(addr + 4, int(g * 255))
            self.mem.write_int(addr + 8, int(b * 255))
        except Exception as e:
            raise RuntimeError(f"Failed to write WaterColor: {e}")

    @property
    def water_reflectance(self) -> float:
        """Отражение воды [0, 1]."""
        try:
            addr = self.instance.address + self._offsets["WaterReflectance"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @water_reflectance.setter
    def water_reflectance(self, value: float):
        try:
            addr = self.instance.address + self._offsets["WaterReflectance"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write WaterReflectance: {e}")

    @property
    def water_transparency(self) -> float:
        """Прозрачность воды [0, 1]."""
        try:
            addr = self.instance.address + self._offsets["WaterTransparency"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @water_transparency.setter
    def water_transparency(self, value: float):
        try:
            addr = self.instance.address + self._offsets["WaterTransparency"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write WaterTransparency: {e}")

    @property
    def water_wave_size(self) -> float:
        """Размер волны."""
        try:
            addr = self.instance.address + self._offsets["WaterWaveSize"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @water_wave_size.setter
    def water_wave_size(self, value: float):
        try:
            addr = self.instance.address + self._offsets["WaterWaveSize"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write WaterWaveSize: {e}")

    @property
    def water_wave_speed(self) -> float:
        """Скорость волны."""
        try:
            addr = self.instance.address + self._offsets["WaterWaveSpeed"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @water_wave_speed.setter
    def water_wave_speed(self, value: float):
        try:
            addr = self.instance.address + self._offsets["WaterWaveSpeed"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write WaterWaveSpeed: {e}")

    # ── Grass ───────────────────────────────────────────────

    @property
    def grass_length(self) -> float:
        """Длина травы."""
        try:
            addr = self.instance.address + self._offsets["GrassLength"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @grass_length.setter
    def grass_length(self, value: float):
        try:
            addr = self.instance.address + self._offsets["GrassLength"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write GrassLength: {e}")

    # ── MaterialColors ──────────────────────────────────────

    def get_material_colors(self) -> "MaterialColors":
        """Возвращает обёртку для работы с цветами материалов."""
        mc_addr = self.instance.address + self._offsets["MaterialColors"]
        return MaterialColors(self.mem, mc_addr)

    def __repr__(self):
        return f"Terrain(water_color={self.water_color}, grass_length={self.grass_length})"


class MaterialColors:
    """
    Обёртка над MaterialColors террейна.

    Позволяет читать/писать цвета 22 материалов.

    Usage:
        mc = terrain.get_material_colors()
        print(mc.grass)           # Color3
        mc.snow = Color3(1, 1, 1)
        mc.asphalt = (0.2, 0.2, 0.2)
        print(mc.get_all())
    """

    SUPPORTED_MATERIALS = list(MATERIAL_COLORS_OFFSETS.keys())

    def __init__(self, memory_module, base_address: int):
        self.mem = memory_module
        self._base = base_address
        self._offsets = MATERIAL_COLORS_OFFSETS

    def _read_color3_at(self, offset: int):
        """Читает Color3 по смещению (3 байта RGB → float 0-1)."""
        from ..datastructures import Color3

        try:
            addr = self._base + offset
            r = self.mem.read_int(addr) / 255.0
            g = self.mem.read_int(addr + 4) / 255.0
            b = self.mem.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return None

    def _write_color3_at(self, offset: int, value):
        """Пишет Color3 по смещению."""
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")

        addr = self._base + offset
        self.mem.write_int(addr, int(r * 255))
        self.mem.write_int(addr + 4, int(g * 255))
        self.mem.write_int(addr + 8, int(b * 255))

    # ── Индивидуальные материалы (property) ─────────────────

    @property
    def asphalt(self):
        return self._read_color3_at(self._offsets["Asphalt"])

    @asphalt.setter
    def asphalt(self, value):
        self._write_color3_at(self._offsets["Asphalt"], value)

    @property
    def basalt(self):
        return self._read_color3_at(self._offsets["Basalt"])

    @basalt.setter
    def basalt(self, value):
        self._write_color3_at(self._offsets["Basalt"], value)

    @property
    def brick(self):
        return self._read_color3_at(self._offsets["Brick"])

    @brick.setter
    def brick(self, value):
        self._write_color3_at(self._offsets["Brick"], value)

    @property
    def cobblestone(self):
        return self._read_color3_at(self._offsets["Cobblestone"])

    @cobblestone.setter
    def cobblestone(self, value):
        self._write_color3_at(self._offsets["Cobblestone"], value)

    @property
    def concrete(self):
        return self._read_color3_at(self._offsets["Concrete"])

    @concrete.setter
    def concrete(self, value):
        self._write_color3_at(self._offsets["Concrete"], value)

    @property
    def cracked_lava(self):
        return self._read_color3_at(self._offsets["CrackedLava"])

    @cracked_lava.setter
    def cracked_lava(self, value):
        self._write_color3_at(self._offsets["CrackedLava"], value)

    @property
    def glacier(self):
        return self._read_color3_at(self._offsets["Glacier"])

    @glacier.setter
    def glacier(self, value):
        self._write_color3_at(self._offsets["Glacier"], value)

    @property
    def grass(self):
        return self._read_color3_at(self._offsets["Grass"])

    @grass.setter
    def grass(self, value):
        self._write_color3_at(self._offsets["Grass"], value)

    @property
    def ground(self):
        return self._read_color3_at(self._offsets["Ground"])

    @ground.setter
    def ground(self, value):
        self._write_color3_at(self._offsets["Ground"], value)

    @property
    def ice(self):
        return self._read_color3_at(self._offsets["Ice"])

    @ice.setter
    def ice(self, value):
        self._write_color3_at(self._offsets["Ice"], value)

    @property
    def leafy_grass(self):
        return self._read_color3_at(self._offsets["LeafyGrass"])

    @leafy_grass.setter
    def leafy_grass(self, value):
        self._write_color3_at(self._offsets["LeafyGrass"], value)

    @property
    def limestone(self):
        return self._read_color3_at(self._offsets["Limestone"])

    @limestone.setter
    def limestone(self, value):
        self._write_color3_at(self._offsets["Limestone"], value)

    @property
    def mud(self):
        return self._read_color3_at(self._offsets["Mud"])

    @mud.setter
    def mud(self, value):
        self._write_color3_at(self._offsets["Mud"], value)

    @property
    def pavement(self):
        return self._read_color3_at(self._offsets["Pavement"])

    @pavement.setter
    def pavement(self, value):
        self._write_color3_at(self._offsets["Pavement"], value)

    @property
    def rock(self):
        return self._read_color3_at(self._offsets["Rock"])

    @rock.setter
    def rock(self, value):
        self._write_color3_at(self._offsets["Rock"], value)

    @property
    def salt(self):
        return self._read_color3_at(self._offsets["Salt"])

    @salt.setter
    def salt(self, value):
        self._write_color3_at(self._offsets["Salt"], value)

    @property
    def sand(self):
        return self._read_color3_at(self._offsets["Sand"])

    @sand.setter
    def sand(self, value):
        self._write_color3_at(self._offsets["Sand"], value)

    @property
    def sandstone(self):
        return self._read_color3_at(self._offsets["Sandstone"])

    @sandstone.setter
    def sandstone(self, value):
        self._write_color3_at(self._offsets["Sandstone"], value)

    @property
    def slate(self):
        return self._read_color3_at(self._offsets["Slate"])

    @slate.setter
    def slate(self, value):
        self._write_color3_at(self._offsets["Slate"], value)

    @property
    def snow(self):
        return self._read_color3_at(self._offsets["Snow"])

    @snow.setter
    def snow(self, value):
        self._write_color3_at(self._offsets["Snow"], value)

    @property
    def wood_planks(self):
        return self._read_color3_at(self._offsets["WoodPlanks"])

    @wood_planks.setter
    def wood_planks(self, value):
        self._write_color3_at(self._offsets["WoodPlanks"], value)

    # ── Batch операции ──────────────────────────────────────

    def get(self, name: str):
        """
        Получить цвет материала по имени.

        Args:
            name: название материала (например "Grass", "Snow")

        Returns:
            Color3 или None
        """
        offset = self._offsets.get(name)
        if offset is None:
            raise KeyError(f"Unknown material: {name}. Available: {self.SUPPORTED_MATERIALS}")
        return self._read_color3_at(offset)

    def set(self, name: str, value):
        """
        Установить цвет материала по имени.

        Args:
            name: название материала
            value: Color3, tuple или list (r, g, b)
        """
        offset = self._offsets.get(name)
        if offset is None:
            raise KeyError(f"Unknown material: {name}")
        self._write_color3_at(offset, value)

    def get_all(self) -> dict:
        """
        Получить все цвета материалов.

        Returns:
            dict[str, Color3]: словарь {имя: цвет}
        """
        result = {}
        for name in self.SUPPORTED_MATERIALS:
            color = self._read_color3_at(self._offsets[name])
            if color is not None:
                result[name] = color
        return result

    def set_all(self, value):
        """
        Установить одинаковый цвет для ВСЕХ материалов.

        Args:
            value: Color3, tuple или list (r, g, b)
        """
        for name in self.SUPPORTED_MATERIALS:
            try:
                self._write_color3_at(self._offsets[name], value)
            except Exception:
                pass

    # ── dict-like access ────────────────────────────────────

    def __getitem__(self, name):
        return self.get(name)

    def __setitem__(self, name, value):
        self.set(name, value)

    def __contains__(self, name):
        return name in self._offsets

    def __repr__(self):
        return f"MaterialColors(materials={len(self.SUPPORTED_MATERIALS)})"


class WorldWrapper:
    """
    Обёртка над World (физический мир Workspace).

    Доступ к Gravitiy, Primitives, AirProperties.

    Usage:
        world = WorldWrapper(memory_module, workspace_address)
        print(world.primitive_count)
    """

    def __init__(self, memory_module, workspace_address: int):
        self.mem = memory_module
        self._ws_addr = workspace_address

    @property
    def address(self) -> int:
        """Адрес World."""
        try:
            return self._ws_addr + 0x400  # Workspace::World
        except Exception:
            return 0

    @property
    def primitive_count(self) -> int:
        """Количество примитивов в мире."""
        try:
            addr = self.address
            return self.mem.read_int(addr + 0x248)
        except Exception:
            return 0

    def __repr__(self):
        return f"World(primitive_count={self.primitive_count})"
