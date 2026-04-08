"""
Enhanced Instance — Новые свойства для существующих классов

Расширяет RBXInstance дополнительными свойствами, которые есть
в оффсетах, но не реализованы в оригинальной библиотеке:

Новые свойства RBXInstance:
  - CastShadow (BasePart)
  - Shape (BasePart)
  - Material (BasePart/Primitive)
  - Scale (Model)
  - Scale (SpecialMesh)
  - MeshId (SpecialMesh)
  - Position (Attachment — уже есть, но для Attachment по другому оффсету)
  - TextureId (Decal / Texture)
  - AssetId (UnionOperation)
  - KeyCode (ProximityPrompt)
  - GamepadKeyCode (ProximityPrompt)
  - LightColor (Lighting)
  - GradientTop / GradientBottom / LightDirection (Lighting)
  - ColorMap, EmissiveMaskContent, EmissiveTint, MetalnessMap, NormalMap, RoughnessMap (SurfaceAppearance)
  - Enabled (Post-processing effects: Bloom, DoF, SunRays, ColorCorrection, ColorGrading, Blur)

Новые классы-обёртки:
  - TerrainWrapper, MaterialColors, AtmosphereWrapper
  - SkyWrapper
  - BloomEffectWrapper, DepthOfFieldEffectWrapper, SunRaysEffectWrapper
  - DragDetectorWrapper
  - PlayerMouseWrapper
"""

import struct


# ──────────────────────────────────────────────────────────────
# Offsets для новых свойств
# ──────────────────────────────────────────────────────────────

# BasePart
BASE_PART_EXTRA = {
    "CastShadow": 0xf5,
    "Shape": 0x1b1,
}

# Primitive
PRIMITIVE_EXTRA = {
    "Material": 0x0,
}

# Model
MODEL_EXTRA = {
    "Scale": 0x164,
}

# SpecialMesh
SPECIAL_MESH = {
    "Scale": 0xdc,
    "MeshId": 0x108,
}

# Attachment
ATTACHMENT_EXTRA = {
    "Position": 0xdc,
}

# Decal / Texture
TEXTURES = {
    "Texture": 0x198,
}

# UnionOperation
UNION_OPERATION = {
    "AssetId": 0x2e0,
}

# ProximityPrompt (дополнительно к существующим)
PROXIMITY_PROMPT_EXTRA = {
    "KeyCode": 0x144,
    "GamepadKeyCode": 0x13c,
}

# Lighting (дополнительно к существующим)
LIGHTING_EXTRA = {
    "LightColor": 0x15c,
    "GradientTop": 0x150,
    "LightDirection": 0x168,
    "GradientBottom": 0x194,
}

# SurfaceAppearance (дополнительно к существующим)
SURFACE_APPEARANCE_EXTRA = {
    "ColorMap": 0xe0,
    "EmissiveMaskContent": 0x110,
    "EmissiveTint": 0x294,
    "MetalnessMap": 0x140,
    "NormalMap": 0x170,
    "RoughnessMap": 0x1a0,
}

# Post-processing — Enabled у всех на 0xc8
POST_PROCESS_ENABLED = 0xc8


def _get_class_name(instance) -> str:
    """Безопасное получение ClassName."""
    try:
        return instance.ClassName
    except Exception:
        return ""


def _ensure_writable(instance):
    """Проверяет, что запись разрешена."""
    if hasattr(instance, "_ensure_writable"):
        instance._ensure_writable()


# ──────────────────────────────────────────────────────────────
# Monkey-patch свойства на RBXInstance
# ──────────────────────────────────────────────────────────────

_patch_applied = False


