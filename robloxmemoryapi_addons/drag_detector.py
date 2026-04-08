"""
DragDetector Module — Детектор перетаскивания Roblox

Позволяет управлять DragDetector:
  - ReferenceInstance, MaxActivationDistance
  - MaxDragAngle, MinDragAngle
  - MaxDragTranslation, MinDragTranslation
  - MaxForce, MaxTorque, Responsiveness
  - CursorIcon, ActivatedCursorIcon
"""


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

DRAG_DETECTOR_OFFSETS = {
    "ReferenceInstance": 0x208,
    "MaxActivationDistance": 0x100,
    "MaxDragAngle": 0x2c0,
    "MaxDragTranslation": 0x284,
    "MinDragAngle": 0x2cc,
    "MinDragTranslation": 0x290,
    "ActivatedCursorIcon": 0x1d8,
    "CursorIcon": 0xe0,
    "MaxForce": 0x2c4,
    "MaxTorque": 0x2c8,
    "Responsiveness": 0x2d8,
}


class DragDetectorWrapper:
    """
    Обёртка над DragDetector инстансом.

    Usage:
        # dd — RBXInstance с ClassName "DragDetector"
        dd = DragDetectorWrapper(dd_instance)
        dd.max_force = 50000
        dd.responsiveness = 10
        dd.max_drag_translation = (100, 100, 100)
    """

    def __init__(self, instance):
        self.instance = instance
        self.mem = instance.memory_module
        self._offsets = DRAG_DETECTOR_OFFSETS

    @property
    def address(self) -> int:
        return self.instance.address

    # ── Reference Instance ──────────────────────────────────

    @property
    def reference_instance(self):
        """ReferenceInstance — объект, к которому привязан DragDetector."""
        try:
            addr = self.address + self._offsets["ReferenceInstance"]
            ptr = self.mem.get_pointer(addr)
            if ptr == 0:
                return None
            from ...instance import RBXInstance
            return RBXInstance(ptr, self.mem)
        except Exception:
            return None

    @reference_instance.setter
    def reference_instance(self, value):
        try:
            addr = self.address + self._offsets["ReferenceInstance"]
            if value is None:
                self.mem.write_int64(addr, 0)
            elif hasattr(value, "address"):
                self.mem.write_int64(addr, value.address)
            else:
                self.mem.write_int64(addr, int(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write ReferenceInstance: {e}")

    # ── Activation Distance ─────────────────────────────────

    @property
    def max_activation_distance(self) -> float:
        """Максимальная дистанция активации."""
        try:
            addr = self.address + self._offsets["MaxActivationDistance"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @max_activation_distance.setter
    def max_activation_distance(self, value: float):
        try:
            addr = self.address + self._offsets["MaxActivationDistance"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxActivationDistance: {e}")

    # ── Drag Angles ─────────────────────────────────────────

    @property
    def max_drag_angle(self):
        """Максимальный угол перетаскивания (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MaxDragAngle"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @max_drag_angle.setter
    def max_drag_angle(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MaxDragAngle"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxDragAngle: {e}")

    @property
    def min_drag_angle(self):
        """Минимальный угол перетаскивания (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MinDragAngle"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @min_drag_angle.setter
    def min_drag_angle(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MinDragAngle"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MinDragAngle: {e}")

    # ── Drag Translations ───────────────────────────────────

    @property
    def max_drag_translation(self):
        """Максимальное перемещение (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MaxDragTranslation"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @max_drag_translation.setter
    def max_drag_translation(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MaxDragTranslation"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxDragTranslation: {e}")

    @property
    def min_drag_translation(self):
        """Минимальное перемещение (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MinDragTranslation"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @min_drag_translation.setter
    def min_drag_translation(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MinDragTranslation"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MinDragTranslation: {e}")

    # ── Force / Torque / Responsiveness ─────────────────────

    @property
    def max_force(self):
        """Максимальная сила (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MaxForce"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @max_force.setter
    def max_force(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MaxForce"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxForce: {e}")

    @property
    def max_torque(self):
        """Максимальный крутящий момент (Vector3)."""
        from ...datastructures import Vector3

        try:
            addr = self.address + self._offsets["MaxTorque"]
            x = self.mem.read_float(addr)
            y = self.mem.read_float(addr + 4)
            z = self.mem.read_float(addr + 8)
            return Vector3(x, y, z)
        except Exception:
            return Vector3()

    @max_torque.setter
    def max_torque(self, value):
        if hasattr(value, "X"):
            x, y, z = value.X, value.Y, value.Z
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            x, y, z = value
        else:
            raise TypeError(f"Expected Vector3 or tuple, got {type(value)}")

        try:
            addr = self.address + self._offsets["MaxTorque"]
            self.mem.write_float(addr, float(x))
            self.mem.write_float(addr + 4, float(y))
            self.mem.write_float(addr + 8, float(z))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxTorque: {e}")

    @property
    def responsiveness(self) -> float:
        """Отзывчивость."""
        try:
            addr = self.address + self._offsets["Responsiveness"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @responsiveness.setter
    def responsiveness(self, value: float):
        try:
            addr = self.address + self._offsets["Responsiveness"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write Responsiveness: {e}")

    # ── Cursor Icons ────────────────────────────────────────

    @property
    def cursor_icon(self) -> str:
        """Иконка курсора по умолчанию."""
        try:
            addr = self.address + self._offsets["CursorIcon"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @cursor_icon.setter
    def cursor_icon(self, value: str):
        try:
            addr = self.address + self._offsets["CursorIcon"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write CursorIcon: {e}")

    @property
    def activated_cursor_icon(self) -> str:
        """Иконка курсора при активации."""
        try:
            addr = self.address + self._offsets["ActivatedCursorIcon"]
            return self.mem.read_string(addr)
        except Exception:
            return ""

    @activated_cursor_icon.setter
    def activated_cursor_icon(self, value: str):
        try:
            addr = self.address + self._offsets["ActivatedCursorIcon"]
            self.mem.write_string(addr, value)
        except Exception as e:
            raise RuntimeError(f"Failed to write ActivatedCursorIcon: {e}")

    def __repr__(self):
        return (
            f"DragDetector("
            f"max_force={self.max_force}, "
            f"max_torque={self.max_torque}, "
            f"responsiveness={self.responsiveness:.1f})"
        )
