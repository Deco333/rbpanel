"""
Post-Processing Module — Эффекты пост-обработки Roblox

Позволяет управлять:
  - BloomEffect (Intensity, Size, Threshold)
  - DepthOfFieldEffect (FocusDistance, FarIntensity, NearIntensity, InFocusRadius)
  - SunRaysEffect (Intensity, Spread)
"""


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

BLOOM_OFFSETS = {
    "Intensity": 0xd0,
    "Size": 0xd4,
    "Threshold": 0xd8,
    "Enabled": 0xc8,
}

DOF_OFFSETS = {
    "FocusDistance": 0xd4,
    "FarIntensity": 0xd0,
    "NearIntensity": 0xdc,
    "InFocusRadius": 0xd8,
    "Enabled": 0xc8,
}

SUNRAYS_OFFSETS = {
    "Intensity": 0xd0,
    "Spread": 0xd4,
    "Enabled": 0xc8,
}


class BasePostEffect:
    """Базовый класс для пост-эффектов."""

    def __init__(self, instance, offsets: dict):
        self.instance = instance
        self.mem = instance.memory_module
        self._offsets = offsets

    @property
    def address(self) -> int:
        return self.instance.address

    @property
    def enabled(self) -> bool:
        """Включён ли эффект."""
        try:
            addr = self.address + self._offsets["Enabled"]
            return self.mem.read_bool(addr)
        except Exception:
            return False

    @enabled.setter
    def enabled(self, value: bool):
        try:
            addr = self.address + self._offsets["Enabled"]
            self.mem.write_bool(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write Enabled: {e}")


class BloomEffectWrapper(BasePostEffect):
    """
    Обёртка над BloomEffect.

    Usage:
        # bloom — RBXInstance с ClassName "BloomEffect"
        bloom = BloomEffectWrapper(bloom_instance)
        bloom.intensity = 0.5
        bloom.size = 24
        bloom.threshold = 0.8
        bloom.enabled = True
    """

    def __init__(self, instance):
        super().__init__(instance, BLOOM_OFFSETS)

    @property
    def intensity(self) -> float:
        """Интенсивность bloom."""
        try:
            addr = self.address + self._offsets["Intensity"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @intensity.setter
    def intensity(self, value: float):
        try:
            addr = self.address + self._offsets["Intensity"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Intensity: {e}")

    @property
    def size(self) -> float:
        """Размер bloom."""
        try:
            addr = self.address + self._offsets["Size"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @size.setter
    def size(self, value: float):
        try:
            addr = self.address + self._offsets["Size"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Size: {e}")

    @property
    def threshold(self) -> float:
        """Порог bloom — яркость, при которой включается."""
        try:
            addr = self.address + self._offsets["Threshold"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @threshold.setter
    def threshold(self, value: float):
        try:
            addr = self.address + self._offsets["Threshold"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Threshold: {e}")

    def __repr__(self):
        return (
            f"BloomEffect(intensity={self.intensity:.2f}, "
            f"size={self.size:.1f}, threshold={self.threshold:.2f}, "
            f"enabled={self.enabled})"
        )


class DepthOfFieldEffectWrapper(BasePostEffect):
    """
    Обёртка над DepthOfFieldEffect.

    Usage:
        dof = DepthOfFieldEffectWrapper(dof_instance)
        dof.focus_distance = 20
        dof.far_intensity = 0.5
        dof.near_intensity = 0.3
        dof.in_focus_radius = 10
    """

    def __init__(self, instance):
        super().__init__(instance, DOF_OFFSETS)

    @property
    def focus_distance(self) -> float:
        """Дистанция фокуса в студиях."""
        try:
            addr = self.address + self._offsets["FocusDistance"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @focus_distance.setter
    def focus_distance(self, value: float):
        try:
            addr = self.address + self._offsets["FocusDistance"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write FocusDistance: {e}")

    @property
    def far_intensity(self) -> float:
        """Интенсивность размытия далеко."""
        try:
            addr = self.address + self._offsets["FarIntensity"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @far_intensity.setter
    def far_intensity(self, value: float):
        try:
            addr = self.address + self._offsets["FarIntensity"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write FarIntensity: {e}")

    @property
    def near_intensity(self) -> float:
        """Интенсивность размытия близко."""
        try:
            addr = self.address + self._offsets["NearIntensity"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @near_intensity.setter
    def near_intensity(self, value: float):
        try:
            addr = self.address + self._offsets["NearIntensity"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write NearIntensity: {e}")

    @property
    def in_focus_radius(self) -> float:
        """Радиус зоны в фокусе."""
        try:
            addr = self.address + self._offsets["InFocusRadius"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @in_focus_radius.setter
    def in_focus_radius(self, value: float):
        try:
            addr = self.address + self._offsets["InFocusRadius"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write InFocusRadius: {e}")

    def __repr__(self):
        return (
            f"DepthOfFieldEffect(focus={self.focus_distance:.1f}, "
            f"far={self.far_intensity:.2f}, near={self.near_intensity:.2f}, "
            f"radius={self.in_focus_radius:.1f}, enabled={self.enabled})"
        )


class SunRaysEffectWrapper(BasePostEffect):
    """
    Обёртка над SunRaysEffect.

    Usage:
        sr = SunRaysEffectWrapper(sunrays_instance)
        sr.intensity = 0.5
        sr.spread = 0.8
        sr.enabled = True
    """

    def __init__(self, instance):
        super().__init__(instance, SUNRAYS_OFFSETS)

    @property
    def intensity(self) -> float:
        """Интенсивность лучей солнца."""
        try:
            addr = self.address + self._offsets["Intensity"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @intensity.setter
    def intensity(self, value: float):
        try:
            addr = self.address + self._offsets["Intensity"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Intensity: {e}")

    @property
    def spread(self) -> float:
        """Разброс лучей."""
        try:
            addr = self.address + self._offsets["Spread"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @spread.setter
    def spread(self, value: float):
        try:
            addr = self.address + self._offsets["Spread"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Spread: {e}")

    def __repr__(self):
        return (
            f"SunRaysEffect(intensity={self.intensity:.2f}, "
            f"spread={self.spread:.2f}, enabled={self.enabled})"
        )