def patch_rbx_instance():
    """
    Применяет патч к RBXInstance, добавляя новые свойства.

    Безопасно вызывать несколько раз — патч применяется только один раз.
    """
    global _patch_applied
    if _patch_applied:
        return

    try:
        from robloxmemoryapi.utils.rbx.instance import RBXInstance
        from robloxmemoryapi.utils.rbx.datastructures import Vector3, Color3
    except ImportError:
        # Если импорт не найден, значит библиотека установлена по-другому
        try:
            import importlib
            # Попытка найти через разные пути
            for mod_path in [
                "robloxmemoryapi.utils.rbx.instance",
                "robloxmemoryapi.instance",
            ]:
                try:
                    mod = importlib.import_module(mod_path)
                    RBXInstance = getattr(mod, "RBXInstance")
                    datastructures = importlib.import_module(
                        mod_path.rsplit(".", 1)[0] + ".datastructures"
                    )
                    Vector3 = datastructures.Vector3
                    Color3 = datastructures.Color3
                    break
                except (ImportError, AttributeError):
                    continue
            else:
                raise ImportError("Cannot find RBXInstance class")
        except Exception:
            return

    # ── BasePart: CastShadow ────────────────────────────────

    def _get_cast_shadow(self):
        cn = _get_class_name(self)
        if cn not in ("BasePart", "Part", "MeshPart", "WedgePart", "CornerWedgePart",
                      "Terrain", "UnionOperation", "NegateOperation",
                      "Seat", "SpawnLocation", "VehicleSeat"):
            return None
        try:
            return self.memory_module.read_bool(
                self.address + BASE_PART_EXTRA["CastShadow"]
            )
        except Exception:
            return None

    def _set_cast_shadow(self, value):
        _ensure_writable(self)
        self.memory_module.write_bool(
            self.address + BASE_PART_EXTRA["CastShadow"], bool(value)
        )

    # ── BasePart: Shape ────────────────────────────────────

    def _get_shape(self):
        cn = _get_class_name(self)
        if cn != "BasePart":
            return None
        try:
            return self.memory_module.read_int(self.address + BASE_PART_EXTRA["Shape"])
        except Exception:
            return None

    # ── BasePart/Primitive: Material ────────────────────────

    def _get_material(self):
        cn = _get_class_name(self)
        if cn not in ("BasePart", "Part", "MeshPart", "WedgePart", "CornerWedgePart",
                      "Terrain", "UnionOperation"):
            return None
        try:
            prim_addr = self.memory_module.get_pointer(
                self.address + 0x148  # BasePart::Primitive
            )
            if prim_addr == 0:
                return None
            return self.memory_module.read_int(prim_addr + PRIMITIVE_EXTRA["Material"])
        except Exception:
            return None

    def _set_material(self, value):
        _ensure_writable(self)
        prim_addr = self.memory_module.get_pointer(self.address + 0x148)
        if prim_addr == 0:
            raise RuntimeError("Primitive pointer is null")
        self.memory_module.write_int(prim_addr + PRIMITIVE_EXTRA["Material"], int(value))

    # ── Model: Scale ────────────────────────────────────────

    def _get_model_scale(self):
        if _get_class_name(self) != "Model":
            return None
        try:
            return self.memory_module.read_float(self.address + MODEL_EXTRA["Scale"])
        except Exception:
            return None

    def _set_model_scale(self, value):
        _ensure_writable(self)
        self.memory_module.write_float(self.address + MODEL_EXTRA["Scale"], float(value))

    # ── SpecialMesh: Scale ──────────────────────────────────

    def _get_specialmesh_scale(self):
        if _get_class_name(self) != "SpecialMesh":
            return None
        try:
            addr = self.address + SPECIAL_MESH["Scale"]
            x = self.memory_module.read_float(addr)
            y = self.memory_module.read_float(addr + 4)
            z = self.memory_module.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return None

    def _set_specialmesh_scale(self, value):
        _ensure_writable(self)
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")
        addr = self.address + SPECIAL_MESH["Scale"]
        self.memory_module.write_float(addr, float(x))
        self.memory_module.write_float(addr + 4, float(y))
        self.memory_module.write_float(addr + 8, float(z))

    # ── SpecialMesh: MeshId ─────────────────────────────────

    def _get_specialmesh_meshid(self):
        if _get_class_name(self) != "SpecialMesh":
            return None
        try:
            return self.memory_module.read_string(self.address + SPECIAL_MESH["MeshId"])
        except Exception:
            return ""

    def _set_specialmesh_meshid(self, value):
        _ensure_writable(self)
        self.memory_module.write_string(self.address + SPECIAL_MESH["MeshId"], str(value))

    # ── Decal / Texture: Texture ────────────────────────────

    def _get_texture(self):
        if _get_class_name(self) not in ("Decal", "Texture"):
            return None
        try:
            return self.memory_module.read_string(self.address + TEXTURES["Texture"])
        except Exception:
            return ""

    def _set_texture(self, value):
        _ensure_writable(self)
        self.memory_module.write_string(self.address + TEXTURES["Texture"], str(value))

    # ── UnionOperation: AssetId ─────────────────────────────

    def _get_asset_id(self):
        if _get_class_name(self) != "UnionOperation":
            return None
        try:
            return self.memory_module.read_string(self.address + UNION_OPERATION["AssetId"])
        except Exception:
            return ""

    def _set_asset_id(self, value):
        _ensure_writable(self)
        self.memory_module.write_string(self.address + UNION_OPERATION["AssetId"], str(value))

    # ── ProximityPrompt: KeyCode / GamepadKeyCode ───────────

    def _get_keycode(self):
        if _get_class_name(self) != "ProximityPrompt":
            return None
        try:
            return self.memory_module.read_int(self.address + PROXIMITY_PROMPT_EXTRA["KeyCode"])
        except Exception:
            return None

    def _get_gamepad_keycode(self):
        if _get_class_name(self) != "ProximityPrompt":
            return None
        try:
            return self.memory_module.read_int(
                self.address + PROXIMITY_PROMPT_EXTRA["GamepadKeyCode"]
            )
        except Exception:
            return None

    # ── Lighting: LightColor, GradientTop, etc. ─────────────

    def _get_light_color(self):
        if _get_class_name(self) != "Lighting":
            return None
        try:
            addr = self.address + LIGHTING_EXTRA["LightColor"]
            r = self.memory_module.read_int(addr) / 255.0
            g = self.memory_module.read_int(addr + 4) / 255.0
            b = self.memory_module.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return None

    def _set_light_color(self, value):
        _ensure_writable(self)
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")
        addr = self.address + LIGHTING_EXTRA["LightColor"]
        self.memory_module.write_int(addr, int(r * 255))
        self.memory_module.write_int(addr + 4, int(g * 255))
        self.memory_module.write_int(addr + 8, int(b * 255))

    def _get_gradient_top(self):
        if _get_class_name(self) != "Lighting":
            return None
        try:
            addr = self.address + LIGHTING_EXTRA["GradientTop"]
            r = self.memory_module.read_int(addr) / 255.0
            g = self.memory_module.read_int(addr + 4) / 255.0
            b = self.memory_module.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return None

    def _set_gradient_top(self, value):
        _ensure_writable(self)
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")
        addr = self.address + LIGHTING_EXTRA["GradientTop"]
        self.memory_module.write_int(addr, int(r * 255))
        self.memory_module.write_int(addr + 4, int(g * 255))
        self.memory_module.write_int(addr + 8, int(b * 255))

    def _get_gradient_bottom(self):
        if _get_class_name(self) != "Lighting":
            return None
        try:
            addr = self.address + LIGHTING_EXTRA["GradientBottom"]
            r = self.memory_module.read_int(addr) / 255.0
            g = self.memory_module.read_int(addr + 4) / 255.0
            b = self.memory_module.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return None

    def _set_gradient_bottom(self, value):
        _ensure_writable(self)
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")
        addr = self.address + LIGHTING_EXTRA["GradientBottom"]
        self.memory_module.write_int(addr, int(r * 255))
        self.memory_module.write_int(addr + 4, int(g * 255))
        self.memory_module.write_int(addr + 8, int(b * 255))

    def _get_light_direction(self):
        if _get_class_name(self) != "Lighting":
            return None
        try:
            addr = self.address + LIGHTING_EXTRA["LightDirection"]
            x = self.memory_module.read_float(addr)
            y = self.memory_module.read_float(addr + 4)
            z = self.memory_module.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return None

    # ── SurfaceAppearance: Additional Properties ────────────

    def _get_color_map(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            return self.memory_module.read_string(
                self.address + SURFACE_APPEARANCE_EXTRA["ColorMap"]
            )
        except Exception:
            return ""

    def _get_emissive_mask_content(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            return self.memory_module.read_string(
                self.address + SURFACE_APPEARANCE_EXTRA["EmissiveMaskContent"]
            )
        except Exception:
            return ""

    def _get_emissive_tint(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            addr = self.address + SURFACE_APPEARANCE_EXTRA["EmissiveTint"]
            r = self.memory_module.read_int(addr) / 255.0
            g = self.memory_module.read_int(addr + 4) / 255.0
            b = self.memory_module.read_int(addr + 8) / 255.0
            return Color3(r, g, b)
        except Exception:
            return None

    def _set_emissive_tint(self, value):
        _ensure_writable(self)
        if hasattr(value, "R"):
            r, g, b = value.R, value.G, value.B
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            r, g, b = value
        else:
            raise TypeError(f"Expected Color3 or tuple, got {type(value)}")
        addr = self.address + SURFACE_APPEARANCE_EXTRA["EmissiveTint"]
        self.memory_module.write_int(addr, int(r * 255))
        self.memory_module.write_int(addr + 4, int(g * 255))
        self.memory_module.write_int(addr + 8, int(b * 255))

    def _get_metalness_map(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            return self.memory_module.read_string(
                self.address + SURFACE_APPEARANCE_EXTRA["MetalnessMap"]
            )
        except Exception:
            return ""

    def _get_normal_map(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            return self.memory_module.read_string(
                self.address + SURFACE_APPEARANCE_EXTRA["NormalMap"]
            )
        except Exception:
            return ""

    def _get_roughness_map(self):
        if _get_class_name(self) != "SurfaceAppearance":
            return None
        try:
            return self.memory_module.read_string(
                self.address + SURFACE_APPEARANCE_EXTRA["RoughnessMap"]
            )
        except Exception:
            return ""

    # ── Post-Processing: Enabled (universal for all effects) ─

    def _get_post_enabled(self):
        cn = _get_class_name(self)
        if cn not in ("BloomEffect", "DepthOfFieldEffect", "SunRaysEffect",
                      "ColorCorrectionEffect", "ColorGradingEffect", "BlurEffect"):
            return None
        try:
            return self.memory_module.read_bool(self.address + POST_PROCESS_ENABLED)
        except Exception:
            return None

    def _set_post_enabled(self, value):
        _ensure_writable(self)
        self.memory_module.write_bool(self.address + POST_PROCESS_ENABLED, bool(value))

    # ═══════════════════════════════════════════════════════════
    # Применяем патчи к классу
    # ═══════════════════════════════════════════════════════════

    # BasePart
    RBXInstance.CastShadow = property(_get_cast_shadow, _set_cast_shadow)
    RBXInstance.Shape = property(_get_shape)
    RBXInstance.Material = property(_get_material, _set_material)

    # Model
    RBXInstance.ModelScale = property(_get_model_scale, _set_model_scale)

    # SpecialMesh
    RBXInstance.MeshScale = property(_get_specialmesh_scale, _set_specialmesh_scale)
    RBXInstance.MeshId = property(_get_specialmesh_meshid, _set_specialmesh_meshid)

    # Decal / Texture
    RBXInstance.Texture = property(_get_texture, _set_texture)

    # UnionOperation
    RBXInstance.AssetId = property(_get_asset_id, _set_asset_id)

    # ProximityPrompt
    RBXInstance.KeyCode = property(_get_keycode)
    RBXInstance.GamepadKeyCode = property(_get_gamepad_keycode)

    # Lighting
    RBXInstance.LightColor = property(_get_light_color, _set_light_color)
    RBXInstance.GradientTop = property(_get_gradient_top, _set_gradient_top)
    RBXInstance.GradientBottom = property(_get_gradient_bottom, _set_gradient_bottom)
    RBXInstance.LightDirection = property(_get_light_direction)

    # SurfaceAppearance
    RBXInstance.ColorMap = property(_get_color_map)
    RBXInstance.EmissiveMaskContent = property(_get_emissive_mask_content)
    RBXInstance.EmissiveTint = property(_get_emissive_tint, _set_emissive_tint)
    RBXInstance.MetalnessMap = property(_get_metalness_map)
    RBXInstance.NormalMap = property(_get_normal_map)
    RBXInstance.RoughnessMap = property(_get_roughness_map)

    # Post-processing enabled (универсальное для всех эффектов)
    RBXInstance.PostEnabled = property(_get_post_enabled, _set_post_enabled)

    _patch_applied = True
