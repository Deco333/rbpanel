"""
Sky Module — Скайбокс Roblox

Позволяет:
  - Управлять всеми гранями Skybox (Bk, Dn, Ft, Lf, Rt, Up)
  - Настройка Sun/Moon (AngularSize, TextureId)
  - StarCount, SkyboxOrientation
"""

import struct


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

SKY_OFFSETS = {
    "SkyboxBk": 0x110,
    "SkyboxDn": 0x140,
    "SkyboxFt": 0x170,
    "SkyboxLf": 0x1a0,
    "SkyboxRt": 0x1d0,
    "SkyboxUp": 0x200,
    "SunAngularSize": 0x254,
    "MoonAngularSize": 0x25c,
    "SunTextureId": 0x230,
    "MoonTextureId": 0xe0,
    "SkyboxOrientation": 0x250,
    "StarCount": 0x260,
}


class SkyWrapper:
    """
    Обёртка над Sky инстансом.

    Usage:
        # sky — RBXInstance с ClassName "Sky"
        sky = SkyWrapper(sky_instance)
        print(sky.star_count)
        sky.star_count = 3000
        sky.sun_angular_size = 21
        print(sky.skybox_front)      # AssetId (str)
    """

    def __init__(self, instance):
        self.instance = instance
        self.mem = instance.memory_module
        self._offsets = SKY_OFFSETS

    @property
    def address(self) -> int:
        return self.instance.address

    # ── Skybox Textures ─────────────────────────────────────

    @property
    def skybox_back(self) -> str:
        """SkyboxBk asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxBk"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_back.setter
    def skybox_back(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxBk"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxBk: {e}")

    @property
    def skybox_down(self) -> str:
        """SkyboxDn asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxDn"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_down.setter
    def skybox_down(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxDn"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxDn: {e}")

    @property
    def skybox_front(self) -> str:
        """SkyboxFt asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxFt"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_front.setter
    def skybox_front(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxFt"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxFt: {e}")

    @property
    def skybox_left(self) -> str:
        """SkyboxLf asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxLf"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_left.setter
    def skybox_left(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxLf"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxLf: {e}")

    @property
    def skybox_right(self) -> str:
        """SkyboxRt asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxRt"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_right.setter
    def skybox_right(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxRt"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxRt: {e}")

    @property
    def skybox_up(self) -> str:
        """SkyboxUp asset ID."""
        try:
            addr = self.address + self._offsets["SkyboxUp"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @skybox_up.setter
    def skybox_up(self, value: str):
        try:
            addr = self.address + self._offsets["SkyboxUp"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxUp: {e}")

    def set_skybox(self, asset_id: str):
        """
        Установить одну текстуру для всех 6 граней скайбокса.

        Args:
            asset_id: Asset ID текстуры (rbxassetid://...)
        """
        for prop in ("skybox_back", "skybox_down", "skybox_front",
                     "skybox_left", "skybox_right", "skybox_up"):
            try:
                setattr(self, prop, asset_id)
            except Exception:
                pass

    def get_all_skybox(self) -> dict:
        """Возвращает все 6 текстур скайбокса."""
        return {
            "Back": self.skybox_back,
            "Down": self.skybox_down,
            "Front": self.skybox_front,
            "Left": self.skybox_left,
            "Right": self.skybox_right,
            "Up": self.skybox_up,
        }

    # ── Sun ─────────────────────────────────────────────────

    @property
    def sun_angular_size(self) -> float:
        """Угловой размер солнца в градусах."""
        try:
            addr = self.address + self._offsets["SunAngularSize"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @sun_angular_size.setter
    def sun_angular_size(self, value: float):
        try:
            addr = self.address + self._offsets["SunAngularSize"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write SunAngularSize: {e}")

    @property
    def sun_texture_id(self) -> str:
        """Текстура солнца."""
        try:
            addr = self.address + self._offsets["SunTextureId"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @sun_texture_id.setter
    def sun_texture_id(self, value: str):
        try:
            addr = self.address + self._offsets["SunTextureId"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write SunTextureId: {e}")

    # ── Moon ────────────────────────────────────────────────

    @property
    def moon_angular_size(self) -> float:
        """Угловой размер луны в градусах."""
        try:
            addr = self.address + self._offsets["MoonAngularSize"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @moon_angular_size.setter
    def moon_angular_size(self, value: float):
        try:
            addr = self.address + self._offsets["MoonAngularSize"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write MoonAngularSize: {e}")

    @property
    def moon_texture_id(self) -> str:
        """Текстура луны."""
        try:
            addr = self.address + self._offsets["MoonTextureId"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @moon_texture_id.setter
    def moon_texture_id(self, value: str):
        try:
            addr = self.address + self._offsets["MoonTextureId"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write MoonTextureId: {e}")

    # ── Other ───────────────────────────────────────────────

    @property
    def star_count(self) -> int:
        """Количество звёзд."""
        try:
            addr = self.address + self._offsets["StarCount"]
            return self.mem.read_int(addr)
        except Exception:
            return 0

    @star_count.setter
    def star_count(self, value: int):
        try:
            addr = self.address + self._offsets["StarCount"]
            self.mem.write_int(addr, int(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write StarCount: {e}")

    @property
    def skybox_orientation(self) -> float:
        """Ориентация скайбокса в градусах."""
        try:
            addr = self.address + self._offsets["SkyboxOrientation"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @skybox_orientation.setter
    def skybox_orientation(self, value: float):
        try:
            addr = self.address + self._offsets["SkyboxOrientation"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write SkyboxOrientation: {e}")

    def __repr__(self):
        return (
            f"Sky(star_count={self.star_count}, "
            f"sun_size={self.sun_angular_size:.1f}, "
            f"moon_size={self.moon_angular_size:.1f})"
        )
