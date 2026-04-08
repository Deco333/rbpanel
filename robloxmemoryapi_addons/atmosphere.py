"""
Atmosphere Module — Атмосфера Roblox

Позволяет управлять атмосферными эффектами:
  - Density, Offset, Color, Decay, Glare, Haze
"""

import struct


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

ATMOSPHERE_OFFSETS = {
    "Density": 0xe8,
    "Offset": 0xf4,
    "Color": 0xd0,
    "Decay": 0xdc,
    "Glare": 0xec,
    "Haze": 0xf0,
}


class AtmosphereWrapper:
    """
    Обёртка над Atmosphere инстансом.

    Usage:
        # atm — RBXInstance с ClassName "Atmosphere"
        atm = AtmosphereWrapper(atm_instance)
        atm.density = 0.5
        atm.haze = 10
        atm.color = Color3(0.8, 0.9, 1.0)
    """

    def __init__(self, instance):
        self.instance = instance
        self.mem = instance.memory_module
        self._offsets = ATMOSPHERE_OFFSETS

    @property
    def address(self) -> int:
        return self.instance.address

    @property
    def density(self) -> float:
        """Плотность атмосферы."""
        try:
            addr = self.address + self._offsets["Density"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @density.setter
    def density(self, value: float):
        try:
            addr = self.address + self._offsets["Density"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Density: {e}")

    @property
    def offset(self) -> float:
        """Смещение атмосферы."""
        try:
            addr = self.address + self._offsets["Offset"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @offset.setter
    def offset(self, value: float):
        try:
            addr = self.address + self._offsets["Offset"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Offset: {e}")

    @property
    def color(self):
        """Цвет атмосферы (Color3)."""
        from ..datastructures import Color3

        try:
            addr = self.address + self._offsets["Color"]
            r = self.mem.read_int(addr) / 255.0
            g = self.mem.read_int(addr + 4) / 255.0
            b = self.mem.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return Color3()

    @color.setter
    def color(self, value):
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["Color"]
            self.mem.write_int(addr, int(r * 255))
            self.mem.write_int(addr + 4, int(g * 255))
            self.mem.write_int(addr + 8, int(b * 255))
        except Exception as e:
            raise RuntimeError(f"Failed to write Color: {e}")

    @property
    def decay(self) -> float:
        """Decay (затухание) атмосферы."""
        try:
            addr = self.address + self._offsets["Decay"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @decay.setter
    def decay(self, value: float):
        try:
            addr = self.address + self._offsets["Decay"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Decay: {e}")

    @property
    def glare(self) -> float:
        """Glare (блик) атмосферы."""
        try:
            addr = self.address + self._offsets["Glare"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @glare.setter
    def glare(self, value: float):
        try:
            addr = self.address + self._offsets["Glare"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Glare: {e}")

    @property
    def haze(self) -> float:
        """Haze (дымка) атмосферы."""
        try:
            addr = self.address + self._offsets["Haze"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @haze.setter
    def haze(self, value: float):
        try:
            addr = self.address + self._offsets["Haze"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Haze: {e}")

    def __repr__(self):
        return (
            f"Atmosphere(density={self.density:.3f}, haze={self.haze:.2f}, "
            f"glare={self.glare:.2f}, color={self.color})"
        )
