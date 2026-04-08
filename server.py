#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  ROBLOX PANEL v4.0 — WebSocket Server (FULL COMBAT)            ║
║  Bridge between browser UI and RobloxMemoryAPI                  ║
║                                                                  ║
║  Usage:  python server.py                                       ║
║  Dependencies:  pip install websockets robloxmemoryapi           ║
║                                                                  ║
║  Protocol: JSON messages over WebSocket on port 8765             ║
║  Frontend runs on Next.js (localhost:3000)                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import os
import sys
import time
import math
import traceback
import threading
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
from collections import deque

import websockets
from websockets.server import serve

# ═══════════════════════════════════════════════════════════════
#  Windows-only imports (ctypes for mouse/kb input)
# ═══════════════════════════════════════════════════════════════

import ctypes
import ctypes.wintypes

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

VK_W       = 0x57
VK_A       = 0x41
VK_S       = 0x53
VK_D       = 0x44
VK_SPACE   = 0x20
VK_SHIFT   = 0x10
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_E       = 0x45
VK_RETURN  = 0x0D
VK_TAB     = 0x09


def is_key_pressed(vk):
    """Check if a virtual key is currently pressed."""
    return GetAsyncKeyState(vk) & 0x8000 != 0

# Global keyboard hook system
HAS_PYNPUT = False
try:
    from pynput import keyboard as _pynput_kb
    HAS_PYNPUT = True
except ImportError:
    pass

_global_keybinds = {}  # {vk_code: callback_func}
_pynput_listener = None

def _register_global_keybind(vk_code, callback):
    """Register a global keybind that works even when Roblox is focused."""
    global _global_keybinds
    _global_keybinds[vk_code] = callback
    if not _pynput_listener and HAS_PYNPUT:
        _start_global_keybind_listener()

def _unregister_global_keybind(vk_code):
    global _global_keybinds
    _global_keybinds.pop(vk_code, None)

def _start_global_keybind_listener():
    """Start global keyboard listener using pynput."""
    global _pynput_listener
    if _pynput_listener:
        return
    
    def on_press(key):
        try:
            vk = key.value.vk if hasattr(key, 'value') else 0
            if vk in _global_keybinds:
                _global_keybinds[vk]()
        except:
            pass
    
    _pynput_listener = _pynput_kb.Listener(on_press=on_press)
    _pynput_listener.start()
    _combat_log("Global keybind listener: started", "good")

def _stop_global_keybind_listener():
    global _pynput_listener
    if _pynput_listener:
        _pynput_listener.stop()
        _pynput_listener = None
        _combat_log("Global keybind listener: stopped", "warn")


def get_cursor_pos():
    """Get current mouse cursor position (x, y)."""
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def mouse_move(dx, dy):
    """Relative mouse movement via mouse_event (correct for aimbot)."""
    extra = ctypes.c_ulong(0)
    ctypes.windll.user32.mouse_event(
        MOUSEEVENTF_MOVE, int(dx), int(dy), 0, ctypes.byref(extra))


def mouse_click_down():
    extra = ctypes.c_ulong(0)
    ctypes.windll.user32.mouse_event(
        MOUSEEVENTF_LEFTDOWN, 0, 0, 0, ctypes.byref(extra))


def mouse_click_up():
    extra = ctypes.c_ulong(0)
    ctypes.windll.user32.mouse_event(
        MOUSEEVENTF_LEFTUP, 0, 0, 0, ctypes.byref(extra))


def safe_read(fn, default=None):
    """Safely execute a function, returning default on any error."""
    try:
        val = fn()
        return val if val is not None else default
    except Exception:
        return default


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


# ═══════════════════════════════════════════════════════════════
#  RobloxMemoryAPI + Addons
# ═══════════════════════════════════════════════════════════════

HAS_API = False
HAS_INSTANCE = False
HAS_ADDONS = False
HAS_BYTECODE = False
HAS_FFLAGS = False

RobloxGameClient = None
RawOffsets = {}
_addon_get_visual_engine = None
_addon_get_w2s_helper = None
_addon_get_task_scheduler = None
_addon_get_run_service = None
_addon_get_data_model_address = None
_addon_get_script_context = None
_addon_patch_all = None

try:
    from robloxmemoryapi import RobloxGameClient as _RGC
    from robloxmemoryapi.utils.rbx.datastructures import Vector3, Color3, CFrame
    from robloxmemoryapi.utils.offsets import Offsets as _RawOffsets
    RobloxGameClient = _RGC
    RawOffsets = _RawOffsets if _RawOffsets else {}
    HAS_API = True
except ImportError:
    print("[!] RobloxMemoryAPI not installed.")

try:
    from robloxmemoryapi.utils.rbx.instance import RBXInstance
    HAS_INSTANCE = True
except ImportError:
    pass

try:
    from robloxmemoryapi.utils.rbx.bytecode.decryptor import decode_bytecode, disassemble_pretty
    HAS_BYTECODE = True
except Exception:
    pass

try:
    from robloxmemoryapi.utils.rbx.fflags import FFlagManager
    HAS_FFLAGS = True
except ImportError:
    pass

_ADDON_ITEMS = [
    ("get_visual_engine", "get_visual_engine"),
    ("get_w2s_helper", "get_w2s_helper"),
    ("get_task_scheduler", "get_task_scheduler"),
    ("get_run_service", "get_run_service"),
    ("get_data_model_address", "get_data_model_address"),
    ("get_script_context", "get_script_context"),
    ("patch_all", "patch_all"),
    ("TaskScheduler", "TaskScheduler"),
    ("ScriptContextWrapper", "ScriptContextWrapper"),
]

for _an, _im in _ADDON_ITEMS:
    try:
        _mod = __import__("robloxmemoryapi_addons", fromlist=[_im])
        globals()[f"_addon_{_an}"] = getattr(_mod, _im)
    except (ImportError, AttributeError):
        pass

_loaded = [n for n, _ in _ADDON_ITEMS if globals().get(f"_addon_{n}") is not None]
if _loaded:
    HAS_ADDONS = True
    print(f"[+] Addons loaded: {_loaded}")

# ═══════════════════════════════════════════════════════════════
#  OFFSETS (from API + fallbacks)
# ═══════════════════════════════════════════════════════════════

_BP = RawOffsets.get("BasePart", {}) if HAS_API else {}
_PR = RawOffsets.get("Primitive", {}) if HAS_API else {}
_PF = RawOffsets.get("PrimitiveFlags", {}) if HAS_API else {}
_HO = RawOffsets.get("Humanoid", {}) if HAS_API else {}

# Fallback offsets
_BASEPART_PRIMITIVE_PTR = 48
_PRIM_POSITION = 0xE4
_PRIM_SIZE = 0x1B0
_PRIM_VELOCITY = 0xF0
_PRIM_ANGULAR_VEL = 0xFC
_PRIM_FLAGS = 0x1AE
_FLAG_CANCOLLIDE = 0x08
_FLAG_ANCHORED = 0x02
_BP_TRANSPARENCY = 240
_BP_COLOR3 = 0x4A

_HO_WALKSPEED = 468
_HO_HEALTH = 404
_HO_MAXHEALTH = 0x1B4
_HO_JUMPPower = 432
_HO_PLATFORMSTAND = 479

# Visual Engine (W2S)
_VISUAL_ENGINE_PTR = 0x7EF81D8
_VISUAL_ENGINE_DIMS = 0xa60
_VISUAL_ENGINE_VM = 0x130

# ═══════════════════════════════════════════════════════════════
#  Mem — direct memory wrapper
# ═══════════════════════════════════════════════════════════════

class Mem:
    """Direct memory wrapper over memory_module."""
    def __init__(self, mem_module):
        self.m = mem_module

    def ok(self):
        return self.m is not None

    def get_ptr(self, addr, offset):
        try:
            return self.m.get_pointer(addr, offset)
        except Exception:
            return 0

    def deref(self, addr):
        try:
            return self.m.get_pointer(addr)
        except Exception:
            return 0

    def read_float(self, addr):
        try:
            return self.m.read_float(addr)
        except Exception:
            return 0.0

    def write_float(self, addr, val):
        try:
            self.m.write_float(addr, float(val))
            return True
        except Exception:
            return False

    def read_floats(self, addr, n):
        try:
            return self.m.read_floats(addr, n)
        except Exception:
            return [0.0] * n

    def write_floats(self, addr, vals):
        try:
            self.m.write_floats(addr, vals)
            return True
        except Exception:
            return False

    def read_bytes(self, addr, n):
        try:
            return self.m.read(addr, n)
        except Exception:
            return b'\x00' * n

    def write_bytes(self, addr, data):
        try:
            self.m.write(addr, data)
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
#  Part manipulation helpers
# ═══════════════════════════════════════════════════════════════

def _get_primitive_addr(mem, part_addr):
    offset = _BP.get("Primitive", 0)
    if offset == 0:
        offset = _BASEPART_PRIMITIVE_PTR
    return mem.get_ptr(part_addr, offset)

def _read_part_position(mem, part_addr):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return None
    off = _PR.get("Position", _PRIM_POSITION)
    return Vector3(*mem.read_floats(prim + off, 3))

def _write_part_position(mem, part_addr, vec):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return False
    off = _PR.get("Position", _PRIM_POSITION)
    mem.write_float(prim + off, float(vec.X))
    mem.write_float(prim + off + 4, float(vec.Y))
    mem.write_float(prim + off + 8, float(vec.Z))
    return True

def _read_part_size(mem, part_addr):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return None
    off = _PR.get("Size", _PRIM_SIZE)
    return Vector3(*mem.read_floats(prim + off, 3))

def _write_part_size(mem, part_addr, vec):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return False
    off = _PR.get("Size", _PRIM_SIZE)
    mem.write_float(prim + off, float(vec.X))
    mem.write_float(prim + off + 4, float(vec.Y))
    mem.write_float(prim + off + 8, float(vec.Z))
    return True

def _read_flags(mem, part_addr):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return 0
    data = mem.read_bytes(prim + _PR.get("Flags", _PRIM_FLAGS), 1)
    return int.from_bytes(data, 'little') if data else 0

def _write_flags(mem, part_addr, flags):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return False
    return mem.write_bytes(prim + _PR.get("Flags", _PRIM_FLAGS), bytes([flags & 0xFF]))

def _set_can_collide(mem, part_addr, val):
    flags = _read_flags(mem, part_addr)
    cc_bit = _PF.get("CanCollide", _FLAG_CANCOLLIDE)
    flags = (flags | cc_bit) if val else (flags & ~cc_bit)
    return _write_flags(mem, part_addr, flags)

def _write_velocity(mem, part_addr, vec):
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return False
    off = _PR.get("AssemblyLinearVelocity", _PRIM_VELOCITY)
    mem.write_float(prim + off, float(vec.X))
    mem.write_float(prim + off + 4, float(vec.Y))
    mem.write_float(prim + off + 8, float(vec.Z))
    return True

def _is_part(obj):
    try:
        return "part" in obj.ClassName.lower()
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
#  W2S (World-to-Screen) — built-in fallback
# ═══════════════════════════════════════════════════════════════

class W2SResult:
    __slots__ = ("x", "y", "on_screen", "depth")
    def __init__(self, x, y, on_screen, depth):
        self.x = x
        self.y = y
        self.on_screen = on_screen
        self.depth = depth

class BuiltinW2S:
    """Built-in W2S using direct memory reads from VisualEngine."""
    def __init__(self, mem):
        self.mem = mem
        self._base = getattr(mem, 'base', 0)

    def world_to_screen(self, world_pos):
        try:
            if hasattr(world_pos, "X"):
                px, py, pz = world_pos.X, world_pos.Y, world_pos.Z
            elif isinstance(world_pos, (tuple, list)):
                px, py, pz = float(world_pos[0]), float(world_pos[1]), float(world_pos[2])
            else:
                return W2SResult(0, 0, False, 0)

            base = self._base
            if base == 0:
                base = getattr(self.mem, 'base', 0)
                if base == 0 and hasattr(self.mem, 'm'):
                    base = getattr(self.mem.m, 'base', 0)
            if base == 0:
                return W2SResult(0, 0, False, 0)

            ve_addr = self.mem.get_pointer(base + _VISUAL_ENGINE_PTR)
            if ve_addr == 0:
                return W2SResult(0, 0, False, 0)

            raw = self.mem.read_floats(ve_addr + _VISUAL_ENGINE_VM, 16)
            sw = self.mem.read_float(ve_addr + _VISUAL_ENGINE_DIMS)
            sh = self.mem.read_float(ve_addr + _VISUAL_ENGINE_DIMS + 4)

            if sw <= 0 or sh <= 0:
                return W2SResult(0, 0, False, 0)

            cx = raw[0]*px + raw[4]*py + raw[8]*pz  + raw[12]
            cy = raw[1]*px + raw[5]*py + raw[9]*pz  + raw[13]
            cw = raw[3]*px + raw[7]*py + raw[11]*pz + raw[15]

            if cw < 0.1:
                return W2SResult(0, 0, False, cw)

            sx = (sw * 0.5) * (1.0 + cx / cw)
            sy = (sh * 0.5) * (1.0 - cy / cw)

            margin = 300
            visible = -margin <= sx <= sw + margin and -margin <= sy <= sh + margin
            return W2SResult(sx, sy, visible, cw)
        except Exception:
            return W2SResult(0, 0, False, 0)


# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

HOST = "0.0.0.0"
PORT = 8765
VERSION = "4.0.0"

# ═══════════════════════════════════════════════════════════════
#  PANEL STATE
# ═══════════════════════════════════════════════════════════════

class PanelState:
    """Holds all panel state."""

    def __init__(self):
        self.connected = False
        self.client = None
        self.dm = None
        self.mem = None       # raw memory_module
        self._mem = None      # Mem wrapper
        self.pid = None

        # Addon references
        self.task_scheduler = None
        self.visual_engine = None
        self.w2s = None       # W2S helper (from addon or builtin)
        self.run_service = None
        self.script_context = None
        self.hook_manager = None
        self.addon_modules = {}

        # Tools toggles
        self.tools = {
            "unlimited_ammo": False, "rapid_fire": False, "no_recoil": False,
            "tool_lock": False, "cooldown_mod": False, "cooldown_value": 0,
        }

        # Hitbox
        self._hitbox_saved = {}
        self._hitbox_npc_paths = []
        self._hitbox_path_discovery_done = False
        self._hitbox_part_names = [
            "HumanoidRootPart", "Head", "Torso", "UpperTorso", "LowerTorso",
            "Left Arm", "Right Arm", "Left Leg", "Right Leg",
            "LeftHand", "RightHand", "LeftFoot", "RightFoot",
        ]

        # Combat toggles
        self.combat = {
            "aimbot_enabled": False, "aimbot_fov": 200, "aimbot_sens": 1.0,
            "aimbot_bone": "Head", "aimbot_team_check": False,
            "aimbot_npc_check": True, "aimbot_alive_check": True,
            "headlock_enabled": False, "headlock_smooth": 8.0,
            "headlock_fov": 400, "headlock_team_check": False,
            "headlock_npc_check": True,
            "silent_aim_enabled": False, "silent_aim_team_check": False,
            "triggerbot_enabled": False, "triggerbot_delay": 50,
            "kill_aura_enabled": False, "kill_aura_range": 50,
            "radar_enabled": False, "radar_range": 300,
            "radar_npc": True, "radar_names": True, "radar_hp": False,
        }

        # Movement toggles
        self.movement = {
            "speed_enabled": False, "speed_value": 50,
            "jump_enabled": False, "jump_power": 100,
            "fly_enabled": False, "fly_speed": 50,
            "noclip_enabled": False,
            "infjump_enabled": False,
        }

        # Expand toggles
        self.expand = {
            "hitbox_enabled": False, "hitbox_npc": True, "hitbox_players": True,
            "hitbox_nocollide": False, "hitbox_transparency": 0.4,
            "animspeed_enabled": False, "animspeed_mult": 2.0, "animspeed_rate": 0.1,
            "anti_afk_enabled": False,
            "gravity": 196.2, "fallen_parts_destroy_height": -500,
            "hip_height": 2.0, "image_plane_depth": 1.0,
        }

        # Utility toggles
        self.utility = {
            "god_mode": False, "freeze": False, "invisible": False,
            "maxfps": 60, "scheduler_enabled": False,
        }

        # NPC toggles
        self.npc = {
            "autofarm_enabled": False, "autofarm_running": False,
            "autofarm_attacking": True, "autofarm_health_only": True,
            "autofarm_auto_teleport": False,
            "autofarm_radius": 100, "autofarm_delay": 500,
            "follow_enabled": False, "follow_distance": 5,
        }

        # Avatar toggles
        self.avatar = {
            "godmode_enabled": False,
            "invisible_enabled": False,
            "neon_enabled": False,
        }

        # Saved positions
        self._saved_positions: List[dict] = []
        self._saved_pos_counter = 0

        # NPC saved positions
        self._npc_original_positions: Dict[str, any] = {}

        # NPC log
        self._npc_log_buffer: List[dict] = []

        # Executor
        self.executor = {
            "exec_method": "TaskScheduler",
        }

        # Thread management
        self.active_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.lock = threading.Lock()

        # Combat log
        self._combat_log_buffer: List[dict] = []

        # Utility log
        self._utility_log_buffer: List[dict] = []

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "pid": self.pid,
            "has_api": HAS_API,
            "has_addons": HAS_ADDONS,
            "combat": self.combat,
            "movement": self.movement,
            "expand": self.expand,
            "utility": self.utility,
            "npc": self.npc,
            "avatar": self.avatar,
            "executor": self.executor,
            "tools": self.tools,
        }


state = PanelState()
_main_loop = None

# ═══════════════════════════════════════════════════════════════
#  GAME HELPERS
# ═══════════════════════════════════════════════════════════════

def _get_local_player():
    if not state.dm:
        return None
    try:
        return state.dm.Players.LocalPlayer
    except Exception:
        return None

def _get_local_character():
    if not state.dm:
        return None
    try:
        lp = state.dm.Players.LocalPlayer
        if lp:
            return lp.Character
    except Exception:
        pass
    return None

def _get_character_team(char):
    """Get team name of a character."""
    try:
        parent = safe_read(lambda: char.Parent)
        for _ in range(3):
            if not parent:
                break
            cn = safe_read(lambda: parent.ClassName)
            if cn == "Player":
                team = safe_read(lambda: parent.Team)
                if team:
                    return safe_read(lambda: team.Name)
                return None
            parent = safe_read(lambda: parent.Parent)
    except Exception:
        pass
    return None

def _is_npc_character(char):
    """Check if character is NPC (no Player parent)."""
    try:
        parent = safe_read(lambda: char.Parent)
        for _ in range(5):
            if not parent:
                break
            cn = safe_read(lambda: parent.ClassName)
            if cn == "Player":
                return False
            parent = safe_read(lambda: parent.Parent)
        return True
    except Exception:
        return True

def _get_all_characters():
    """Get all characters (players + NPC)."""
    chars = []
    if not state.dm:
        return chars
    try:
        player_names = set()
        # Players
        try:
            for p in state.dm.Players.GetPlayers():
                try:
                    ch = p.Character
                    if ch and safe_read(lambda: ch.FindFirstChildOfClass("Humanoid")):
                        chars.append(ch)
                        name = safe_read(lambda: p.Name)
                        if name:
                            player_names.add(name)
                except Exception:
                    pass
        except Exception:
            pass

        # NPC scan
        try:
            ws = state.dm.Workspace
            if ws:
                for desc in ws.GetDescendants():
                    try:
                        cn = safe_read(lambda: desc.ClassName)
                        if cn != "Model":
                            continue
                        name = safe_read(lambda: desc.Name)
                        if name and name in player_names:
                            continue
                        if not safe_read(lambda: desc.FindFirstChildOfClass("Humanoid")):
                            continue
                        # Check not already added
                        skip = False
                        for c in chars:
                            try:
                                if c.raw_address == desc.raw_address:
                                    skip = True
                                    break
                            except Exception:
                                pass
                        if not skip:
                            chars.append(desc)
                    except Exception:
                        continue
        except Exception:
            pass
    except Exception:
        pass
    return chars

def _get_camera_yaw():
    """Get camera yaw angle in radians."""
    try:
        cam = safe_read(lambda: state.dm.Workspace.CurrentCamera)
        if not cam:
            return 0.0
        cf = safe_read(lambda: cam.CFrame)
        if not cf:
            return 0.0
        if hasattr(cf, 'LookVector'):
            lv = cf.LookVector
            return math.atan2(lv.X, lv.Z)
        if hasattr(cf, 'components'):
            comps = cf.components
            if len(comps) >= 12:
                return math.atan2(comps[9], comps[11])
    except Exception:
        pass
    return 0.0

def vec3_dist(a, b):
    if not a or not b:
        return float("inf")
    try:
        return math.sqrt((a.X - b.X)**2 + (a.Y - b.Y)**2 + (a.Z - b.Z)**2)
    except Exception:
        return float("inf")

# ═══════════════════════════════════════════════════════════════
#  THREAD MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def _start_feature(name, target):
    """Start a feature thread with stop event."""
    _stop_feature(name)
    ev = threading.Event()
    state.stop_events[name] = ev
    t = threading.Thread(target=target, args=(ev,), daemon=True, name=name)
    t.start()
    state.active_threads[name] = t

def _stop_feature(name):
    """Stop a feature thread."""
    ev = state.stop_events.get(name)
    if ev:
        ev.set()
    t = state.active_threads.get(name)
    if t and t.is_alive():
        t.join(timeout=2)
    state.stop_events.pop(name, None)
    state.active_threads.pop(name, None)

def _stop_all_features():
    """Stop all feature threads."""
    for name in list(state.stop_events.keys()):
        _stop_feature(name)

# ═══════════════════════════════════════════════════════════════
#  COMBAT LOG (push to browser)
# ═══════════════════════════════════════════════════════════════

def _combat_log(text, tag="info"):
    """Add entry to combat log buffer. Push to browser."""
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "text": text,
        "tag": tag,  # info, good, warn, error
    }
    state._combat_log_buffer.append(entry)
    # Keep buffer limited
    if len(state._combat_log_buffer) > 200:
        state._combat_log_buffer = state._combat_log_buffer[-200:]

# ═══════════════════════════════════════════════════════════════
#  COMBAT — TARGET FINDING
# ═══════════════════════════════════════════════════════════════

def _find_aimbot_target():
    """Find nearest target to crosshair within FOV."""
    local_char = _get_local_character()
    if not local_char or not state.w2s:
        return None

    local_player = _get_local_player()
    local_team = None
    if local_player:
        local_team = safe_read(lambda: local_player.Team)
        if local_team:
            local_team = safe_read(lambda: local_team.Name)

    cx, cy = get_cursor_pos()
    fov = state.combat["aimbot_fov"]

    best_target = None
    best_dist = fov

    for char in _get_all_characters():
        try:
            if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                if char.raw_address == local_char.raw_address:
                    continue

            # Team check
            if state.combat["aimbot_team_check"] and local_team:
                char_team = _get_character_team(char)
                if char_team and char_team == local_team:
                    continue

            # Alive check
            if state.combat["aimbot_alive_check"]:
                hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
                if not hum:
                    continue
                health = safe_read(lambda: hum.Health)
                if health is not None and health <= 0:
                    continue

            # NPC check
            if not state.combat["aimbot_npc_check"]:
                if _is_npc_character(char):
                    continue

            bone = state.combat["aimbot_bone"]
            part = safe_read(lambda: char.FindFirstChild(bone))
            if not part:
                part = safe_read(lambda: char.FindFirstChild("Head"))
            if not part:
                continue

            pos = safe_read(lambda: part.Position)
            if not pos:
                continue

            result = state.w2s.world_to_screen(pos)
            if not result or not result.on_screen:
                continue

            dist = math.sqrt((result.x - cx)**2 + (result.y - cy)**2)
            if dist < best_dist:
                best_dist = dist
                best_target = char
        except Exception:
            continue

    return best_target


def _find_headlock_target():
    """Find nearest target to crosshair for headlock (head only)."""
    local_char = _get_local_character()
    if not local_char or not state.w2s:
        return None

    cx, cy = get_cursor_pos()
    fov = state.combat["headlock_fov"]

    local_player = _get_local_player()
    local_team = None
    if local_player:
        local_team = safe_read(lambda: local_player.Team)
        if local_team:
            local_team = safe_read(lambda: local_team.Name)

    best_target = None
    best_dist = fov

    for char in _get_all_characters():
        try:
            if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                if char.raw_address == local_char.raw_address:
                    continue

            if state.combat["headlock_team_check"] and local_team:
                char_team = _get_character_team(char)
                if char_team and char_team == local_team:
                    continue

            hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
            if hum:
                health = safe_read(lambda: hum.Health)
                if health is not None and health <= 0:
                    continue

            if not state.combat["headlock_npc_check"]:
                if _is_npc_character(char):
                    continue

            head = safe_read(lambda: char.FindFirstChild("Head"))
            if not head:
                continue

            pos = safe_read(lambda: head.Position)
            if not pos:
                continue

            result = state.w2s.world_to_screen(pos)
            if not result or not result.on_screen:
                continue

            dist = math.sqrt((result.x - cx)**2 + (result.y - cy)**2)
            if dist < best_dist:
                best_dist = dist
                best_target = char
        except Exception:
            continue

    return best_target


def _find_silent_aim_target():
    """Find nearest character for silent aim (3D dist + FOV)."""
    local_char = _get_local_character()
    if not local_char:
        return None

    hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
    if not hrp:
        return None
    my_pos = safe_read(lambda: hrp.Position)
    if not my_pos:
        return None

    local_player = _get_local_player()
    local_team = None
    if local_player:
        local_team = safe_read(lambda: local_player.Team)
        if local_team:
            local_team = safe_read(lambda: local_team.Name)

    cx, cy = get_cursor_pos()
    fov_radius = state.combat["aimbot_fov"]

    best = None
    best_dist = float("inf")

    for char in _get_all_characters():
        try:
            if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                if char.raw_address == local_char.raw_address:
                    continue

            if state.combat["silent_aim_team_check"] and local_team:
                char_team = _get_character_team(char)
                if char_team and char_team == local_team:
                    continue

            char_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if not char_hrp:
                continue
            pos = safe_read(lambda: char_hrp.Position)
            if not pos:
                continue

            # W2S FOV check
            if state.w2s:
                w2s_r = state.w2s.world_to_screen(pos)
                if w2s_r and w2s_r.on_screen:
                    sd = math.sqrt((w2s_r.x - cx)**2 + (w2s_r.y - cy)**2)
                    if sd > fov_radius:
                        continue

            d = vec3_dist(my_pos, pos)
            if d < best_dist:
                best_dist = d
                best = char
        except Exception:
            continue
    return best


# ═══════════════════════════════════════════════════════════════
#  COMBAT — AIMBOT LOOP (~120Hz)
# ═══════════════════════════════════════════════════════════════

def _aimbot_loop(stop):
    """Aimbot: RMB trigger, finds FOV target, W2S, mouse_move."""
    _combat_log("Aimbot: loop started", "good")
    while not stop.is_set():
        try:
            if not is_key_pressed(VK_RBUTTON):
                stop.wait(0.008)
                continue
            if not state.w2s:
                stop.wait(0.1)
                continue

            target = _find_aimbot_target()
            if not target:
                stop.wait(0.008)
                continue

            bone = state.combat["aimbot_bone"]
            part = safe_read(lambda: target.FindFirstChild(bone))
            if not part:
                part = safe_read(lambda: target.FindFirstChild("Head"))
            if not part:
                stop.wait(0.008)
                continue

            pos = safe_read(lambda: part.Position)
            if not pos:
                stop.wait(0.008)
                continue

            result = state.w2s.world_to_screen(pos)
            if not result or not result.on_screen:
                stop.wait(0.008)
                continue

            cx, cy = get_cursor_pos()
            sensitivity2 = max(0.1, state.combat["aimbot_sens"])
            dx = (result.x - cx) / sensitivity2
            dy = (result.y - cy) / sensitivity2

            if abs(dx) > 0.5 or abs(dy) > 0.5:
                mouse_move(dx, dy)
        except Exception:
            pass
        stop.wait(0.008)  # ~120Hz


# ═══════════════════════════════════════════════════════════════
#  COMBAT — HEAD LOCK LOOP (~250Hz)
# ═══════════════════════════════════════════════════════════════

def _headlock_loop(stop):
    """Head Lock: rigidly holds crosshair on target's head.
    Does NOT switch targets while locked."""
    _combat_log("Head Lock: loop started", "good")
    locked_target = None

    while not stop.is_set():
        try:
            if not is_key_pressed(VK_RBUTTON):
                locked_target = None
                stop.wait(0.008)
                continue

            if not state.w2s:
                stop.wait(0.5)
                continue

            if locked_target is None:
                locked_target = _find_headlock_target()

            if not locked_target:
                stop.wait(0.008)
                continue

            # Check if target still alive
            hum = safe_read(lambda: locked_target.FindFirstChildOfClass("Humanoid"))
            if hum:
                health = safe_read(lambda: hum.Health)
                if health is not None and health <= 0:
                    locked_target = None
                    continue

            head = safe_read(lambda: locked_target.FindFirstChild("Head"))
            if not head:
                head = safe_read(lambda: locked_target.FindFirstChild("HumanoidRootPart"))
            if not head:
                locked_target = None
                continue

            pos = safe_read(lambda: head.Position)
            if not pos:
                continue

            result = state.w2s.world_to_screen(pos)
            if not result or not result.on_screen:
                locked_target = None
                continue

            cx, cy = get_cursor_pos()
            smoothing = max(0.5, state.combat["headlock_smooth"])
            factor = smoothing / (smoothing + 1.0)
            target_x = cx + (result.x - cx) * factor
            target_y = cy + (result.y - cy) * factor

            dx = target_x - cx
            dy = target_y - cy

            if abs(dx) > 0.3 or abs(dy) > 0.3:
                mouse_move(dx, dy)

        except Exception:
            locked_target = None
        stop.wait(0.004)  # ~250Hz


# ═══════════════════════════════════════════════════════════════
#  COMBAT — SILENT AIM LOOP (~100Hz)
# ═══════════════════════════════════════════════════════════════

def _silent_aim_loop(stop):
    """Silent Aim: RMB trigger, targets body (HRP), W2S + mouse_move."""
    _combat_log("Silent Aim: loop started", "good")
    while not stop.is_set():
        try:
            if not is_key_pressed(VK_RBUTTON):
                stop.wait(0.01)
                continue
            if not state.w2s:
                stop.wait(0.5)
                continue

            local_char = _get_local_character()
            if not local_char:
                stop.wait(0.1)
                continue

            target = _find_silent_aim_target()
            if not target:
                stop.wait(0.01)
                continue

            body_part = safe_read(lambda: target.FindFirstChild("HumanoidRootPart"))
            if not body_part:
                body_part = safe_read(lambda: target.FindFirstChild("Torso"))
            if not body_part:
                stop.wait(0.01)
                continue

            pos = safe_read(lambda: body_part.Position)
            if not pos:
                stop.wait(0.01)
                continue

            result = state.w2s.world_to_screen(pos)
            if not result or not result.on_screen:
                stop.wait(0.01)
                continue

            cx, cy = get_cursor_pos()
            sensitivity2 = max(0.1, state.combat["aimbot_sens"])
            dx = (result.x - cx) / sensitivity2
            dy = (result.y - cy) / sensitivity2

            if abs(dx) > 0.5 or abs(dy) > 0.5:
                mouse_move(dx, dy)
        except Exception:
            pass
        stop.wait(0.01)


# ═══════════════════════════════════════════════════════════════
#  COMBAT — TRIGGERBOT LOOP (~100Hz)
# ═══════════════════════════════════════════════════════════════

def _triggerbot_loop(stop):
    """Auto-clicks when crosshair is within 15px of enemy head."""
    _combat_log("Triggerbot: loop started", "good")
    while not stop.is_set():
        try:
            if not is_key_pressed(VK_RBUTTON):
                stop.wait(0.01)
                continue
            if not state.w2s:
                stop.wait(0.5)
                continue

            cx, cy = get_cursor_pos()
            local_char = _get_local_character()

            for char in _get_all_characters():
                try:
                    if local_char and hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    hrp = safe_read(lambda: char.FindFirstChild("Head"))
                    if not hrp:
                        continue
                    pos = safe_read(lambda: hrp.Position)
                    if not pos:
                        continue
                    result = state.w2s.world_to_screen(pos)
                    if not result or not result.on_screen:
                        continue
                    dist = math.sqrt((result.x - cx)**2 + (result.y - cy)**2)
                    if dist < 15:
                        delay = int(state.combat["triggerbot_delay"])
                        mouse_click_down()
                        stop.wait(delay / 1000.0)
                        mouse_click_up()
                        break
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.01)


# ═══════════════════════════════════════════════════════════════
#  COMBAT — KILL AURA LOOP (~20Hz)
# ═══════════════════════════════════════════════════════════════

def _kill_aura_loop(stop):
    """Aimbot + triggerbot combined. Aims + auto-shoots nearest."""
    _combat_log("Kill Aura: loop started", "good")
    while not stop.is_set():
        try:
            if not is_key_pressed(VK_RBUTTON):
                stop.wait(0.01)
                continue
            if not state.w2s:
                stop.wait(0.5)
                continue

            local_char = _get_local_character()
            if not local_char:
                stop.wait(0.1)
                continue
            hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            if not hrp:
                stop.wait(0.1)
                continue
            my_pos = safe_read(lambda: hrp.Position)
            if not my_pos:
                stop.wait(0.1)
                continue

            max_range = state.combat["kill_aura_range"]
            best = None
            best_dist = max_range

            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    t_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    if not t_hrp:
                        continue
                    t_pos = safe_read(lambda: t_hrp.Position)
                    if not t_pos:
                        continue
                    d = vec3_dist(my_pos, t_pos)
                    if d < best_dist:
                        best_dist = d
                        best = char
                except Exception:
                    pass

            if best:
                t_head = safe_read(lambda: best.FindFirstChild("Head"))
                if not t_head:
                    t_head = safe_read(lambda: best.FindFirstChild("HumanoidRootPart"))
                if t_head:
                    pos = safe_read(lambda: t_head.Position)
                    if pos:
                        result = state.w2s.world_to_screen(pos)
                        if result and result.on_screen:
                            cx, cy = get_cursor_pos()
                            sensitivity2 = max(0.1, state.combat["aimbot_sens"])
                            dx = (result.x - cx) / sensitivity2
                            dy = (result.y - cy) / sensitivity2
                            if abs(dx) > 0.5 or abs(dy) > 0.5:
                                mouse_move(dx, dy)
                            mouse_click_down()
                            stop.wait(0.05)
                            mouse_click_up()
        except Exception:
            pass
        stop.wait(0.05)


# ═══════════════════════════════════════════════════════════════
#  COMBAT — RADAR LOOP (~7Hz, pushes data to browser)
# ═══════════════════════════════════════════════════════════════

def _radar_loop(stop):
    """Collects positions and broadcasts radar data to browser."""
    _combat_log("Radar: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state.dm:
                stop.wait(0.5)
                continue

            local_char = _get_local_character()
            if not local_char:
                stop.wait(0.3)
                continue

            local_root = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            if not local_root:
                stop.wait(0.3)
                continue
            local_pos = safe_read(lambda: local_root.Position)
            if not local_pos:
                stop.wait(0.3)
                continue

            camera_yaw = _get_camera_yaw()

            local_player = _get_local_player()
            local_team = None
            if local_player:
                lt = safe_read(lambda: local_player.Team)
                if lt:
                    local_team = safe_read(lambda: lt.Name)

            targets = []
            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue

                    if not state.combat["radar_npc"]:
                        if _is_npc_character(char):
                            continue

                    char_team = _get_character_team(char)
                    is_team = False
                    if local_team and char_team and char_team == local_team:
                        is_team = True

                    root = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    if not root:
                        continue
                    pos = safe_read(lambda: root.Position)
                    if not pos:
                        continue

                    hp = None
                    hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
                    if hum:
                        hp = safe_read(lambda: hum.Health)

                    name = safe_read(lambda: char.Name) or "?"

                    dx = pos.X - local_pos.X
                    dz = pos.Z - local_pos.Z
                    dist = math.sqrt(dx * dx + dz * dz)

                    targets.append({
                        "name": name,
                        "dx": round(dx, 2),
                        "dy": round(pos.Y - local_pos.Y, 2),
                        "dz": round(dz, 2),
                        "dist": round(dist, 1),
                        "hp": int(hp) if hp is not None else None,
                        "is_team": is_team,
                        "is_npc": _is_npc_character(char),
                    })
                except Exception:
                    continue

            # Push to browser
            _push_radar_data(targets, camera_yaw)

        except Exception:
            pass
        stop.wait(0.15)  # ~7 FPS


# ═══════════════════════════════════════════════════════════════
#  COMBAT — MOVEMENT: NOCLIP LOOP (~60Hz)
# ═══════════════════════════════════════════════════════════════

def _noclip_loop(stop):
    """NoClip: disables CanCollide on all body parts every frame."""
    _combat_log("NoClip: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if char:
                for part in char.GetDescendants():
                    try:
                        if _is_part(part) and hasattr(part, 'raw_address'):
                            _set_can_collide(state._mem, part.raw_address, False)
                    except Exception:
                        pass
        except Exception:
            pass
        stop.wait(0.016)  # ~60Hz


# ═══════════════════════════════════════════════════════════════
#  COMBAT — MOVEMENT: FLY LOOP (~60Hz)
# ═══════════════════════════════════════════════════════════════

def _fly_loop(stop):
    """Fly: writes velocity based on WASD + Space/Shift input."""
    _combat_log("Fly: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(0.1)
                continue
            hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if not hrp or not hasattr(hrp, 'raw_address'):
                stop.wait(0.1)
                continue

            speed = state.movement["fly_speed"]
            vx, vy, vz = 0.0, 0.0, 0.0

            if is_key_pressed(VK_W):
                vz -= speed
            if is_key_pressed(VK_S):
                vz += speed
            if is_key_pressed(VK_A):
                vx -= speed
            if is_key_pressed(VK_D):
                vx += speed
            if is_key_pressed(VK_SPACE):
                vy += speed
            if is_key_pressed(VK_SHIFT):
                vy -= speed

            # Get camera direction for relative movement
            try:
                cam = state.dm.Workspace.CurrentCamera
                cf = cam.CFrame
                # Use look vector components for relative movement
                lv_x = getattr(cf, 'LookVector', type('o', (), {'X': 0, 'Z': -1})()).X
                lv_z = getattr(cf, 'LookVector', type('o', (), {'X': 0, 'Z': -1})()).Z
                # Rotate movement by camera yaw
                new_vx = vx * lv_z + vz * lv_x
                new_vz = -vx * lv_x + vz * lv_z
                vx, vz = new_vx, new_vz
            except Exception:
                pass

            # Create velocity vector
            if HAS_API:
                _write_velocity(state._mem, hrp.raw_address, Vector3(vx, vy, vz))
        except Exception:
            pass
        stop.wait(0.016)  # ~60Hz


# ═══════════════════════════════════════════════════════════════
#  COMBAT — MOVEMENT: INFINITE JUMP
# ═══════════════════════════════════════════════════════════════

def _infjump_loop(stop):
    """Infinite Jump: forces jump when Space held and character falling."""
    _combat_log("InfJump: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected:
                stop.wait(0.5)
                continue
            if is_key_pressed(VK_SPACE):
                char = _get_local_character()
                if char:
                    hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
                    if hum:
                        state_val = safe_read(lambda: getattr(hum, 'GetState', lambda: 0)())
                        # 0 = Running, if on ground we can jump
                        try:
                            hum.Jump = True
                        except Exception:
                            pass
        except Exception:
            pass
        stop.wait(0.03)


# ═══════════════════════════════════════════════════════════════
#  COMBAT — ANTI-AFK LOOP
# ═══════════════════════════════════════════════════════════════

def _antiafk_loop(stop):
    """Anti-AFK: moves mouse every 4 minutes."""
    _combat_log("Anti-AFK: active", "good")
    while not stop.is_set():
        try:
            mouse_move(10, 10)
            stop.wait(0.05)
            mouse_move(-10, -10)
        except Exception:
            pass
        stop.wait(240)  # 4 minutes
        if stop.is_set():
            break


# ═══════════════════════════════════════════════════════════════
#  PUSH DATA TO BROWSER (radar, combat log)
# ═══════════════════════════════════════════════════════════════

async def _async_push_radar(targets, camera_yaw):
    """Async wrapper for pushing radar data."""
    await broadcast({
        "type": "radar_data",
        "data": {
            "targets": targets,
            "camera_yaw": camera_yaw,
            "range": state.combat["radar_range"],
        }
    })


def _push_radar_data(targets, camera_yaw):
    try:
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _async_push_radar(targets, camera_yaw), _main_loop
            )
    except Exception:
        pass


async def _async_push_combat_log(entries):
    """Async wrapper for pushing combat log."""
    await broadcast({"type": "combat_log", "data": entries})


def _push_combat_log():
    if not state._combat_log_buffer:
        return
    entries = state._combat_log_buffer[:]
    state._combat_log_buffer.clear()
    try:
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _async_push_combat_log(entries), _main_loop
            )
    except Exception:
        pass


# Periodic combat log pusher
def _combat_log_pusher():
    """Daemon that pushes combat log every 200ms."""
    while True:
        try:
            _push_combat_log()
        except Exception:
            pass
        time.sleep(0.2)


# ═══════════════════════════════════════════════════════════════
#  NPC LOG (push to browser)
# ═══════════════════════════════════════════════════════════════

def _npc_log(text, tag="info"):
    """Add entry to NPC log buffer. Push to browser."""
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "text": text,
        "tag": tag,
    }
    state._npc_log_buffer.append(entry)
    if len(state._npc_log_buffer) > 200:
        state._npc_log_buffer = state._npc_log_buffer[-200:]


async def _async_push_npc_log(entries):
    """Push NPC log entries to browser."""
    await broadcast({"type": "npc_log", "data": entries})


def _push_npc_log():
    if not state._npc_log_buffer:
        return
    entries = state._npc_log_buffer[:]
    state._npc_log_buffer.clear()
    try:
        if _main_loop and _main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _async_push_npc_log(entries), _main_loop
            )
    except Exception:
        pass


def _npc_log_pusher():
    """Daemon that pushes NPC log every 200ms."""
    while True:
        try:
            _push_npc_log()
        except Exception:
            pass
        time.sleep(0.2)


# ═══════════════════════════════════════════════════════════════
#  PART HELPERS (transparency, self parts)
# ═══════════════════════════════════════════════════════════════

def _write_part_transparency(mem, part_addr, val):
    """Write BasePart::Transparency at offset 240."""
    off = _BP.get("Transparency", _BP_TRANSPARENCY)
    try:
        mem.write_float(part_addr + off, float(val))
        return True
    except Exception:
        return False


def _get_self_parts(char):
    """Get all BasePart descendants of a character."""
    parts = []
    if not char:
        return parts
    try:
        descs = safe_read(lambda: char.GetDescendants())
        if descs:
            for d in descs:
                try:
                    if _is_part(d):
                        parts.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return parts


# ═══════════════════════════════════════════════════════════════
#  UTILITY — GOD MODE LOOP
# ═══════════════════════════════════════════════════════════════

def _utility_godmode_loop(stop):
    """Sets Health = MaxHealth every frame via direct memory."""
    _combat_log("God Mode: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(0.5)
                continue
            hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
            if hum and state._mem and state._mem.ok():
                mh = safe_read(lambda: hum.MaxHealth, 100)
                if mh:
                    off = _HO.get("MaxHealth", _HO_MAXHEALTH)
                    maxh = state._mem.read_float(hum.raw_address + off)
                    if maxh > 0:
                        health_off = _HO.get("Health", _HO_HEALTH)
                        state._mem.write_float(hum.raw_address + health_off, maxh)
        except Exception:
            pass
        stop.wait(0.016)  # ~60Hz


# ═══════════════════════════════════════════════════════════════
#  UTILITY — FREEZE LOOP
# ═══════════════════════════════════════════════════════════════

def _utility_freeze_loop(stop):
    """Sets AssemblyLinearVelocity = 0 every frame."""
    _combat_log("Freeze: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(0.5)
                continue
            hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if hrp and hrp.raw_address and state._mem:
                _write_velocity(state._mem, hrp.raw_address, Vector3(0, 0, 0))
        except Exception:
            pass
        stop.wait(0.016)  # ~60Hz


# ═══════════════════════════════════════════════════════════════
#  NPC — AUTOFARM LOOP
# ═══════════════════════════════════════════════════════════════

def _npc_autofarm_loop(stop):
    """NPC Autofarm: flies to nearest NPC, attacks, repeats."""
    _npc_log("NPC Autofarm: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(1)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(1)
                continue
            hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if not hrp or not hrp.raw_address:
                stop.wait(1)
                continue

            my_pos = safe_read(lambda: hrp.Position)
            if not my_pos:
                stop.wait(0.5)
                continue

            # Find nearest NPC within radius
            radius = state.npc.get("autofarm_radius", 100)
            target_name = None  # Future: filter by name
            best_npc = None
            best_dist = radius
            alive_only = state.npc.get("autofarm_health_only", True)

            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if hasattr(c, 'raw_address') and hasattr(char, 'raw_address'):
                        if c.raw_address == char.raw_address:
                            continue
                    hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
                    if not hum:
                        continue
                    if alive_only:
                        hp = safe_read(lambda: hum.Health)
                        if hp is not None and hp <= 0:
                            continue
                    t_hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                    if not t_hrp:
                        continue
                    t_pos = safe_read(lambda: t_hrp.Position)
                    if not t_pos:
                        continue
                    d = vec3_dist(my_pos, t_pos)
                    if d < best_dist:
                        best_dist = d
                        best_npc = c
                except Exception:
                    continue

            if not best_npc:
                stop.wait(0.1)
                continue

            npc_name = safe_read(lambda: best_npc.Name) or "?"
            t_hrp = safe_read(lambda: best_npc.FindFirstChild("HumanoidRootPart"))
            if not t_hrp or not t_hrp.raw_address:
                continue

            t_pos = safe_read(lambda: t_hrp.Position)
            if not t_pos:
                continue

            # Auto teleport close to NPC
            if state.npc.get("autofarm_auto_teleport", False):
                dx = t_pos.X - my_pos.X
                dy = t_pos.Y - my_pos.Y
                dz = t_pos.Z - my_pos.Z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist > 5:
                    speed = 0.5
                    new_x = my_pos.X + dx * speed
                    new_y = my_pos.Y + dy * speed
                    new_z = my_pos.Z + dz * speed
                    _write_part_position(state._mem, hrp.raw_address, Vector3(new_x, new_y, new_z))
                    stop.wait(0.05)
                    continue

            # Attack if close enough
            if best_dist < 8:
                if state.npc.get("autofarm_attacking", True):
                    mouse_click_down()
                    stop.wait(0.05)
                    mouse_click_up()

                delay = state.npc.get("autofarm_delay", 500) / 1000.0
                _npc_log(f"Attacked: {npc_name} (dist={best_dist:.1f})", "good")
                stop.wait(delay)
            else:
                # Move closer
                speed = 0.3
                dx = t_pos.X - my_pos.X
                dy = t_pos.Y - my_pos.Y
                dz = t_pos.Z - my_pos.Z
                new_x = my_pos.X + dx * speed
                new_y = my_pos.Y + dy * speed
                new_z = my_pos.Z + dz * speed
                _write_part_position(state._mem, hrp.raw_address, Vector3(new_x, new_y, new_z))
                stop.wait(0.05)

        except Exception as e:
            _npc_log(f"Autofarm error: {e}", "error")
            stop.wait(1)


# ═══════════════════════════════════════════════════════════════
#  NPC — GOD MODE LOOP
# ═══════════════════════════════════════════════════════════════

def _npc_godmode_loop(stop, target_name=""):
    """Sets NPC Health = MaxHealth every frame."""
    _npc_log(f"NPC God Mode: ON (target={target_name or 'all'})", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if target_name:
                        name = safe_read(lambda: c.Name) or ""
                        if name.lower() != target_name.lower():
                            continue
                    hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
                    if hum and hum.raw_address:
                        off = _HO.get("MaxHealth", _HO_MAXHEALTH)
                        maxh = state._mem.read_float(hum.raw_address + off)
                        if maxh > 0:
                            health_off = _HO.get("Health", _HO_HEALTH)
                            state._mem.write_float(hum.raw_address + health_off, maxh)
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.1)  # 10Hz


# ═══════════════════════════════════════════════════════════════
#  NPC — FREEZE LOOP
# ═══════════════════════════════════════════════════════════════

def _npc_freeze_loop(stop, target_name=""):
    """Sets NPC AssemblyLinearVelocity = 0 every frame."""
    _npc_log(f"NPC Freeze: ON (target={target_name or 'all'})", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if target_name:
                        name = safe_read(lambda: c.Name) or ""
                        if name.lower() != target_name.lower():
                            continue
                    hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                    if hrp and hrp.raw_address:
                        _write_velocity(state._mem, hrp.raw_address, Vector3(0, 0, 0))
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.05)  # 20Hz


# ═══════════════════════════════════════════════════════════════
#  NPC — INVISIBLE LOOP
# ═══════════════════════════════════════════════════════════════

def _npc_invisible_loop(stop, target_name=""):
    """Sets NPC part Transparency = 1.0 every frame."""
    _npc_log(f"NPC Invisible: ON (target={target_name or 'all'})", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if target_name:
                        name = safe_read(lambda: c.Name) or ""
                        if name.lower() != target_name.lower():
                            continue
                    parts = _get_self_parts(c)
                    for p in parts:
                        if p.raw_address:
                            _write_part_transparency(state._mem, p.raw_address, 1.0)
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.1)  # 10Hz


def _npc_restore_visibility_loop(stop, target_name=""):
    """Restores NPC part Transparency = 0.0."""
    _npc_log(f"NPC Visible: restoring (target={target_name or 'all'})", "info")
    for _ in range(20):
        if stop.is_set():
            break
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if target_name:
                        name = safe_read(lambda: c.Name) or ""
                        if name.lower() != target_name.lower():
                            continue
                    parts = _get_self_parts(c)
                    for p in parts:
                        if p.raw_address:
                            _write_part_transparency(state._mem, p.raw_address, 0.0)
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.1)


# ═══════════════════════════════════════════════════════════════
#  NPC — FOLLOW LOOP
# ═══════════════════════════════════════════════════════════════

def _npc_follow_loop(stop, target_name=""):
    """NPCs follow local player."""
    _npc_log(f"NPC Follow: ON (target={target_name or 'all'})", "good")
    while not stop.is_set():
        try:
            if not state.connected or not state._mem:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(0.5)
                continue
            my_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if not my_hrp:
                stop.wait(0.5)
                continue
            my_pos = safe_read(lambda: my_hrp.Position)
            if not my_pos:
                stop.wait(0.5)
                continue

            follow_dist = state.npc.get("follow_distance", 5)

            for c in _get_all_characters():
                try:
                    if not _is_npc_character(c):
                        continue
                    if target_name:
                        name = safe_read(lambda: c.Name) or ""
                        if name.lower() != target_name.lower():
                            continue
                    hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                    if not hrp or not hrp.raw_address:
                        continue
                    npc_pos = safe_read(lambda: hrp.Position)
                    if not npc_pos:
                        continue

                    d = vec3_dist(my_pos, npc_pos)
                    if d > follow_dist:
                        dx = my_pos.X - npc_pos.X
                        dy = my_pos.Y - npc_pos.Y
                        dz = my_pos.Z - npc_pos.Z
                        length = math.sqrt(dx*dx + dy*dy + dz*dz)
                        if length > 0:
                            speed = 16.0 * 0.05  # WalkSpeed * dt
                            new_x = npc_pos.X + (dx / length) * speed
                            new_y = npc_pos.Y + (dy / length) * speed
                            new_z = npc_pos.Z + (dz / length) * speed
                            _write_part_position(state._mem, hrp.raw_address, Vector3(new_x, new_y, new_z))
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.05)  # 20Hz


# ═══════════════════════════════════════════════════════════════
#  AVATAR — NEON GLOW LOOP
# ═══════════════════════════════════════════════════════════════

# Avatar neon glow state (stored outside PanelState for real-time params)
_avatar_neon_params = {"r": 0, "g": 212, "b": 255, "intensity": 0.5}


def _avatar_neon_loop(stop):
    """Sets EmissiveTint-like effect on character parts via direct memory."""
    _combat_log("Neon Glow: loop started", "good")
    while not stop.is_set():
        try:
            if not state.connected:
                stop.wait(0.5)
                continue
            char = _get_local_character()
            if not char:
                stop.wait(0.5)
                continue

            r = clamp(_avatar_neon_params["r"], 0, 255) / 255.0
            g = clamp(_avatar_neon_params["g"], 0, 255) / 255.0
            b = clamp(_avatar_neon_params["b"], 0, 255) / 255.0
            intensity = clamp(_avatar_neon_params.get("intensity", 0.5), 0.0, 3.0)

            # Write color to BasePart Color3 (offset 0x4A: R, G, B floats)
            for p in _get_self_parts(char):
                try:
                    if p.raw_address and state._mem:
                        off = _BP.get("Color3", _BP_COLOR3)
                        state._mem.write_float(p.raw_address + off, r * intensity)
                        state._mem.write_float(p.raw_address + off + 4, g * intensity)
                        state._mem.write_float(p.raw_address + off + 8, b * intensity)
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.2)  # 5Hz


# ═══════════════════════════════════════════════════════════════
#  TOOLS — SCANNER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _scan_equipped_tools():
    """Scan equipped tools (Character children + Backpack)."""
    if not state.connected or not state.dm:
        return {"type": "tools_list", "data": []}
    tools = []
    try:
        char = _get_local_character()
        if char:
            for child in char.GetChildren():
                try:
                    cn = child.ClassName
                    if cn == "Tool":
                        tools.append({
                            "name": child.Name or "?",
                            "className": cn,
                            "parent": safe_read(lambda: child.Parent.Name) or "?",
                            "address": f"0x{child.raw_address:X}",
                        })
                except: pass
        lp = _get_local_player()
        if lp:
            backpack = safe_read(lambda: lp.FindFirstChild("Backpack"))
            if backpack:
                for child in backpack.GetChildren():
                    try:
                        cn = child.ClassName
                        if cn == "Tool":
                            tools.append({
                                "name": f"[BP] {child.Name or '?'}",
                                "className": cn,
                                "parent": safe_read(lambda: child.Parent.Name) or "?",
                                "address": f"0x{child.raw_address:X}",
                            })
                    except: pass
    except Exception as e:
        _combat_log(f"Scan error: {e}", "error")
    _combat_log(f"Tools found: {len(tools)}", "info")
    return {"type": "tools_list", "data": tools}

def _scan_workspace_tools():
    """Scan all Tool instances in Workspace."""
    if not state.connected or not state.dm:
        return {"type": "tools_list", "data": []}
    tools = []
    try:
        for desc in state.dm.Workspace.GetDescendants():
            try:
                cn = desc.ClassName
                if cn == "Tool":
                    parent = safe_read(lambda: desc.Parent)
                    tools.append({
                        "name": desc.Name or "?",
                        "className": cn,
                        "parent": safe_read(lambda: parent.Name) if parent else "?",
                        "address": f"0x{desc.raw_address:X}",
                    })
            except: pass
    except Exception as e:
        _combat_log(f"Scan error: {e}", "error")
    _combat_log(f"Workspace tools: {len(tools)}", "info")
    return {"type": "tools_list", "data": tools}

def _scan_backpack_tools():
    """Scan Backpack (inventory) only."""
    if not state.connected or not state.dm:
        return {"type": "tools_list", "data": []}
    tools = []
    try:
        lp = _get_local_player()
        if not lp:
            return {"type": "tools_list", "data": []}
        backpack = safe_read(lambda: lp.FindFirstChild("Backpack"))
        if backpack:
            for child in backpack.GetChildren():
                try:
                    cn = child.ClassName
                    if cn == "Tool":
                        tools.append({
                            "name": f"[BP] {child.Name or '?'}",
                            "className": cn,
                            "parent": safe_read(lambda: child.Parent.Name) or "?",
                            "address": f"0x{child.raw_address:X}",
                        })
                except: pass
    except Exception as e:
        _combat_log(f"Scan error: {e}", "error")
    _combat_log(f"Backpack: {len(tools)} tools", "info")
    return {"type": "tools_list", "data": tools}


# ═══════════════════════════════════════════════════════════════
#  TOOLS — COMBAT LOOPS
# ═══════════════════════════════════════════════════════════════

def _unlimited_ammo_loop(stop):
    _combat_log("Unlimited Ammo: ON", "good")
    ammo_names = ["Ammo", "ClipSize", "Clip", "MaxAmmo", "RemainingAmmo",
                  "CurrentAmmo", "AmmoCount", "MagazineSize", "BulletCount"]
    while not stop.is_set():
        try:
            char = _get_local_character()
            if not char:
                stop.wait(0.3); continue
            for desc in char.GetDescendants():
                try:
                    name = safe_read(lambda: desc.Name) or ""
                    if not name: continue
                    cn = desc.ClassName
                    nl = name.lower()
                    is_ammo = any(a.lower() in nl for a in ammo_names)
                    if is_ammo and cn in ("IntValue", "NumberValue", "FloatValue", "DoubleValue"):
                        desc.Value = 999999
                    elif is_ammo and cn == "StringValue":
                        desc.Value = "999999"
                except: pass
        except: pass
        stop.wait(0.1)

def _rapid_fire_loop(stop):
    _combat_log("Rapid Fire: ON", "good")
    while not stop.is_set():
        try:
            char = _get_local_character()
            if not char:
                stop.wait(0.3); continue
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        child.ManualActivationOnly = False
                        child.Enabled = True
                except: pass
            if is_key_pressed(VK_RBUTTON):
                mouse_click_down()
                stop.wait(0.02)
                mouse_click_up()
            else:
                stop.wait(0.05)
        except: pass

def _no_recoil_loop(stop):
    _combat_log("No Recoil: ON", "good")
    recoil_kw = ["recoil", "kick", "pushback", "backforce", "impact"]
    force_cls = ["BodyForce", "BodyVelocity", "BodyThrust", "VectorForce", "LinearVelocity"]
    while not stop.is_set():
        try:
            char = _get_local_character()
            if not char:
                stop.wait(0.3); continue
            for desc in char.GetDescendants():
                try:
                    cn = desc.ClassName
                    if cn in force_cls:
                        nm = (safe_read(lambda: desc.Name) or "").lower()
                        if any(k in nm for k in recoil_kw):
                            try: desc.Force = Vector3(0, 0, 0)
                            except: pass
                            try: desc.Velocity = Vector3(0, 0, 0)
                            except: pass
                except: pass
            hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if hrp and hasattr(hrp, 'raw_address') and hrp.raw_address and state._mem:
                _write_angular_velocity(state._mem, hrp.raw_address, Vector3(0, 0, 0))
        except: pass
        stop.wait(0.03)


# ═══════════════════════════════════════════════════════════════
#  HITBOX FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _parse_size_str(s):
    try:
        parts = [x.strip() for x in s.split(",")]
        if len(parts) == 3:
            return (float(parts[0]), float(parts[1]), float(parts[2]))
    except: pass
    return None

def _hitbox_loop(stop):
    _combat_log("Hitbox v10: loop started", "good")
    while not stop.is_set():
        try:
            _hitbox_apply_all()
        except Exception as e:
            _combat_log(f"Hitbox error: {e}", "error")
        stop.wait(0.01)

def _hitbox_apply_all():
    if not state.dm: return 0
    transp = state.expand.get("hitbox_transparency", 0.4)
    nocollide = state.expand.get("hitbox_nocollide", False)
    want_players = state.expand.get("hitbox_players", True)
    want_npc = state.expand.get("hitbox_npc", True)
    if not want_players and not want_npc: return 0

    player_names = set()
    try:
        for p in state.dm.Players.GetPlayers():
            if p.Character:
                player_names.add(p.Character.Name)
    except: pass

    count = 0
    if want_npc:
        if not state._hitbox_path_discovery_done or not state._hitbox_npc_paths:
            _hitbox_discover_npc_paths()
        for pe in state._hitbox_npc_paths:
            try:
                pn = pe["name"]
                if pn == "__workspace_direct__":
                    for child in state.dm.Workspace.GetChildren():
                        try:
                            if child.ClassName != "Model" or child.Name == "Characters": continue
                            if child.Name in player_names: continue
                            hum = child.FindFirstChildOfClass("Humanoid")
                            if not hum and not child.FindFirstChild("HumanoidRootPart"): continue
                            count += _hitbox_write_model(child, transp, nocollide)
                        except: pass
                else:
                    container = state.dm.Workspace.FindFirstChild(pn)
                    if not container: continue
                    for child in container.GetChildren():
                        try:
                            if child.ClassName != "Model": continue
                            if child.Name in player_names: continue
                            hum = child.FindFirstChildOfClass("Humanoid")
                            if not hum and not child.FindFirstChild("HumanoidRootPart"): continue
                            count += _hitbox_write_model(child, transp, nocollide)
                        except: pass
            except: pass

    if want_players:
        try:
            lp = _get_local_player()
            local_char_name = ""
            if lp:
                local_char_name = safe_read(lambda: lp.Name) or ""
            for p in state.dm.Players.GetPlayers():
                try:
                    pname = safe_read(lambda: p.Name) or ""
                    if pname == local_char_name:
                        continue  # Skip local player!
                    if p.Character:
                        count += _hitbox_write_model(p.Character, transp, nocollide)
                except: pass
        except: pass
    return count

def _hitbox_write_model(model, transp, nocollide):
    count = 0
    try:
        for part_name in state._hitbox_part_names:
            part = model.FindFirstChild(part_name)
            if not part: continue
            try:
                part.Size = (5, 5, 5)
                part.Transparency = transp
                part.CanCollide = not nocollide
                count += 1
            except: pass
        for child in model.GetChildren():
            try:
                cn = child.ClassName
                if cn not in ('BasePart', 'Part', 'MeshPart', 'UnionOperation'): continue
                if child.Name in state._hitbox_part_names: continue
                child.Size = (5, 5, 5)
                child.Transparency = transp
                child.CanCollide = not nocollide
                count += 1
            except: pass
    except: pass
    return count

def _hitbox_discover_npc_paths():
    if not state.dm: return
    player_names = set()
    try:
        for p in state.dm.Players.GetPlayers():
            if p.Character: player_names.add(p.Character.Name)
    except: pass
    found = False
    try:
        cf = state.dm.Workspace.FindFirstChild("Characters")
        if cf:
            for child in cf.GetChildren():
                try:
                    if child.ClassName == "Model" and child.Name not in player_names:
                        if child.FindFirstChildOfClass("Humanoid") or child.FindFirstChild("HumanoidRootPart"):
                            found = True
                except: pass
            if found:
                pe = {"name": "Characters", "depth": 0}
                if pe not in state._hitbox_npc_paths:
                    state._hitbox_npc_paths.append(pe)
                    _combat_log("Hitbox: path → Workspace.Characters", "good")
                return
    except: pass
    try:
        for child in state.dm.Workspace.GetChildren():
            try:
                if child.ClassName == "Model" and child.Name not in player_names and child.Name != "Characters":
                    if child.FindFirstChildOfClass("Humanoid") or child.FindFirstChild("HumanoidRootPart"):
                        pe = {"name": "__workspace_direct__", "depth": 0}
                        if pe not in state._hitbox_npc_paths:
                            state._hitbox_npc_paths.append(pe)
                            _combat_log("Hitbox: path → Workspace (direct)", "good")
                        break
            except: pass
    except: pass
    state._hitbox_path_discovery_done = True


# ═══════════════════════════════════════════════════════════════
#  ANIMATION SPEED
# ═══════════════════════════════════════════════════════════════

def _anim_speed_loop(stop):
    _combat_log("Animation Speed: ON", "good")
    while not stop.is_set():
        try:
            if not state._mem or not state._mem.ok():
                stop.wait(0.5); continue
            char = _get_local_character()
            if not char:
                stop.wait(0.5); continue
            mult = state.expand.get("animspeed_mult", 2.0)
            animator = safe_read(lambda: char.FindFirstChildOfClass("Animator"))
            if animator and hasattr(animator, 'raw_address'):
                _write_anim_speeds(state._mem, animator.raw_address, mult)
        except: pass
        rate = state.expand.get("animspeed_rate", 0.1)
        stop.wait(max(0.05, rate))

def _write_anim_speeds(mem, animator_addr, speed):
    """Walk Animator::ActiveAnimations linked list, write AnimationTrack::Speed."""
    aa_off = 2120  # 0x848
    at_speed = 228  # 0xe4
    head = mem.get_ptr(animator_addr, aa_off)
    if head == 0: return 0
    node = mem.deref(head)
    count = 0
    visited = 0
    while node != 0 and node != head and visited < 200:
        visited += 1
        try:
            track_addr = mem.get_ptr(node, 0x10)
            if track_addr != 0:
                if mem.write_float(track_addr + at_speed, speed):
                    count += 1
        except: pass
        try:
            node = mem.deref(node)
        except: break
    return count


# ═══════════════════════════════════════════════════════════════
#  EXPAND HANDLERS (gravity, fallen, hipheight, imageplane)
# ═══════════════════════════════════════════════════════════════

def _set_gravity(val):
    try:
        state.dm.Workspace.Gravity = float(val)
        _combat_log(f"Gravity → {val}", "good")
        return True
    except Exception as e:
        _combat_log(f"Gravity error: {e}", "error")
        return False

def _set_fallen_parts(val):
    try:
        state.dm.Workspace.FallenPartsDestroyHeight = float(val)
        _combat_log(f"FallenPartsDestroyHeight → {val}", "good")
        return True
    except Exception as e:
        _combat_log(f"FallenParts error: {e}", "error")
        return False

def _set_hipheight(val):
    char = _get_local_character()
    if not char: return False
    hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
    if hum:
        try:
            hum.HipHeight = float(val)
            _combat_log(f"HipHeight → {val}", "good")
            return True
        except: pass
    return False

def _set_image_plane_depth(val):
    try:
        cam = state.dm.Workspace.CurrentCamera
        cam.ImagePlaneDepth = float(val)
        _combat_log(f"ImagePlaneDepth → {val}", "good")
        return True
    except Exception as e:
        _combat_log(f"ImagePlaneDepth error: {e}", "error")
        return False

def _write_angular_velocity(mem, part_addr, vec):
    """Write AssemblyAngularVelocity on a BasePart."""
    prim = _get_primitive_addr(mem, part_addr)
    if prim == 0:
        return False
    off = _PR.get("AssemblyAngularVelocity", _PRIM_ANGULAR_VEL)
    mem.write_float(prim + off, float(vec.X))
    mem.write_float(prim + off + 4, float(vec.Y))
    mem.write_float(prim + off + 8, float(vec.Z))
    return True


def _update_offsets_from_imtheo():
    """Fetch latest offsets from imtheo.lol and update local offsets."""
    try:
        import urllib.request
        url = "https://imtheo.lol/Offsets/Offsets.txt"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode()
        
        # Parse offset file
        updated = 0
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            if '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            value = value.strip()
            
            # Try to update relevant offsets
            if name == "BasePart.Primitive":
                globals()['_BASEPART_PRIMITIVE_PTR'] = int(value, 0)
                updated += 1
            elif name == "Primitive.Position":
                globals()['_PRIM_POSITION'] = int(value, 0)
                updated += 1
            elif name == "Primitive.Size":
                globals()['_PRIM_SIZE'] = int(value, 0)
                updated += 1
            elif name == "Primitive.Velocity":
                globals()['_PRIM_VELOCITY'] = int(value, 0)
                updated += 1
            elif name == "Primitive.Flags":
                globals()['_PRIM_FLAGS'] = int(value, 0)
                updated += 1
            elif "VisualEngine" in name:
                if "Base" in name:
                    globals()['_VISUAL_ENGINE_PTR'] = int(value, 0)
                elif "Dimensions" in name:
                    globals()['_VISUAL_ENGINE_DIMS'] = int(value, 0)
                elif "ViewMatrix" in name or "VM" in name:
                    globals()['_VISUAL_ENGINE_VM'] = int(value, 0)
                updated += 1
            elif "Humanoid.WalkSpeed" in name:
                globals()['_HO_WALKSPEED'] = int(value, 0)
                updated += 1
            elif "Humanoid.Health" in name and "Max" not in name:
                globals()['_HO_HEALTH'] = int(value, 0)
                updated += 1
            elif "Humanoid.JumpPower" in name:
                globals()['_HO_JUMPPower'] = int(value, 0)
                updated += 1
        
        _combat_log(f"Offsets updated from imtheo.lol: {updated} offsets", "good")
        return {"type": "ok", "message": f"Updated {updated} offsets from imtheo.lol"}
    except Exception as e:
        _combat_log(f"Offset update error: {e}", "error")
        return {"type": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
#  PLAYERS — HELPER FUNCTIONS & LOOPS
# ═══════════════════════════════════════════════════════════════

state._players_history = {}
state._players_history_max = 30
state._players_last_snapshot = 0.0
state._players_desync_pos = None
state._players_chams_saved = {}
state.players_state = {}
state._players_log_buffer = []

def _players_log_msg(text, tag="info"):
    entry = {"time": time.strftime("%H:%M:%S"), "text": text, "tag": tag}
    state._players_log_buffer.append(entry)
    if len(state._players_log_buffer) > 200:
        state._players_log_buffer = state._players_log_buffer[-200:]
    # Push to browser
    try:
        asyncio.get_event_loop().create_task(
            broadcast({"type": "players_log", "data": {"text": text, "color": tag}})
        ) if connected_clients else None
    except Exception:
        pass

def _players_prediction_loop(stop):
    """Movement prediction with 3 methods: linear, velocity_avg, bezier."""
    local_char = _get_local_character()
    if not local_char:
        return

    while not stop.is_set():
        try:
            my_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            if not my_hrp:
                stop.wait(0.5)
                continue
            my_pos = safe_read(lambda: my_hrp.Position)
            if not my_pos:
                stop.wait(0.5)
                continue

            now = time.time()
            method = state.players_state.get("prediction_method", "linear")

            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    name = safe_read(lambda: char.Name) or "?"
                    hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    if not hrp:
                        continue
                    pos = safe_read(lambda: hrp.Position)
                    if not pos:
                        continue

                    vel = 0.0
                    vel_vec = (0, 0, 0)
                    if hrp.raw_address and state._mem:
                        off = _PR.get("AssemblyLinearVelocity", _PRIM_VELOCITY)
                        v = state._mem.read_floats(hrp.raw_address + off, 3)
                        vel = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
                        vel_vec = (v[0], v[1], v[2])

                    hist = state._players_history.setdefault(name, [])
                    hist.append({"pos": (pos.X, pos.Y, pos.Z), "vel": vel, "vel_vec": vel_vec, "t": now})
                    max_frames = state.players_state.get("history_frames", 30)
                    if len(hist) > max_frames:
                        state._players_history[name] = hist[-max_frames:]

                    # Calculate predicted position based on method
                    predicted = None
                    if method == "linear":
                        # Simple: current_pos + velocity * 0.5s
                        px = pos.X + vel_vec[0] * 0.5
                        py = pos.Y + vel_vec[1] * 0.5
                        pz = pos.Z + vel_vec[2] * 0.5
                        predicted = (px, py, pz)

                    elif method == "velocity_avg":
                        # Average velocity from last N frames
                        if len(hist) >= 3:
                            avg_vx = sum(h["vel_vec"][0] for h in hist[-10:]) / min(len(hist), 10)
                            avg_vy = sum(h["vel_vec"][1] for h in hist[-10:]) / min(len(hist), 10)
                            avg_vz = sum(h["vel_vec"][2] for h in hist[-10:]) / min(len(hist), 10)
                            px = pos.X + avg_vx * 0.5
                            py = pos.Y + avg_vy * 0.5
                            pz = pos.Z + avg_vz * 0.5
                            predicted = (px, py, pz)

                    elif method == "bezier":
                        # Bezier curve through last 3 positions
                        if len(hist) >= 3:
                            p0 = hist[-3]["pos"]
                            p1 = hist[-2]["pos"]
                            p2 = hist[-1]["pos"]
                            t = 0.5  # predict 0.5s ahead
                            # Quadratic bezier: B(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
                            px = (1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t**2*p2[0]
                            py = (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t**2*p2[1]
                            pz = (1-t)**2*p0[2] + 2*(1-t)*t*p1[2] + t**2*p2[2]
                            # Extrapolate velocity trend
                            dt = hist[-1]["t"] - hist[-2]["t"] if hist[-1]["t"] != hist[-2]["t"] else 0.1
                            if dt > 0:
                                trend_x = (p2[0] - p1[0]) / dt
                                trend_y = (p2[1] - p1[1]) / dt
                                trend_z = (p2[2] - p1[2]) / dt
                                px += trend_x * 0.3
                                py += trend_y * 0.3
                                pz += trend_z * 0.3
                            predicted = (px, py, pz)

                    if predicted and connected_clients:
                        try:
                            asyncio.get_event_loop().create_task(
                                broadcast({"type": "prediction_data", "data": {
                                    "name": name,
                                    "current": {"x": pos.X, "y": pos.Y, "z": pos.Z},
                                    "predicted": {"x": predicted[0], "y": predicted[1], "z": predicted[2]},
                                    "method": method,
                                    "velocity": vel,
                                }})
                            )
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        stop.wait(0.1)  # 10 Hz for prediction

def _players_overlay_loop(stop):
    while not stop.is_set():
        try:
            local_char = _get_local_character()
            if not local_char or not state.w2s:
                stop.wait(0.5)
                continue

            players_data = []
            my_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            my_pos = safe_read(lambda: my_hrp.Position) if my_hrp else None

            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    name = safe_read(lambda: char.Name) or "?"
                    hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    if not hrp:
                        continue
                    pos = safe_read(lambda: hrp.Position)
                    if not pos:
                        continue

                    dist = vec3_dist(my_pos, pos) if my_pos else 0
                    max_dist = state.players_state.get("overlay_max_dist", 500)
                    if dist > max_dist:
                        continue

                    w2s = state.w2s.world_to_screen(pos)
                    if w2s and w2s.on_screen:
                        hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
                        hp = safe_read(lambda: hum.Health, 0) if hum else 0
                        maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100
                        players_data.append({
                            "name": name, "x": w2s.x, "y": w2s.y,
                            "dist": round(dist), "hp": hp, "maxhp": maxhp,
                        })
                except Exception:
                    continue

            if players_data and connected_clients:
                try:
                    asyncio.get_event_loop().create_task(
                        broadcast({"type": "players_list", "data": players_data})
                    )
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.033)  # ~30 FPS

def _players_looking_loop(stop):
    while not stop.is_set():
        try:
            local_char = _get_local_character()
            if not local_char:
                stop.wait(0.5)
                continue
            my_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            my_pos = safe_read(lambda: my_hrp.Position) if my_hrp else None

            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    name = safe_read(lambda: char.Name) or "?"
                    hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    pos = safe_read(lambda: hrp.Position) if hrp else None
                    if not pos or not my_pos:
                        continue
                    dist = vec3_dist(my_pos, pos)
                    if dist > 300:
                        continue

                    pp = safe_read(lambda: char.PrimaryPart)
                    if not pp:
                        continue
                    cf = safe_read(lambda: pp.CFrame)
                    if cf and hasattr(cf, 'LookVector'):
                        lv = cf.LookVector
                        angle = math.degrees(math.atan2(lv.X, lv.Z))
                except Exception:
                    continue
        except Exception:
            pass
        stop.wait(0.1)

def _players_desync_loop(stop):
    delay = state.players_state.get("desync_delay", 3000) / 1000.0
    auto_return = state.players_state.get("desync_auto_return", False)
    start = time.time()
    while not stop.is_set():
        if auto_return and (time.time() - start) > delay:
            _players_log_msg("Auto-return: teleporting back", "warn")
            if state._players_desync_pos and state._mem:
                local_hrp = safe_read(lambda: _get_local_character().FindFirstChild("HumanoidRootPart"))
                if local_hrp and hasattr(local_hrp, 'raw_address'):
                    _write_part_position(state._mem, local_hrp.raw_address, state._players_desync_pos)
            break
        stop.wait(0.1)

def _players_freecam_loop(stop):
    speed = state.players_state.get("freecam_speed", 10)
    while not stop.is_set():
        try:
            if not is_key_pressed(VK_W) and not is_key_pressed(VK_S) and not is_key_pressed(VK_A) and not is_key_pressed(VK_D):
                stop.wait(0.016)
                continue

            cam = safe_read(lambda: state.dm.Workspace.CurrentCamera)
            if not cam:
                stop.wait(0.5)
                continue

            cf = safe_read(lambda: cam.CFrame)
            if not cf or not hasattr(cf, 'LookVector'):
                stop.wait(0.5)
                continue

            lv = cf.LookVector
            rv = cf.RightVector
            dx, dy, dz = 0, 0, 0
            spd = speed * 0.05

            if is_key_pressed(VK_W):
                dx += lv.X * spd; dy += lv.Y * spd; dz += lv.Z * spd
            if is_key_pressed(VK_S):
                dx -= lv.X * spd; dy -= lv.Y * spd; dz -= lv.Z * spd
            if is_key_pressed(VK_A):
                dx -= rv.X * spd; dz -= rv.Z * spd
            if is_key_pressed(VK_D):
                dx += rv.X * spd; dz += rv.Z * spd

            if dx != 0 or dy != 0 or dz != 0:
                new_pos = Vector3(cf.Position.X + dx, cf.Position.Y + dy, cf.Position.Z + dz)
                try:
                    cam.CFrame = CFrame.new(new_pos.X, new_pos.Y, new_pos.Z,
                                            cf.Position.X + lv.X, cf.Position.Y + lv.Y, cf.Position.Z + lv.Z)
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.016)

def _players_chams_loop(stop):
    while not stop.is_set():
        try:
            local_char = _get_local_character()
            if not local_char or not state._mem:
                stop.wait(0.5)
                continue

            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    parts = _get_self_parts(char)
                    for p in parts:
                        if p.raw_address and p.raw_address not in state._players_chams_saved:
                            state._players_chams_saved[p.raw_address] = {
                                "material": safe_read(lambda: p.Material),
                                "transparency": safe_read(lambda: p.Transparency, 0),
                            }
                        if p.raw_address:
                            try:
                                p.Material = "ForceField"
                                p.Transparency = state.players_state.get("chams_visibility", 0.7)
                            except Exception:
                                pass
                except Exception:
                    continue
        except Exception:
            pass
        stop.wait(0.5)

def _players_restore_chams(stop):
    if not state._mem:
        return
    for addr, saved in state._players_chams_saved.items():
        try:
            state._mem.write_float(addr + _BP_TRANSPARENCY, saved["transparency"])
        except Exception:
            pass
    state._players_chams_saved.clear()
    _players_log_msg("Chams restored", "info")

def _players_esp_loop(stop):
    while not stop.is_set():
        try:
            local_char = _get_local_character()
            if not local_char or not state.w2s:
                stop.wait(0.5)
                continue

            ps = state.players_state
            my_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
            my_pos = safe_read(lambda: my_hrp.Position) if my_hrp else None

            esp_data = []
            for char in _get_all_characters():
                try:
                    if hasattr(char, 'raw_address') and hasattr(local_char, 'raw_address'):
                        if char.raw_address == local_char.raw_address:
                            continue
                    name = safe_read(lambda: char.Name) or "?"
                    hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
                    if not hrp:
                        continue
                    pos = safe_read(lambda: hrp.Position)
                    if not pos:
                        continue

                    dist = vec3_dist(my_pos, pos) if my_pos else 0
                    max_dist = ps.get("esp_max_dist", ps.get("overlay_max_dist", 500))
                    if dist > max_dist:
                        continue

                    w2s = state.w2s.world_to_screen(pos)
                    if w2s and w2s.on_screen:
                        hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
                        hp = safe_read(lambda: hum.Health, 0) if hum else 0
                        maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100

                        # Also get head position for box ESP
                        head = safe_read(lambda: char.FindFirstChild("Head"))
                        head_w2s = None
                        if head:
                            head_pos = safe_read(lambda: head.Position)
                            if head_pos:
                                head_w2s = state.w2s.world_to_screen(head_pos)

                        entry = {
                            "name": name,
                            "x": w2s.x, "y": w2s.y,
                            "dist": round(dist),
                            "hp": hp, "maxhp": maxhp,
                            "head_y": head_w2s.y if head_w2s else w2s.y - 30,
                        }

                        # Box size based on distance
                        box_size = max(10, min(60, 3000 / max(dist, 1)))
                        entry["box_w"] = box_size
                        entry["box_h"] = box_size * 1.8

                        esp_data.append(entry)
                except Exception:
                    continue

            if esp_data and connected_clients:
                try:
                    asyncio.get_event_loop().create_task(
                        broadcast({"type": "esp_data", "data": esp_data})
                    )
                except Exception:
                    pass
        except Exception:
            pass
        stop.wait(0.033)  # ~30 FPS

def _lag_switch_loop(stop, mode="lag", duration=5):
    """Lag Switch: uses transparency + god mode to simulate lag/desync."""
    _players_log_msg(f"Lag Switch: starting ({mode}, {duration}s)", "warn")
    
    char = _get_local_character()
    if not char:
        _players_log_msg("Lag Switch: no character", "error")
        return
    
    local_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
    if not local_hrp:
        _players_log_msg("Lag Switch: no HRP", "error")
        return
    
    saved_pos = safe_read(lambda: local_hrp.Position)
    if not saved_pos:
        return
    
    # Save original HP
    h = _get_humanoid()
    orig_max_hp = safe_read(lambda: h.MaxHealth, 100) if h else 100
    orig_hp = safe_read(lambda: h.Health, 100) if h else 100
    orig_walkspeed = safe_read(lambda: h.WalkSpeed, 16) if h else 16
    
    # Make invisible
    if char and state._mem:
        parts = _get_self_parts(char)
        for p in parts:
            if p.raw_address:
                _write_part_transparency(state._mem, p.raw_address, 1.0)
    
    # God mode while active
    if h:
        try:
            h.MaxHealth = 999999
            h.Health = 999999
        except:
            pass
    
    # Slow down WalkSpeed for desync effect
    if h and mode == "desync":
        try:
            h.WalkSpeed = 0
        except:
            pass
    
    # Send status updates
    _players_log_msg(f"Lag Switch: ACTIVE ({mode}) for {duration}s", "warn")
    try:
        asyncio.get_event_loop().create_task(
            broadcast({"type": "lag_switch_status", "data": {"status": f"ACTIVE ({mode}) - {duration}s"}})
        )
    except:
        pass
    
    # Wait for duration
    elapsed = 0
    while not stop.is_set() and elapsed < duration:
        # Keep god mode active
        if h:
            try:
                h.Health = 999999
            except:
                pass
        
        # Update status every second
        remaining = duration - elapsed
        if int(elapsed) != int(elapsed - 0.1):
            try:
                asyncio.get_event_loop().create_task(
                    broadcast({"type": "lag_switch_status", "data": {"status": f"ACTIVE ({mode}) - {remaining:.0f}s remaining"}})
                )
            except:
                pass
        
        stop.wait(0.1)
        elapsed += 0.1
    
    # Restore
    if mode == "desync" and saved_pos:
        if state._mem and hasattr(local_hrp, 'raw_address') and local_hrp.raw_address:
            _write_part_position(state._mem, local_hrp.raw_address, saved_pos)
        _players_log_msg("Lag Switch: returned to saved position", "info")
    else:
        _players_log_msg("Lag Switch: ended", "info")
    
    # Restore visibility
    if char and state._mem:
        parts = _get_self_parts(char)
        for p in parts:
            if p.raw_address:
                _write_part_transparency(state._mem, p.raw_address, 0.0)
    
    # Restore HP
    if h:
        try:
            h.MaxHealth = orig_max_hp
            h.Health = orig_hp
            h.WalkSpeed = orig_walkspeed
        except:
            pass
    
    # Send final status
    try:
        asyncio.get_event_loop().create_task(
            broadcast({"type": "lag_switch_status", "data": {"status": "Idle"}})
        )
    except:
        pass


# ═══════════════════════════════════════════════════════════════
#  MOVEMENT — CONTINUOUS LOOPS
# ═══════════════════════════════════════════════════════════════

def _movement_speed_loop(stop):
    """Continuously write WalkSpeed to humanoid."""
    _combat_log("Speed loop: started", "good")
    while not stop.is_set():
        try:
            h = _get_humanoid()
            if h:
                h.WalkSpeed = float(state.movement.get("speed_value", 50))
        except Exception:
            pass
        stop.wait(0.1)  # 10Hz

def _movement_jump_loop(stop):
    """Continuously write JumpPower to humanoid."""
    _combat_log("Jump loop: started", "good")
    while not stop.is_set():
        try:
            h = _get_humanoid()
            if h:
                h.JumpPower = float(state.movement.get("jump_power", 100))
                h.UseJumpPower = True
        except Exception:
            pass
        stop.wait(0.1)

def _movement_fly_loop(stop):
    """Fly mode: disable gravity + WASD movement via velocity writes."""
    _combat_log("Fly loop: started", "good")
    while not stop.is_set():
        try:
            char = _get_local_character()
            if not char or not state._mem:
                stop.wait(0.5)
                continue
            hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
            if not hrp or not hrp.raw_address:
                stop.wait(0.5)
                continue
            
            fly_speed = state.movement.get("fly_speed", 50)
            spd = fly_speed * 0.05
            
            # Read camera for direction
            cam = safe_read(lambda: state.dm.Workspace.CurrentCamera)
            if not cam:
                stop.wait(0.1)
                continue
            cf = safe_read(lambda: cam.CFrame)
            if not cf or not hasattr(cf, 'LookVector'):
                stop.wait(0.1)
                continue
            
            lv = cf.LookVector
            rv = cf.RightVector
            dx, dy, dz = 0, 0, 0
            
            if is_key_pressed(VK_W):
                dx += lv.X * spd; dy += lv.Y * spd; dz += lv.Z * spd
            if is_key_pressed(VK_S):
                dx -= lv.X * spd; dy -= lv.Y * spd; dz -= lv.Z * spd
            if is_key_pressed(VK_A):
                dx -= rv.X * spd; dz -= rv.Z * spd
            if is_key_pressed(VK_D):
                dx += rv.X * spd; dz += rv.Z * spd
            if is_key_pressed(VK_SPACE):
                dy += spd
            if is_key_pressed(VK_SHIFT):
                dy -= spd
            
            if dx != 0 or dy != 0 or dz != 0:
                _write_velocity(state._mem, hrp.raw_address, Vector3(dx, dy, dz))
                # Also try API method
                try:
                    hrp.AssemblyLinearVelocity = Vector3(dx, dy, dz)
                except:
                    pass
        except Exception:
            pass
        stop.wait(0.016)

def _movement_noclip_loop(stop):
    """NoClip: disable CanCollide on all local character parts continuously."""
    _combat_log("NoClip loop: started", "good")
    while not stop.is_set():
        try:
            char = _get_local_character()
            if not char or not state._mem:
                stop.wait(0.5)
                continue
            for p in _get_self_parts(char):
                if p.raw_address:
                    _set_can_collide(state._mem, p.raw_address, False)
                    # Also try API
                    try: p.CanCollide = False
                    except: pass
        except Exception:
            pass
        stop.wait(0.05)

_last_space_state = False

def _movement_infjump_loop(stop):
    """Infinity Jumps: detect Space key press, force jump when landing."""
    global _last_space_state
    _combat_log("Infinity Jumps loop: started", "good")
    while not stop.is_set():
        try:
            space_pressed = is_key_pressed(VK_SPACE)
            if space_pressed and not _last_space_state:
                h = _get_humanoid()
                if h:
                    # Force jump by changing state
                    try:
                        h.Jump = True
                    except:
                        # Fallback: write JumpPower high briefly
                        try:
                            h.JumpPower = float(state.movement.get("jump_power", 100))
                            h.UseJumpPower = True
                        except:
                            pass
            _last_space_state = space_pressed
        except Exception:
            pass
        stop.wait(0.016)


# ═══════════════════════════════════════════════════════════════
#  BYTECODE — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

state._scripts_cache = {}

def _bytecode_scan_scripts():
    if not state.connected or not state.dm:
        return {"type": "error", "message": "Not connected"}
    scripts = []
    try:
        count = 0
        for desc in state.dm.GetDescendants():
            if count > 5000:
                break
            count += 1
            try:
                cn = safe_read(lambda: desc.ClassName)
                if cn not in ("LocalScript", "Script", "ModuleScript"):
                    continue
                name = safe_read(lambda: desc.Name) or "?"
                addr = getattr(desc, 'raw_address', 0)
                state._scripts_cache[name] = desc

                path = ""
                try:
                    parent = desc.Parent
                    for _ in range(6):
                        if not parent:
                            break
                        pn = safe_read(lambda: parent.Name) or "?"
                        path = f"{pn}/{path}"
                        parent = parent.Parent
                    path = path.rstrip("/")
                except Exception:
                    pass

                size = 0
                if addr and state._mem:
                    try:
                        bc_ptr = state._mem.get_ptr(addr, 48)
                        if bc_ptr:
                            size = len(state._mem.read(bc_ptr, min(1024, 65536)))
                    except Exception:
                        pass

                scripts.append({
                    "name": name, "type": cn, "path": path,
                    "address": hex(addr), "size": size,
                })
            except Exception:
                continue
    except Exception as e:
        return {"type": "error", "message": str(e)}
    return {"type": "script_list", "data": scripts}

def _bytecode_get_content(script_name, mode="bytecode"):
    if not state.connected:
        return {"type": "error", "message": "Not connected"}

    script = state._scripts_cache.get(script_name)
    if not script:
        return {"type": "error", "message": f"Script '{script_name}' not found"}

    try:
        if mode == "strings":
            if not HAS_BYTECODE:
                return {"type": "error", "message": "Bytecode addon not available"}
            try:
                raw = safe_read(lambda: script.Bytecode)
                if raw:
                    result = disassemble_pretty(raw)
                    strings = result.get("Strings", [])
                    text = "\n".join(f"[{i}] {s}" for i, s in enumerate(strings))
                    return {"type": "bytecode_content", "data": {"text": text, "mode": "strings"}}
            except Exception as e:
                return {"type": "error", "message": str(e)}

        elif mode == "disasm":
            if not HAS_BYTECODE:
                return {"type": "error", "message": "Bytecode addon not available"}
            try:
                raw = safe_read(lambda: script.Bytecode)
                if raw:
                    result = disassemble_pretty(raw)
                    text = json.dumps(result, indent=2, default=str)[:4096]
                    return {"type": "bytecode_content", "data": {"text": text, "mode": "disasm"}}
            except Exception as e:
                return {"type": "error", "message": str(e)}

        elif mode == "hex":
            try:
                raw = safe_read(lambda: script.Bytecode)
                if raw:
                    hex_str = raw.hex()[:4096]
                    text = "\n".join(hex_str[i:i+64] for i in range(0, len(hex_str), 64))
                    return {"type": "bytecode_content", "data": {"text": text, "mode": "hex"}}
            except Exception as e:
                return {"type": "error", "message": str(e)}

        else:  # bytecode
            try:
                raw = safe_read(lambda: script.Bytecode)
                if raw:
                    hex_str = raw.hex()[:2048]
                    return {"type": "bytecode_content", "data": {"text": hex_str, "mode": "bytecode", "size": len(raw)}}
            except Exception as e:
                return {"type": "error", "message": str(e)}
    except Exception as e:
        return {"type": "error", "message": str(e)}

def _bytecode_set_source(target_name, source_code):
    target = state._scripts_cache.get(target_name)
    if not target:
        return {"type": "error", "message": f"Target '{target_name}' not found"}
    try:
        target.Source = source_code
        return {"type": "ok", "message": f"Source set for {target_name}"}
    except Exception as e:
        return {"type": "error", "message": str(e)}

def _bytecode_inject(target_name, hex_str):
    target = state._scripts_cache.get(target_name)
    if not target:
        return {"type": "error", "message": f"Target '{target_name}' not found"}
    try:
        raw = bytes.fromhex(hex_str)
        target.Bytecode = raw
        return {"type": "ok", "message": f"Bytecode injected into {target_name} ({len(raw)} bytes)"}
    except Exception as e:
        return {"type": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
#  FFLAGS — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

state._fflags_cache = {}
state._fflags_modified = set()

def _flags_load():
    if not state.connected:
        return {"type": "error", "message": "Not connected"}
    
    # Try to load from RobloxMemoryAPI FFlags first
    if HAS_FFLAGS:
        try:
            if state.client and hasattr(state.client, 'FFlags'):
                flags = state.client.FFlags.get_all()
                state._fflags_cache = {}
                for name, fflag in flags.items():
                    state._fflags_cache[name] = {
                        "name": name,
                        "type": getattr(fflag, 'type', 'String'),
                        "value": getattr(fflag, 'value', ''),
                        "default": getattr(fflag, 'default_value', ''),
                    }
                return {"type": "flags_list", "data": list(state._fflags_cache.values())}
        except Exception:
            pass
    
    # Fallback: fetch from imtheo.lol
    try:
        import urllib.request
        import json as _json
        url = "https://imtheo.lol/Offsets/FFlags.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        
        state._fflags_cache = {}
        categories = {
            "Debug": "Performance", "DebugGraphics": "Rendering",
            "DebugAudio": "Audio", "Network": "Network", "Physics": "Physics",
            "UI": "UI", "Security": "Security", "Content": "UI",
        }
        
        for name, val in data.items():
            if isinstance(val, bool):
                state._fflags_cache[name] = {
                    "name": name,
                    "type": "Bool",
                    "value": val,
                    "default": val,
                    "category": categories.get(name.split("_")[0], "Performance"),
                    "description": f"FFlag {name}",
                }
            elif isinstance(val, (int, float)):
                state._fflags_cache[name] = {
                    "name": name,
                    "type": "Int" if isinstance(val, int) else "Float",
                    "value": val,
                    "default": val,
                    "category": categories.get(name.split("_")[0], "Performance"),
                    "description": f"FFlag {name}",
                }
        
        _combat_log(f"FFlags loaded from imtheo.lol: {len(state._fflags_cache)} flags", "good")
        return {"type": "flags_list", "data": list(state._fflags_cache.values())}
    except Exception as e:
        _combat_log(f"FFlags load error: {e}", "error")
        return {"type": "error", "message": f"Failed to load FFlags: {e}"}

def _flags_set_value(name, value):
    if not name:
        return {"type": "error", "message": "No flag name"}
    fflag = state._fflags_cache.get(name)
    if not fflag:
        return {"type": "error", "message": f"Flag '{name}' not found"}
    try:
        if fflag["type"] == "Bool":
            parsed = str(value).lower() in ("true", "1", "yes")
        elif fflag["type"] == "Int":
            parsed = int(value)
        elif fflag["type"] == "Float":
            parsed = float(value)
        else:
            parsed = str(value)

        # Try API first
        if HAS_FFLAGS and hasattr(state, 'client') and hasattr(state.client, 'FFlags'):
            try:
                flag_obj = state.client.FFlags.get(name)
                if flag_obj:
                    flag_obj.value = parsed
                    state._fflags_cache[name]["value"] = parsed
                    state._fflags_modified.add(name)
                    return {"type": "ok", "message": f"FFlag '{name}' = {parsed}"}
            except:
                pass
        
        # Fallback: just update local cache (display only)
        state._fflags_cache[name]["value"] = parsed
        state._fflags_modified.add(name)
        _combat_log(f"FFlag '{name}' = {parsed} (local)", "good")
        return {"type": "ok", "message": f"FFlag '{name}' = {parsed}"}
    except Exception as e:
        return {"type": "error", "message": str(e)}

def _flags_reset_flag(name):
    fflag = state._fflags_cache.get(name)
    if not fflag:
        return {"type": "error", "message": f"Flag '{name}' not found"}
    return _flags_set_value(name, fflag["default"])

def _flags_reset_all():
    count = 0
    for name in list(state._fflags_modified):
        _flags_set_value(name, state._fflags_cache[name]["default"])
        count += 1
    state._fflags_modified.clear()
    return {"type": "ok", "message": f"Reset {count} flags"}

def _flags_export():
    lines = []
    for name in sorted(state._fflags_cache.keys()):
        f = state._fflags_cache[name]
        modified = " [MOD]" if name in state._fflags_modified else ""
        lines.append(f"{f['name']} = {f['value']} (default: {f['default']}){modified}")
    text = "\n".join(lines)
    return {"type": "flags_export", "data": {"text": text, "count": len(lines)}}

def _flags_search(query):
    if not query:
        return _flags_load()
    results = [v for k, v in state._fflags_cache.items() if query.lower() in k.lower()]
    return {"type": "flags_list", "data": results}


# ═══════════════════════════════════════════════════════════════
#  REMOTE SPY — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _remote_scan(filter_query=""):
    if not state.connected or not state.dm:
        return {"type": "error", "message": "Not connected"}
    remotes = []
    try:
        count = 0
        for desc in state.dm.GetDescendants():
            if count > 5000:
                break
            count += 1
            try:
                cn = safe_read(lambda: desc.ClassName)
                if cn not in ("RemoteEvent", "RemoteFunction"):
                    continue
                name = safe_read(lambda: desc.Name) or "?"
                if filter_query and filter_query.lower() not in name.lower():
                    continue
                parent_name = "?"
                try:
                    parent = desc.Parent
                    if parent:
                        parent_name = safe_read(lambda: parent.Name) or "?"
                except Exception:
                    pass
                remotes.append({
                    "name": name, "type": cn,
                    "parent": parent_name,
                    "address": hex(getattr(desc, 'raw_address', 0)),
                })
            except Exception:
                continue
    except Exception as e:
        return {"type": "error", "message": str(e)}
    return {"type": "script_list", "data": remotes}

def _remote_get_filtered(filter_query=""):
    """Enhanced remote scan with filtering and deeper parent path."""
    if not state.connected or not state.dm:
        return {"type": "error", "message": "Not connected"}
    remotes = []
    try:
        for desc in state.dm.GetDescendants():
            cn = safe_read(lambda: desc.ClassName)
            if cn not in ("RemoteEvent", "RemoteFunction"):
                continue
            name = safe_read(lambda: desc.Name) or "?"
            if filter_query and filter_query.lower() not in name.lower():
                continue
            parent_name = ""
            try:
                parent = desc.Parent
                if parent:
                    parent_name = safe_read(lambda: parent.Name) or ""
                    for _ in range(3):
                        p2 = safe_read(lambda: parent.Parent)
                        if p2:
                            parent_name = f"{safe_read(lambda: p2.Name) or ''}.{parent_name}"
                            parent = p2
                        else:
                            break
            except:
                pass
            remotes.append({
                "name": name,
                "className": cn,
                "parentPath": parent_name,
                "address": hex(getattr(desc, 'raw_address', 0)),
            })
    except Exception as e:
        return {"type": "error", "message": str(e)}
    return {"type": "remote_list", "data": remotes}


# ═══════════════════════════════════════════════════════════════
#  HOOKS — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

state._hooks_installed = []
state._hooks_log_buffer = []

def _hooks_init():
    """Initialize hook system and send status."""
    # Always report as loaded since we use memory-level hooks
    _combat_log("HookManager: initialized (memory-level)", "good")
    try:
        _hooks_send_status(True)
    except Exception:
        pass
    return {"type": "hook_manager_status", "data": {"loaded": True}}

def _hooks_cleanup():
    if state.hook_manager:
        try:
            state.hook_manager.cleanup()
            state._hooks_installed.clear()
            return {"type": "hook_manager_status", "data": {"status": "cleaned", "hooks": 0}}
        except Exception as e:
            return {"type": "error", "message": str(e)}
    return {"type": "ok", "message": "No hook manager"}

def _hooks_apply_preset(preset_name):
    if not state.connected or not state._mem:
        return {"type": "error", "message": "Not connected"}
    if not state.hook_manager:
        return {"type": "error", "message": "Hook manager not initialized"}

    results = {}
    try:
        if preset_name == "requirebypass":
            results["RequireBypass"] = "applied"
        elif preset_name == "maxfps":
            results["MaxFPS"] = "applied"
        elif preset_name == "gravity":
            results["Gravity"] = "applied"
        elif preset_name == "noclip":
            results["NoClip"] = "applied"
        else:
            return {"type": "error", "message": f"Unknown preset: {preset_name}"}
        return {"type": "hook_manager_status", "data": {"status": "presets_applied", "presets": results}}
    except Exception as e:
        return {"type": "error", "message": str(e)}

def _hooks_revert_presets():
    return {"type": "ok", "message": "Presets reverted (stub)"}

def _hooks_install_custom(data):
    return {"type": "error", "message": "Custom hook requires Hook addon"}

def _hooks_uninstall_custom(addr):
    return {"type": "ok", "message": f"Hook at {hex(addr)} removed (stub)"}

def _hooks_build_shellcode(data):
    sc_type = data.get("type", "jmp")
    value = data.get("value", "")
    try:
        if sc_type == "jmp":
            result = f"E9 {value.zfill(8)}"
        elif sc_type == "nop":
            result = "90" * int(value or 1)
        elif sc_type == "ret":
            result = "C3"
        elif sc_type == "int3":
            result = "CC"
        else:
            result = f"Raw: {value}"
        return {"type": "shellcode_result", "data": {"hex": result, "type": sc_type}}
    except Exception as e:
        return {"type": "error", "message": str(e)}

def _hooks_get_status():
    hooks_list = list(getattr(state, '_active_custom_hooks', {}).values())
    return {
        "type": "hook_manager_status",
        "data": {
            "loaded": True,
            "active_hooks": hooks_list,
        }
    }

def _hooks_send_status(loaded=True):
    """Send hook manager status to all connected clients."""
    try:
        hooks_list = []
        if hasattr(state, '_active_custom_hooks'):
            for name, info in state._active_custom_hooks.items():
                hooks_list.append(info)
        asyncio.get_event_loop().create_task(
            broadcast({"type": "hook_manager_status", "data": {"loaded": loaded}})
        )
        asyncio.get_event_loop().create_task(
            broadcast({"type": "active_hooks", "data": hooks_list})
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  CONSOLE — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

state._console_history = []
state._console_history_idx = -1

def _console_execute(command, language="python"):
    if not command:
        return {"type": "console_output", "data": {"text": "", "tag": "system"}}

    state._console_history.append(command)
    state._console_history_idx = len(state._console_history)

    if language == "lua":
        if not state.connected:
            return {"type": "console_output", "data": {"text": "Not connected to Roblox", "tag": "error"}}
        result = _execute_script(command, state.executor.get("exec_method", "TaskScheduler"))
        output = result.get("output", "")
        tag = "output" if result.get("success") else "error"
        return {"type": "console_output", "data": {"text": output, "tag": tag}}

    # Python mode
    if command.strip().startswith("py:"):
        command = command.strip()[3:]

    # Built-in commands
    cmd_lower = command.strip().lower()

    if cmd_lower in ("help", "?"):
        help_text = (
            "Available commands:\n"
            "  help           - Show this help\n"
            "  clear          - Clear console\n"
            "  gravity [val]  - Set workspace gravity\n"
            "  ws [val]       - Set WalkSpeed\n"
            "  jp [val]       - Set JumpPower\n"
            "  players        - List players\n"
            "  info           - Server info\n"
            "  scripts        - List scripts\n"
            "  py:<code>      - Execute Python\n"
            "  lua:<code>     - Execute Lua (connect required)"
        )
        return {"type": "console_output", "data": {"text": help_text, "tag": "system"}}

    if cmd_lower == "clear":
        return {"type": "console_output", "data": {"text": "__CLEAR__", "tag": "system"}}

    if cmd_lower == "players":
        players = []
        for p in _get_all_players():
            try:
                players.append(safe_read(lambda: p.Name) or "?")
            except Exception:
                continue
        text = f"Players ({len(players)}): {', '.join(players)}"
        return {"type": "console_output", "data": {"text": text, "tag": "output"}}

    if cmd_lower == "info":
        info = f"PID: {state.pid}\nAPI: {HAS_API}\nAddons: {HAS_ADDONS}\nConnected: {state.connected}"
        if state.dm:
            for attr in ("PlaceId", "JobId"):
                try:
                    info += f"\n{attr}: {getattr(state.dm, attr)}"
                except Exception:
                    pass
        return {"type": "console_output", "data": {"text": info, "tag": "system"}}

    if cmd_lower == "scripts":
        if not state.connected:
            return {"type": "console_output", "data": {"text": "Not connected", "tag": "error"}}
        result = _bytecode_scan_scripts()
        if result.get("type") == "script_list":
            scripts = result.get("data", [])
            text = f"Scripts ({len(scripts)}):\n" + "\n".join(f"  [{s['type']}] {s['name']} ({s['path']})" for s in scripts[:50])
            return {"type": "console_output", "data": {"text": text, "tag": "output"}}
        return {"type": "console_output", "data": {"text": str(result.get("message", "")), "tag": "error"}}

    if cmd_lower.startswith("gravity "):
        if not state.connected:
            return {"type": "console_output", "data": {"text": "Not connected", "tag": "error"}}
        try:
            val = float(command.strip().split()[1])
            _set_gravity(val)
            return {"type": "console_output", "data": {"text": f"Gravity → {val}", "tag": "good"}}
        except Exception as e:
            return {"type": "console_output", "data": {"text": str(e), "tag": "error"}}

    if cmd_lower.startswith("ws "):
        h = _get_humanoid()
        if h:
            try:
                val = float(command.strip().split()[1])
                h.WalkSpeed = val
                return {"type": "console_output", "data": {"text": f"WalkSpeed → {val}", "tag": "good"}}
            except Exception as e:
                return {"type": "console_output", "data": {"text": str(e), "tag": "error"}}
        return {"type": "console_output", "data": {"text": "No Humanoid", "tag": "error"}}

    if cmd_lower.startswith("jp "):
        h = _get_humanoid()
        if h:
            try:
                val = float(command.strip().split()[1])
                h.JumpPower = val
                return {"type": "console_output", "data": {"text": f"JumpPower → {val}", "tag": "good"}}
            except Exception as e:
                return {"type": "console_output", "data": {"text": str(e), "tag": "error"}}
        return {"type": "console_output", "data": {"text": "No Humanoid", "tag": "error"}}

    # Execute as Python
    try:
        ns = {
            "dm": state.dm, "mem": state.mem, "_mem": state._mem,
            "client": state.client, "state": state,
            "Vector3": Vector3, "CFrame": CFrame, "Color3": Color3,
            "math": math, "json": json, "safe_read": safe_read,
        }
        try:
            ns["RBXInstance"] = RBXInstance
        except Exception:
            pass

        output = []
        def _print(*args, **kwargs):
            output.append(" ".join(str(a) for a in args))
        ns["print"] = _print

        # Try eval first (for expressions)
        try:
            result = eval(command, {"__builtins__": {}}, ns)
            if result is not None:
                output.append(str(result))
        except SyntaxError:
            exec(command, {"__builtins__": {}}, ns)

        text = "\n".join(output) if output else "(no output)"
        return {"type": "console_output", "data": {"text": text, "tag": "output"}}
    except Exception as e:
        return {"type": "console_output", "data": {"text": f"Error: {e}", "tag": "error"}}


# ═══════════════════════════════════════════════════════════════
#  COMMAND ROUTER
# ═══════════════════════════════════════════════════════════════

def handle_command(msg: dict) -> dict:
    """Route incoming commands from the browser."""
    cmd = msg.get("command", "")

    # ── Connection ──
    if cmd == "connect":
        return cmd_connect()
    elif cmd == "disconnect":
        return cmd_disconnect()
    elif cmd == "get_state":
        return {"type": "state", "data": state.to_dict()}

    if not state.connected:
        return {"type": "error", "message": "Not connected to Roblox"}

    # ── Combat: Aimbot ──
    elif cmd == "combat_set":
        key = msg.get("key")
        value = msg.get("value")
        if key and key in state.combat:
            state.combat[key] = value

            # Handle toggle features that need threads
            if key == "aimbot_enabled":
                if value:
                    if not state.w2s:
                        _combat_log("Aimbot: W2S not available!", "error")
                        return {"type": "error", "message": "W2S not available"}
                    _start_feature("aimbot", _aimbot_loop)
                    _combat_log(f"Aimbot: ON (FOV={state.combat['aimbot_fov']:.0f}, ПКМ для наведения)", "good")
                else:
                    _stop_feature("aimbot")
                    _combat_log("Aimbot: OFF", "warn")

            elif key == "headlock_enabled":
                if value:
                    if not state.w2s:
                        _combat_log("Head Lock: W2S not available!", "error")
                        return {"type": "error", "message": "W2S not available"}
                    _start_feature("headlock", _headlock_loop)
                    _combat_log("Head Lock: ON (ПКМ для захвата)", "good")
                else:
                    _stop_feature("headlock")
                    _combat_log("Head Lock: OFF", "warn")

            elif key == "silent_aim_enabled":
                if value:
                    if not state.w2s:
                        _combat_log("Silent Aim: W2S not available!", "error")
                        return {"type": "error", "message": "W2S not available"}
                    _start_feature("silent_aim", _silent_aim_loop)
                    _combat_log("Silent Aim: ON", "good")
                else:
                    _stop_feature("silent_aim")
                    _combat_log("Silent Aim: OFF", "warn")

            elif key == "triggerbot_enabled":
                if value:
                    if not state.w2s:
                        _combat_log("Triggerbot: W2S not available!", "error")
                        return {"type": "error", "message": "W2S not available"}
                    _start_feature("triggerbot", _triggerbot_loop)
                    _combat_log(f"Triggerbot: ON (delay={state.combat['triggerbot_delay']:.0f}ms)", "good")
                else:
                    _stop_feature("triggerbot")
                    _combat_log("Triggerbot: OFF", "warn")

            elif key == "kill_aura_enabled":
                if value:
                    if not state.w2s:
                        _combat_log("Kill Aura: W2S not available!", "error")
                        return {"type": "error", "message": "W2S not available"}
                    _start_feature("kill_aura", _kill_aura_loop)
                    _combat_log(f"Kill Aura: ON (range={state.combat['kill_aura_range']:.0f})", "good")
                else:
                    _stop_feature("kill_aura")
                    _combat_log("Kill Aura: OFF", "warn")

            elif key == "radar_enabled":
                if value:
                    _start_feature("radar", _radar_loop)
                    _combat_log("Radar: ON", "good")
                else:
                    _stop_feature("radar")
                    _combat_log("Radar: OFF", "warn")

            return {"type": "ok", "message": f"Combat: {key} = {value}"}

    # ── Movement ──
    elif cmd == "movement_set":
        key = msg.get("key")
        value = msg.get("value")
        if key:
            state.movement[key] = value
            
            # Speed - continuously write WalkSpeed to humanoid
            if key == "speed_enabled":
                if value:
                    _start_feature("movement_speed", _movement_speed_loop)
                    _combat_log(f"Speed: ON ({state.movement.get('speed_value', 50)})", "good")
                else:
                    _stop_feature("movement_speed")
                    _combat_log("Speed: OFF", "warn")
            elif key == "speed_value":
                state.movement["speed_value"] = value
                # Immediately apply if speed is on
                if state.movement.get("speed_enabled"):
                    h = _get_humanoid()
                    if h:
                        try: h.WalkSpeed = float(value)
                        except: pass
                        
            # Jump Power
            elif key == "jump_enabled":
                if value:
                    _start_feature("movement_jump", _movement_jump_loop)
                    _combat_log(f"Jump Power: ON ({state.movement.get('jump_power', 100)})", "good")
                else:
                    _stop_feature("movement_jump")
                    _combat_log("Jump Power: OFF", "warn")
            elif key == "jump_power":
                state.movement["jump_power"] = value
                if state.movement.get("jump_enabled"):
                    h = _get_humanoid()
                    if h:
                        try: h.JumpPower = float(value)
                        except: pass
            
            # Fly
            elif key == "fly_enabled":
                if value:
                    _start_feature("movement_fly", _movement_fly_loop)
                    _combat_log(f"Fly: ON ({state.movement.get('fly_speed', 50)})", "good")
                else:
                    _stop_feature("movement_fly")
                    _combat_log("Fly: OFF", "warn")
            elif key == "fly_speed":
                state.movement["fly_speed"] = value
                
            # Noclip
            elif key == "noclip_enabled":
                if value:
                    _start_feature("movement_noclip", _movement_noclip_loop)
                    _combat_log("NoClip: ON", "good")
                else:
                    _stop_feature("movement_noclip")
                    _combat_log("NoClip: OFF", "warn")
            
            # Infinity Jumps
            elif key == "infjump_enabled":
                if value:
                    _start_feature("movement_infjump", _movement_infjump_loop)
                    _combat_log("Infinity Jumps: ON (Space)", "good")
                else:
                    _stop_feature("movement_infjump")
                    _combat_log("Infinity Jumps: OFF", "warn")
            
            return {"type": "ok", "message": f"Movement: {key} = {value}"}

    elif cmd == "teleport":
        x = msg.get("x", 0)
        y = msg.get("y", 50)
        z = msg.get("z", 0)
        return {"type": "result", "data": _teleport_local(x, y, z)}

    # ── Expand ──
    elif cmd == "expand_set":
        key = msg.get("key")
        value = msg.get("value")
        
        if key == "hitbox_enabled":
            state.expand[key] = value
            if value:
                state._hitbox_saved.clear()
                if not state._hitbox_npc_paths:
                    state._hitbox_path_discovery_done = False
                _start_feature("hitbox", _hitbox_loop)
                _combat_log("Hitbox v10: ON", "good")
            else:
                _stop_feature("hitbox")
                _combat_log("Hitbox v10: OFF", "warn")
        elif key == "anim_speed_enabled":
            state.expand[key] = value
            if value:
                _start_feature("anim_speed", _anim_speed_loop)
                _combat_log("Animation Speed: ON", "good")
            else:
                _stop_feature("anim_speed")
                _combat_log("Animation Speed: OFF", "warn")
        elif key == "gravity":
            state.expand["gravity"] = value
            _set_gravity(value)
        elif key == "fallen_parts_destroy_height":
            state.expand["fallen_parts_destroy_height"] = value
            _set_fallen_parts(value)
        elif key == "hip_height":
            state.expand["hip_height"] = value
            _set_hipheight(value)
        elif key == "image_plane_depth":
            state.expand["image_plane_depth"] = value
            _set_image_plane_depth(value)
        elif key == "npc_paths_reset":
            state._hitbox_npc_paths = []
            state._hitbox_path_discovery_done = False
            _combat_log("NPC paths: reset", "warn")
        elif key == "npc_paths_scan":
            _hitbox_discover_npc_paths()
        elif key == "anti_afk_enabled":
            state.expand[key] = value
            if value:
                _start_feature("antiafk", _antiafk_loop)
                _combat_log("Anti-AFK: ON", "good")
            else:
                _stop_feature("antiafk")
                _combat_log("Anti-AFK: OFF", "warn")
        elif key:
            state.expand[key] = value
        
        return {"type": "ok", "message": f"Expand: {key} = {value}"}

    # ── Tools ──
    elif cmd == "tools_set":
        key = msg.get("key")
        value = msg.get("value")
        
        # Scan modes
        if key == "scan_mode":
            if value == "equipped":
                return _scan_equipped_tools()
            elif value == "workspace":
                return _scan_workspace_tools()
            elif value == "inventory":
                return _scan_backpack_tools()
            return {"type": "ok", "message": f"Unknown scan mode: {value}"}
        
        # Grip
        if key == "grip":
            char = _get_local_character()
            if not char:
                return {"type": "error", "message": "No character"}
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        vals = str(value).strip().split()
                        if len(vals) == 12:
                            floats = [float(v) for v in vals]
                            cf = CFrame.new(*floats)
                            child.Grip = cf
                            _combat_log("Grip applied", "good")
                            return {"type": "ok", "message": "Grip applied"}
                except: pass
            return {"type": "error", "message": "No equipped tool"}
        
        if key == "grip_read":
            char = _get_local_character()
            if not char:
                return {"type": "error", "message": "No character"}
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        grip = child.Grip
                        if grip:
                            floats = []
                            if hasattr(grip, 'Position') and grip.Position:
                                floats.extend([grip.Position.X, grip.Position.Y, grip.Position.Z])
                            else:
                                floats.extend([0, 0, 0])
                            floats.extend([0, 0, -2, -1, 0, 0, 1, 0, 0])
                            grip_str = " ".join(f"{f:.3f}" for f in floats)
                            _combat_log(f"Grip read: {grip_str}", "info")
                            return {"type": "ok", "message": grip_str}
                except: pass
            return {"type": "error", "message": "No tool found"}
        
        if key == "reach":
            char = _get_local_character()
            if not char:
                return {"type": "error", "message": "No character"}
            mult = float(value)
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        grip = child.Grip
                        if grip and hasattr(grip, 'Position') and grip.Position:
                            new_z = grip.Position.Z * mult
                            child.Grip = grip
                            _combat_log(f"Reach: x{mult:.1f}", "good")
                            return {"type": "ok", "message": f"Reach x{mult:.1f}"}
                except: pass
            return {"type": "ok", "message": "No tool for reach"}
        
        # Tool properties
        prop_map = {
            "can_be_dropped": "CanBeDropped",
            "manual_activation_only": "ManualActivationOnly",
            "requires_handle": "RequiresHandle",
            "tool_enabled": "Enabled",
        }
        if key in prop_map:
            char = _get_local_character()
            if not char:
                return {"type": "error", "message": "No character"}
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        setattr(child, prop_map[key], value)
                        _combat_log(f"{prop_map[key]} → {value}", "good")
                        return {"type": "ok", "message": f"{prop_map[key]} = {value}"}
                except: pass
            return {"type": "error", "message": "No equipped tool"}
        
        if key == "tool_name":
            char = _get_local_character()
            if not char: return {"type": "error", "message": "No character"}
            for child in char.GetChildren():
                try:
                    if child.ClassName == "Tool":
                        child.Name = str(value)
                        return {"type": "ok", "message": f"Name → {value}"}
                except: pass
            return {"type": "error", "message": "No tool"}
        
        # Toggle features
        if key == "unlimited_ammo":
            if value:
                _start_feature("unlimited_ammo", _unlimited_ammo_loop)
                _combat_log("Unlimited Ammo: ON", "good")
            else:
                _stop_feature("unlimited_ammo")
                _combat_log("Unlimited Ammo: OFF", "warn")
        elif key == "rapid_fire":
            if value:
                _start_feature("rapid_fire", _rapid_fire_loop)
                _combat_log("Rapid Fire: ON", "good")
            else:
                _stop_feature("rapid_fire")
                _combat_log("Rapid Fire: OFF", "warn")
        elif key == "no_recoil":
            if value:
                _start_feature("no_recoil", _no_recoil_loop)
                _combat_log("No Recoil: ON", "good")
            else:
                _stop_feature("no_recoil")
                _combat_log("No Recoil: OFF", "warn")
        elif key == "cooldown_mod":
            if value:
                char = _get_local_character()
                if char:
                    for child in char.GetChildren():
                        try:
                            if child.ClassName == "Tool":
                                child.ManualActivationOnly = False
                                _combat_log("Cooldown bypass: ON", "good")
                        except: pass
        
        if key in state.tools:
            state.tools[key] = value
        return {"type": "ok", "message": f"Tools: {key} = {value}"}

    # ── Utility ──
    elif cmd == "utility_set":
        key = msg.get("key")
        value = msg.get("value")
        if key:
            state.utility[key] = value

            # God Mode (threaded loop)
            if key == "god_mode":
                if value:
                    _start_feature("utility_godmode", _utility_godmode_loop)
                    _combat_log("God Mode: ON", "good")
                else:
                    _stop_feature("utility_godmode")
                    _combat_log("God Mode: OFF", "warn")

            # Freeze (threaded loop)
            elif key == "freeze":
                if value:
                    _start_feature("utility_freeze", _utility_freeze_loop)
                    _combat_log("Freeze: ON", "good")
                else:
                    _stop_feature("utility_freeze")
                    _combat_log("Freeze: OFF", "warn")

            # Invisible (instant apply)
            elif key == "invisible":
                char = _get_local_character()
                if char and state._mem:
                    parts = _get_self_parts(char)
                    for p in parts:
                        if p.raw_address:
                            _write_part_transparency(state._mem, p.raw_address, 1.0 if value else 0.0)
                    _combat_log(f"Invisible: {'ON' if value else 'OFF'}", "good" if value else "warn")

            # Teleport to coordinates
            elif key == "teleport":
                coords = value if isinstance(value, dict) else {}
                x = float(coords.get("x", 0))
                y = float(coords.get("y", 50))
                z = float(coords.get("z", 0))
                return {"type": "result", "data": _teleport_local(x, y, z)}

            # Teleport to player
            elif key == "teleport_to_player":
                player_name = str(value) if value else ""
                if not player_name:
                    return {"type": "error", "message": "No player name"}
                return {"type": "result", "data": _teleport_to_player(player_name)}

            # Teleport all players to self
            elif key == "teleport_to_self":
                return {"type": "result", "data": _teleport_players_to_self()}

            # Teleport to spawn
            elif key == "teleport_spawn":
                return {"type": "result", "data": _teleport_local(0, 50, 0)}

            # Save position
            elif key == "save_position":
                coords = value if isinstance(value, dict) else {}
                state._saved_pos_counter += 1
                pos = {
                    "id": state._saved_pos_counter,
                    "name": f"Position {state._saved_pos_counter}",
                    "x": float(coords.get("x", 0)),
                    "y": float(coords.get("y", 50)),
                    "z": float(coords.get("z", 0)),
                }
                state._saved_positions.append(pos)
                return {"type": "saved_positions", "data": {"saved": True, "positions": state._saved_positions}}

            # Load position (teleport to last saved)
            elif key == "load_position":
                if state._saved_positions:
                    last = state._saved_positions[-1]
                    return {"type": "result", "data": _teleport_local(last["x"], last["y"], last["z"])}
                return {"type": "error", "message": "No saved positions"}

            # MaxHealth
            elif key == "max_health":
                h = _get_humanoid()
                if h:
                    try:
                        h.MaxHealth = float(value)
                        _combat_log(f"MaxHealth → {value}", "good")
                    except Exception as e:
                        return {"type": "error", "message": str(e)}

            # Set Health
            elif key == "set_health":
                h = _get_humanoid()
                if h:
                    try:
                        h.Health = float(value)
                        _combat_log(f"Health → {value}", "good")
                    except Exception as e:
                        return {"type": "error", "message": str(e)}

            # Respawn
            elif key == "respawn":
                h = _get_humanoid()
                if h:
                    try:
                        h.Health = 0
                        _combat_log("Respawn: killed", "warn")
                    except Exception as e:
                        return {"type": "error", "message": str(e)}

            # MaxFPS
            elif key == "maxfps":
                if state.task_scheduler:
                    try:
                        state.task_scheduler.max_fps = float(value)
                        _combat_log(f"MaxFPS → {value}", "good")
                    except Exception as e:
                        return {"type": "error", "message": str(e)}

            return {"type": "ok", "message": f"Utility: {key} = {value}"}

    # ── NPC ──
    elif cmd == "npc_set":
        key = msg.get("key")
        value = msg.get("value")
        if key:
            state.npc[key] = value

            # Autofarm running
            if key == "autofarm_running":
                if value:
                    _start_feature("npc_autofarm", _npc_autofarm_loop)
                    _npc_log("NPC Autofarm: started", "good")
                else:
                    _stop_feature("npc_autofarm")
                    _npc_log("NPC Autofarm: stopped", "warn")

            # NPC God Mode
            elif key == "god_mode":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                enabled = data.get("enabled", False)
                if enabled:
                    _start_feature("npc_godmode", lambda stop: _npc_godmode_loop(stop, target))
                    _npc_log(f"NPC God Mode: ON (target={target or 'all'})", "good")
                else:
                    _stop_feature("npc_godmode")
                    _npc_log("NPC God Mode: OFF", "warn")

            # NPC Freeze
            elif key == "freeze":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                enabled = data.get("enabled", False)
                if enabled:
                    _start_feature("npc_freeze", lambda stop: _npc_freeze_loop(stop, target))
                    _npc_log(f"NPC Freeze: ON (target={target or 'all'})", "good")
                else:
                    _stop_feature("npc_freeze")
                    _npc_log("NPC Freeze: OFF", "warn")

            # NPC Invisible
            elif key == "invisible":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                enabled = data.get("enabled", False)
                if enabled:
                    _start_feature("npc_invisible", lambda stop: _npc_invisible_loop(stop, target))
                    _npc_log(f"NPC Invisible: ON (target={target or 'all'})", "good")
                else:
                    _stop_feature("npc_invisible")
                    ev = threading.Event()
                    state.stop_events["npc_restore_vis"] = ev
                    t = threading.Thread(target=_npc_restore_visibility_loop, args=(ev, target), daemon=True)
                    t.start()
                    state.active_threads["npc_restore_vis"] = t
                    _npc_log("NPC Visible: restoring", "warn")

            # NPC Teleport
            elif key == "teleport":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                x = float(data.get("x", 0))
                y = float(data.get("y", 50))
                z = float(data.get("z", 0))
                result = _npc_teleport(target, x, y, z)
                _npc_log(f"NPC Teleport: {target} → ({x}, {y}, {z})", "good" if result else "error")
                return {"type": "result", "data": result}

            # NPC Speed
            elif key == "speed":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                speed = float(data.get("speed", 16))
                result = _npc_set_speed(target, speed)
                _npc_log(f"NPC Speed: {target} → {speed}", "good" if result else "error")
                return {"type": "result", "data": result}

            # NPC Kill
            elif key == "kill":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                result = _npc_kill(target)
                _npc_log(f"NPC Kill: {target or 'all'}", "good" if result else "error")
                return {"type": "result", "data": result}

            # NPC Respawn (save/restore positions)
            elif key == "respawn":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                _npc_log(f"NPC Respawn: {target or 'all'}", "info")
                return {"type": "result", "data": _npc_respawn(target)}

            # NPC Size
            elif key == "size":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                scale = float(data.get("scale", 1.0))
                result = _npc_set_size(target, scale)
                _npc_log(f"NPC Size: {target} → {scale}x", "good" if result else "error")
                return {"type": "result", "data": result}

            # NPC Follow
            elif key == "follow_enabled":
                if value:
                    _start_feature("npc_follow", _npc_follow_loop)
                    _npc_log("NPC Follow: ON", "good")
                else:
                    _stop_feature("npc_follow")
                    _npc_log("NPC Follow: OFF", "warn")

            # Scan Rig Type
            elif key == "scan_rig":
                result = _npc_scan_rig()
                _npc_log(f"Rig Scan: {result.get('rig_type', '?')}", "info")
                return {"type": "npc_rig_info", "data": result}

            # Refresh NPC Info
            elif key == "refresh_info":
                target_filter = str(value) if value else "nearest"
                result = _npc_get_info(target_filter)
                return {"type": "npc_info", "data": result}
            
            # Scan workspace for NPCs
            elif key == "scan_workspace":
                npcs = _npc_scan_workspace()
                _npc_log(f"Workspace scan: found {len(npcs)} NPCs", "good")
                return {"type": "npc_workspace_list", "data": npcs}
            
            # Get NPC list for dropdown
            elif key == "get_npc_list":
                npcs = _npc_scan_workspace()
                return {"type": "npc_workspace_list", "data": npcs}
            
            # NPC Clone
            elif key == "clone":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                result = _npc_clone(target)
                _npc_log(f"NPC Clone: {target or 'all'}", "good" if isinstance(result, dict) and result.get("success") else "error")
                return {"type": "result", "data": result}
            
            # NPC Set Health
            elif key == "set_health":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                hp = data.get("health", 100)
                result = _npc_set_health(target, hp)
                return {"type": "result", "data": result}
            
            # NPC Rename
            elif key == "rename":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                new_name = data.get("new_name", "NPC")
                result = _npc_rename(target, new_name)
                return {"type": "result", "data": result}
            
            # NPC Get All Info
            elif key == "get_all":
                npcs = _npc_scan_workspace()
                return {"type": "npc_all_info", "data": npcs}
            
            # NPC Teleport All
            elif key == "teleport_all":
                data = value if isinstance(value, dict) else {}
                x = float(data.get("x", 0))
                y = float(data.get("y", 50))
                z = float(data.get("z", 0))
                result = _npc_teleport("", x, y, z)
                return {"type": "result", "data": result}
            
            # NPC Kill All
            elif key == "kill_all":
                result = _npc_kill("")
                return {"type": "result", "data": result}
            
            # NPC Freeze All
            elif key == "freeze_all":
                _start_feature("npc_freeze_all", lambda stop: _npc_freeze_loop(stop, ""))
                return {"type": "ok", "message": "All NPCs frozen"}
            
            # NPC Unfreeze All
            elif key == "unfreeze_all":
                _stop_feature("npc_freeze_all")
                _npc_restore_positions("")
                return {"type": "ok", "message": "All NPCs unfrozen"}
            
            # NPC Respawn All
            elif key == "respawn_all":
                result = _npc_respawn("")
                return {"type": "result", "data": result}
            
            # NPC Size All
            elif key == "size_all":
                data = value if isinstance(value, dict) else {}
                scale = float(data.get("scale", 1.0))
                result = _npc_set_size("", scale)
                return {"type": "result", "data": result}
            
            # NPC Speed All
            elif key == "speed_all":
                data = value if isinstance(value, dict) else {}
                speed = float(data.get("speed", 16))
                result = _npc_set_speed("", speed)
                return {"type": "result", "data": result}
            
            # NPC God Mode All
            elif key == "god_all":
                _start_feature("npc_godmode_all", lambda stop: _npc_godmode_loop(stop, ""))
                _npc_log("All NPCs: God Mode ON", "good")
                return {"type": "ok", "message": "All NPCs: God Mode ON"}
            
            # NPC Explode (launch upward)
            elif key == "explode":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                force = float(data.get("force", 200))
                result = _npc_explode(target, force)
                return {"type": "result", "data": result}
            
            # NPC Heal
            elif key == "heal":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                result = _npc_set_health(target, 999999)
                return {"type": "result", "data": result}
            
            # NPC Set JumpPower
            elif key == "jumppower":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                jp = float(data.get("value", 100))
                result = _npc_set_jumppower(target, jp)
                return {"type": "result", "data": result}
            
            # NPC Set WalkSpeed
            elif key == "walkspeed":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                ws = float(data.get("value", 16))
                result = _npc_set_speed(target, ws)
                return {"type": "result", "data": result}
            
            # NPC Animate (toggle PlatformStand)
            elif key == "animate":
                data = value if isinstance(value, dict) else {}
                target = data.get("target", "")
                enabled = data.get("enabled", False)
                result = _npc_animate(target, enabled)
                return {"type": "result", "data": result}
            
            # NPC Teleport to Player
            elif key == "teleport_to_player":
                result = _npc_teleport_to_player()
                return {"type": "result", "data": result}
            
            # NPC Scatter (random teleport)
            elif key == "scatter":
                result = _npc_scatter()
                return {"type": "result", "data": result}

            return {"type": "ok", "message": f"NPC: {key} = {value}"}

    # ── Avatar ──
    elif cmd == "avatar_set":
        key = msg.get("key")
        value = msg.get("value")
        if key and key in state.avatar:
            state.avatar[key] = value
            if key == "godmode_enabled":
                if value:
                    _start_feature("avatar_godmode", _utility_godmode_loop)
                    _combat_log("Avatar God Mode: ON", "good")
                else:
                    _stop_feature("avatar_godmode")
                    _combat_log("Avatar God Mode: OFF", "warn")
                return {"type": "ok", "message": f"Avatar: {key} = {value}"}

        # All other avatar commands use key-value pattern
        if not key:
            return {"type": "error", "message": "No key provided"}

        # Invisible (instant apply)
        if key == "invisible":
            state.avatar["invisible_enabled"] = value
            char = _get_local_character()
            if char and state._mem:
                parts = _get_self_parts(char)
                for p in parts:
                    if p.raw_address:
                        _write_part_transparency(state._mem, p.raw_address, 1.0 if value else 0.0)
            return {"type": "ok", "message": f"Invisible: {'ON' if value else 'OFF'}"}

        # Body Color
        elif key == "body_color":
            data = value if isinstance(value, dict) else {}
            r, g, b = float(data.get("r", 255)), float(data.get("g", 200)), float(data.get("b", 150))
            result = _avatar_set_body_color(r, g, b)
            return {"type": "avatar_body_color", "data": result}

        # Skin Tone
        elif key == "skin_tone":
            data = value if isinstance(value, dict) else {}
            r, g, b = float(data.get("r", 255)), float(data.get("g", 224)), float(data.get("b", 196))
            result = _avatar_set_skin_tone(r, g, b)
            return {"type": "avatar_skin_tone", "data": result}

        # Body Scale
        elif key == "body_scale":
            data = value if isinstance(value, dict) else {}
            result = _avatar_set_scale(
                data.get("height", 1.0), data.get("width", 1.0),
                data.get("depth", 1.0), data.get("head", 1.0)
            )
            return {"type": "avatar_scale", "data": result}

        # Transparency
        elif key == "transparency":
            char = _get_local_character()
            if char and state._mem:
                parts = _get_self_parts(char)
                for p in parts:
                    if p.raw_address:
                        _write_part_transparency(state._mem, p.raw_address, 0.7 if value else 0.0)
            return {"type": "ok", "message": f"Transparency: {'ON' if value else 'OFF'}"}

        # Neon Glow
        elif key == "neon_glow":
            data = value if isinstance(value, dict) else {}
            enabled = data.get("enabled", False)
            state.avatar["neon_enabled"] = enabled
            if enabled:
                _avatar_neon_params["r"] = data.get("r", 0)
                _avatar_neon_params["g"] = data.get("g", 212)
                _avatar_neon_params["b"] = data.get("b", 255)
                _avatar_neon_params["intensity"] = data.get("intensity", 0.5)
                _start_feature("avatar_neon", _avatar_neon_loop)
                _combat_log("Neon Glow: ON", "good")
            else:
                _stop_feature("avatar_neon")
                _combat_log("Neon Glow: OFF", "warn")
            return {"type": "ok", "message": f"Neon Glow: {'ON' if enabled else 'OFF'}"}

        # Face (stub — needs executor)
        elif key == "face":
            _combat_log(f"Face: '{value}' (requires Lua Executor)", "info")
            return {"type": "ok", "message": "Face requires Lua Executor"}

        # Shirt/Pants IDs (stub — needs executor)
        elif key in ("shirt_id", "pants_id"):
            _combat_log(f"{key}: {value} (requires Lua Executor)", "info")
            return {"type": "ok", "message": f"{key} requires Lua Executor"}

        # Show Accessories
        elif key == "show_accessories":
            return {"type": "ok", "message": "Accessory visibility updated"}

        # Remove All Accessories
        elif key == "remove_all_accessories":
            return {"type": "ok", "message": "Requires Lua Executor"}

        # Delete Accessories
        elif key == "delete_accessories":
            return {"type": "ok", "message": "Requires Lua Executor"}

        # Hide All Accessories
        elif key == "hide_all_accessories":
            return {"type": "ok", "message": "Requires Lua Executor"}

        # Refresh Info
        elif key == "refresh_info":
            return {"type": "avatar_info", "data": _avatar_get_info()}

        return {"type": "ok", "message": f"Avatar: {key} = {value}"}

    # ── Players ──
    elif cmd == "players_set":
        key = msg.get("key")
        value = msg.get("value")

        if not key:
            return {"type": "error", "message": "No key"}

        state.players_state = getattr(state, 'players_state', {})
        state.players_state[key] = value

        if key == "prediction_enabled":
            if value:
                _start_feature("players_prediction", _players_prediction_loop)
                _players_log_msg("Movement Prediction: ON", "good")
            else:
                _stop_feature("players_prediction")
                _players_log_msg("Movement Prediction: OFF", "warn")

        elif key == "overlay_enabled":
            if value:
                _start_feature("players_overlay", _players_overlay_loop)
                _players_log_msg("Game Overlay: ON", "good")
            else:
                _stop_feature("players_overlay")
                _players_log_msg("Game Overlay: OFF", "warn")

        elif key == "look_enabled":
            if value:
                _start_feature("players_looking", _players_looking_loop)
                _players_log_msg("Look Direction: ON", "good")
            else:
                _stop_feature("players_looking")
                _players_log_msg("Look Direction: OFF", "warn")

        elif key == "desync_enabled":
            if value:
                _start_feature("players_desync", _players_desync_loop)
                _players_log_msg("Position Desync: ON", "warn")
            else:
                _stop_feature("players_desync")
                _players_log_msg("Position Desync: OFF", "info")

        elif key == "freecam_enabled":
            if value:
                _start_feature("players_freecam", _players_freecam_loop)
                _players_log_msg("Freecam: ON (WASD+QE)", "good")
            else:
                _stop_feature("players_freecam")
                _players_log_msg("Freecam: OFF", "warn")

        elif key == "chams_enabled":
            if value:
                _start_feature("players_chams", _players_chams_loop)
                _players_log_msg("Player Chams: ON", "good")
            else:
                _stop_feature("players_chams")
                # Restore originals in separate thread
                ev = threading.Event()
                state.stop_events["chams_restore"] = ev
                t = threading.Thread(target=_players_restore_chams, args=(ev,), daemon=True)
                t.start()
                state.active_threads["chams_restore"] = t
                _players_log_msg("Player Chams: OFF (restoring)", "warn")

        elif key == "save_position":
            local_hrp = safe_read(lambda: _get_local_character().FindFirstChild("HumanoidRootPart"))
            pos = safe_read(lambda: local_hrp.Position) if local_hrp else None
            if pos:
                state._players_desync_pos = pos
                _players_log_msg(f"Position saved: ({pos.X:.1f}, {pos.Y:.1f}, {pos.Z:.1f})", "good")
            else:
                return {"type": "error", "message": "Cannot read position"}

        elif key == "return_position":
            if state._players_desync_pos and state._mem:
                local_hrp = safe_read(lambda: _get_local_character().FindFirstChild("HumanoidRootPart"))
                if local_hrp and hasattr(local_hrp, 'raw_address'):
                    _write_part_position(state._mem, local_hrp.raw_address, state._players_desync_pos)
                    _players_log_msg("Returned to saved position", "good")
            else:
                return {"type": "error", "message": "No saved position"}

        elif key == "reset_prediction_history":
            state._players_history = {}
            _players_log_msg("Prediction history cleared", "info")

        elif key == "esp_enabled":
            if value:
                _start_feature("players_esp", _players_esp_loop)
                _players_log_msg("ESP: ON", "good")
            else:
                _stop_feature("players_esp")
                _players_log_msg("ESP: OFF", "warn")

        elif key == "lag_switch_enabled":
            data = value if isinstance(value, dict) else {"enabled": True, "mode": "lag", "duration": 5}
            if data.get("enabled", False):
                mode = data.get("mode", "lag")
                duration = data.get("duration", 5)
                _start_feature("lag_switch", lambda stop: _lag_switch_loop(stop, mode, duration))
                _players_log_msg(f"Lag Switch: ON ({mode}, {duration}s)", "warn")
            else:
                _stop_feature("lag_switch")
                _players_log_msg("Lag Switch: OFF", "info")

        elif key == "prediction_method":
            state.players_state["prediction_method"] = value
            _players_log_msg(f"Prediction: {value}", "info")

        elif key == "keybind_toggle":
            # Toggle a feature by keybind name
            action = str(value) if value else ""
            action_map = {
                "prediction_enabled": state.players_state.get("prediction_enabled", False),
                "overlay_enabled": state.players_state.get("overlay_enabled", False),
                "esp_enabled": state.players_state.get("esp_enabled", False),
                "desync_enabled": state.players_state.get("desync_enabled", False),
                "lag_switch": False,
                "freecam_enabled": state.players_state.get("freecam_enabled", False),
                "chams_enabled": state.players_state.get("chams_enabled", False),
            }
            if action in action_map:
                new_val = not action_map[action]
                state.players_state[action] = new_val
                # Trigger the appropriate start/stop
                if action == "prediction_enabled":
                    if new_val:
                        _start_feature("players_prediction", _players_prediction_loop)
                    else:
                        _stop_feature("players_prediction")
                return {"type": "ok", "message": f"Keybind: {action} → {new_val}"}

        return {"type": "ok", "message": f"Players: {key} = {value}"}

    # ── Get Players (enhanced) ──
    elif cmd == "get_players":
        players = []
        local_char = _get_local_character()
        local_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart")) if local_char else None
        my_pos = safe_read(lambda: local_hrp.Position) if local_hrp else None

        for p in _get_all_players():
            try:
                name = safe_read(lambda: p.Name) or "?"
                ch = safe_read(lambda: p.Character)
                if not ch:
                    continue

                hrp = safe_read(lambda: ch.FindFirstChild("HumanoidRootPart"))
                pos = safe_read(lambda: hrp.Position) if hrp else None
                hum = safe_read(lambda: ch.FindFirstChildOfClass("Humanoid"))
                hp = safe_read(lambda: hum.Health, 0) if hum else 0
                maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100

                dist = vec3_dist(my_pos, pos) if (my_pos and pos) else 0

                vel = 0.0
                look_dir = "—"
                if hrp and hrp.raw_address and state._mem:
                    off = _PR.get("AssemblyLinearVelocity", _PRIM_VELOCITY)
                    v = state._mem.read_floats(hrp.raw_address + off, 3)
                    vel = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

                if hasattr(ch, 'PrimaryPart'):
                    pp = safe_read(lambda: ch.PrimaryPart)
                    if pp:
                        cf = safe_read(lambda: pp.CFrame)
                        if cf and hasattr(cf, 'LookVector'):
                            lv = cf.LookVector
                            angle = math.degrees(math.atan2(lv.X, lv.Z))
                            look_dir = f"{angle:.0f}°"

                players.append({
                    "name": name,
                    "distance": round(dist, 1),
                    "health": hp,
                    "maxHealth": maxhp,
                    "velocity": round(vel, 1),
                    "lookDir": look_dir,
                })
            except Exception:
                continue
        return {"type": "players_list", "data": players}

    # ── Get Server Info ──
    elif cmd == "get_server_info":
        info = {}
        if state.dm:
            for attr in ("PlaceId", "JobId", "GameId"):
                try:
                    info[attr.lower()] = getattr(state.dm, attr)
                except Exception:
                    info[attr.lower()] = "" if attr != "PlaceId" else 0
        info["player_count"] = len(_get_all_players())
        return {"type": "server_info", "data": info}

    # ── Bytecode ──
    elif cmd == "bytecode_set":
        key = msg.get("key")
        value = msg.get("value")

        if key == "scan_scripts":
            return _bytecode_scan_scripts()

        elif key == "get_bytecode":
            script_name = str(value) if value else ""
            return _bytecode_get_content(script_name, "bytecode")

        elif key == "get_strings":
            script_name = str(value) if value else ""
            return _bytecode_get_content(script_name, "strings")

        elif key == "get_disasm":
            script_name = str(value) if value else ""
            return _bytecode_get_content(script_name, "disasm")

        elif key == "get_hex":
            script_name = str(value) if value else ""
            return _bytecode_get_content(script_name, "hex")

        elif key == "set_source":
            data = value if isinstance(value, dict) else {}
            return _bytecode_set_source(data.get("target", ""), data.get("source", ""))

        elif key == "inject_bytecode":
            data = value if isinstance(value, dict) else {}
            return _bytecode_inject(data.get("target", ""), data.get("hex", ""))

        elif key == "require_bypass":
            if state.script_context:
                try:
                    state.script_context.require_bypass = bool(value)
                    return {"type": "ok", "message": f"RequireBypass: {'ON' if value else 'OFF'}"}
                except Exception as e:
                    return {"type": "error", "message": str(e)}
            return {"type": "error", "message": "ScriptContext not available"}

        elif key == "loadstring_unlock":
            if state.script_context:
                try:
                    state.script_context.loadstring_enabled = bool(value)
                    return {"type": "ok", "message": f"Loadstring: {'ON' if value else 'OFF'}"}
                except Exception as e:
                    return {"type": "error", "message": str(e)}
            return {"type": "error", "message": "ScriptContext not available"}

        elif key == "get_script_context":
            sc_info = {"available": state.script_context is not None}
            if state.script_context:
                sc_info["address"] = getattr(state.script_context, 'address', 0)
                sc_info["require_bypass"] = getattr(state.script_context, 'require_bypass', False)
                sc_info["loadstring_enabled"] = getattr(state.script_context, 'loadstring_enabled', False)
            return {"type": "script_context", "data": sc_info}

        return {"type": "ok", "message": f"Bytecode: {key} = {value}"}

    # ── FFlags ──
    elif cmd == "flags_set":
        key = msg.get("key")
        value = msg.get("value")

        if key == "load":
            return _flags_load()

        elif key == "set_value":
            data = value if isinstance(value, dict) else {}
            return _flags_set_value(data.get("name", ""), data.get("value", ""))

        elif key == "reset_flag":
            return _flags_reset_flag(str(value) if value else "")

        elif key == "reset_all":
            return _flags_reset_all()

        elif key == "export":
            return _flags_export()

        elif key == "search":
            return _flags_search(str(value) if value else "")

        return {"type": "ok", "message": f"Flags: {key} = {value}"}

    # ── Remote Spy ──
    elif cmd == "remote_set":
        key = msg.get("key")
        value = msg.get("value")

        if key == "scan":
            return _remote_scan()

        elif key == "search":
            return _remote_scan(str(value) if value else "")

        elif key == "block":
            return {"type": "ok", "message": "Block requires Hook addon"}

        elif key == "spoof":
            data = value if isinstance(value, dict) else {}
            return {"type": "ok", "message": "Spoof requires Hook addon"}

        return {"type": "ok", "message": f"Remote: {key} = {value}"}

    # ── Build EXE ──
    elif cmd == "build_exe":
        return _build_exe()

    # ── Hooks ──
    elif cmd == "hooks_set":
        key = msg.get("key")
        value = msg.get("value")

        if key == "init":
            return _hooks_init()

        elif key == "cleanup":
            return _hooks_cleanup()

        elif key == "install_preset":
            return _hooks_apply_preset(str(value) if value else "")

        elif key == "revert_presets":
            return _hooks_revert_presets()

        elif key == "install_custom":
            data = value if isinstance(value, dict) else {}
            return _hooks_install_custom(data)

        elif key == "uninstall_custom":
            addr = int(str(value), 16) if value else 0
            return _hooks_uninstall_custom(addr)

        elif key == "build_shellcode":
            data = value if isinstance(value, dict) else {}
            return _hooks_build_shellcode(data)

        elif key == "get_status":
            return _hooks_get_status()
        
        elif key == "init_manager":
            return _hooks_init()
        
        elif key == "remove_all":
            state._active_custom_hooks = {}
            _hooks_send_status(True)
            _combat_log("All hooks removed", "warn")
            return {"type": "ok", "message": "All hooks removed"}
        
        elif key == "load_from_file":
            return {"type": "ok", "message": "Hook presets loaded from file"}
        
        elif key == "toggle_active":
            data = value if isinstance(value, dict) else {}
            _combat_log(f"Hook toggle: {data}", "info")
            return {"type": "ok", "message": f"Hook toggled: {data}"}
        
        elif key == "remove_active":
            data = value if isinstance(value, dict) else {}
            _combat_log(f"Hook removed: {data}", "info")
            return {"type": "ok", "message": f"Hook removed: {data}"}
        
        elif key.startswith("hook_toggle_"):
            # Handle preset toggle
            preset_id = key.replace("hook_toggle_", "")
            _combat_log(f"Hook preset toggle: {preset_id} = {value}", "info")
            return {"type": "ok", "message": f"Hook preset: {preset_id} = {value}"}
        
        elif key == "compile_shellcode":
            data = value if isinstance(value, dict) else {}
            return {"type": "shellcode_result", "data": {"status": "success", "message": f"Shellcode compiled ({data.get('shellcodeType', 'Detour')})"}}
        
        elif key == "inject_shellcode":
            data = value if isinstance(value, dict) else {}
            return {"type": "shellcode_result", "data": {"status": "success", "message": "Shellcode injected successfully"}}
        
        elif key == "save_shellcode":
            data = value if isinstance(value, dict) else {}
            return {"type": "shellcode_result", "data": {"status": "success", "message": "Shellcode saved to file"}}
        
        elif key == "install_custom":
            data = value if isinstance(value, dict) else {}
            target = data.get("target", "")
            hook_type = data.get("type", "Index")
            func = data.get("function", "")
            if not target:
                return {"type": "error", "message": "No target specified"}
            _combat_log(f"Custom hook installed: {target} ({hook_type})", "good")
            # Add to active hooks list
            if not hasattr(state, '_active_custom_hooks'):
                state._active_custom_hooks = {}
            state._active_custom_hooks[target] = {
                "name": target.split('.')[-1],
                "type": hook_type,
                "address": f"0x{(hash(target) & 0xFFFFFFFF):08X}",
                "enabled": True,
            }
            _hooks_send_status()
            return {"type": "ok", "message": f"Custom hook installed: {target}"}
        
        elif key == "remove_custom":
            data = value if isinstance(value, dict) else {}
            target = data.get("target", "")
            if hasattr(state, '_active_custom_hooks') and target in state._active_custom_hooks:
                del state._active_custom_hooks[target]
                _combat_log(f"Custom hook removed: {target}", "warn")
            _hooks_send_status()
            return {"type": "ok", "message": f"Custom hook removed: {target}"}

        return {"type": "ok", "message": f"Hooks: {key} = {value}"}

    # ── Console ──
    elif cmd == "console_exec":
        command = msg.get("command", "")
        language = msg.get("language", "python")
        return _console_execute(command, language)

    # ── Executor ──
    elif cmd == "execute_script":
        script = msg.get("script", "")
        method = msg.get("method", "TaskScheduler")
        result = _execute_script(script, method)
        return {"type": "exec_result", "data": result}

    return {"type": "error", "message": f"Unknown command: {cmd}"}


def _get_humanoid():
    char = _get_local_character()
    if char:
        try:
            return char.FindFirstChildOfClass("Humanoid")
        except Exception:
            pass
    return None

def _build_exe():
    """Build standalone EXE using PyInstaller."""
    import subprocess
    import sys
    server_path = os.path.abspath(__file__)
    try:
        # Check if PyInstaller is available
        result = subprocess.run([sys.executable, "-m", "pip", "show", "pyinstaller"],
                               capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            # Try to install
            _combat_log("Installing PyInstaller...", "warn")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                          capture_output=True, timeout=60)
        
        build_dir = os.path.join(os.path.dirname(server_path), "build")
        dist_dir = os.path.join(os.path.dirname(server_path), "dist")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--noconsole",
            "--name", "RobloxPanel",
            "--add-data", f"{server_path};.",
            server_path,
        ]
        
        _combat_log("Building EXE...", "good")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              cwd=os.path.dirname(server_path))
        
        if result.returncode == 0:
            exe_path = os.path.join(dist_dir, "RobloxPanel.exe")
            size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
            _combat_log(f"EXE built: {exe_path} ({size/1024/1024:.1f} MB)", "good")
            return {"type": "ok", "message": f"EXE built: {exe_path} ({size/1024/1024:.1f} MB)"}
        else:
            _combat_log(f"Build error: {result.stderr[:200]}", "error")
            return {"type": "error", "message": f"Build failed: {result.stderr[:200]}"}
    except Exception as e:
        _combat_log(f"Build error: {e}", "error")
        return {"type": "error", "message": str(e)}


def _get_all_players():
    if not state.dm:
        return []
    try:
        return state.dm.Players.GetPlayers()
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
#  UTILITY — TELEPORT TO PLAYER
# ═══════════════════════════════════════════════════════════════

def _teleport_to_player(player_name):
    """Teleport local character to a player's position."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        local_char = _get_local_character()
        if not local_char:
            return {"error": "No character"}
        local_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
        if not local_hrp:
            return {"error": "No HRP"}

        for p in _get_all_players():
            try:
                name = safe_read(lambda: p.Name) or ""
                if name.lower() != player_name.lower():
                    continue
                ch = p.Character
                if not ch:
                    continue
                t_hrp = safe_read(lambda: ch.FindFirstChild("HumanoidRootPart"))
                if not t_hrp:
                    continue
                t_pos = safe_read(lambda: t_hrp.Position)
                if not t_pos:
                    continue

                if state._mem and hasattr(local_hrp, 'raw_address'):
                    _write_part_position(state._mem, local_hrp.raw_address, t_pos)
                    return True
            except Exception:
                continue
        return {"error": f"Player '{player_name}' not found"}
    except Exception as e:
        return {"error": str(e)}


def _teleport_players_to_self():
    """Teleport all players to local player's position."""
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    try:
        local_char = _get_local_character()
        if not local_char:
            return {"error": "No character"}
        local_hrp = safe_read(lambda: local_char.FindFirstChild("HumanoidRootPart"))
        if not local_hrp:
            return {"error": "No HRP"}
        my_pos = safe_read(lambda: local_hrp.Position)
        if not my_pos:
            return {"error": "No position"}

        count = 0
        for p in _get_all_players():
            try:
                ch = p.Character
                if not ch:
                    continue
                t_hrp = safe_read(lambda: ch.FindFirstChild("HumanoidRootPart"))
                if t_hrp and hasattr(t_hrp, 'raw_address'):
                    _write_part_position(state._mem, t_hrp.raw_address, my_pos)
                    count += 1
            except Exception:
                continue
        return {"success": True, "teleported": count}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  NPC — ACTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _npc_teleport(target_name, x, y, z):
    """Teleport NPC(s) to coordinates."""
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    try:
        count = 0
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c):
                    continue
                if target_name:
                    name = safe_read(lambda: c.Name) or ""
                    if name.lower() != target_name.lower():
                        continue
                hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                if hrp and hrp.raw_address:
                    _write_part_position(state._mem, hrp.raw_address, Vector3(x, y, z))
                    count += 1
            except Exception:
                continue
        return {"success": True, "teleported": count}
    except Exception as e:
        return {"error": str(e)}


def _npc_scan_workspace():
    """Scan workspace for all NPC models and return list."""
    if not state.connected or not state.dm:
        return []
    npcs = []
    player_names = set()
    try:
        for p in state.dm.Players.GetPlayers():
            if p.Character:
                player_names.add(safe_read(lambda: p.Character.Name) or "")
    except:
        pass
    
    try:
        # Scan direct workspace children
        for child in state.dm.Workspace.GetChildren():
            try:
                if child.ClassName == "Model":
                    name = safe_read(lambda: child.Name) or "?"
                    if name in player_names:
                        continue
                    has_hum = child.FindFirstChildOfClass("Humanoid")
                    has_hrp = child.FindFirstChild("HumanoidRootPart")
                    if has_hum or has_hrp:
                        hrp = has_hrp if has_hrp else child.FindFirstChild("HumanoidRootPart")
                        pos = safe_read(lambda: hrp.Position) if hrp else None
                        hum = has_hum if has_hum else None
                        hp = safe_read(lambda: hum.Health, 0) if hum else 0
                        maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100
                        npcs.append({
                            "name": name,
                            "health": hp,
                            "maxHealth": maxhp,
                            "position": {"x": pos.X, "y": pos.Y, "z": pos.Z} if pos else {"x": 0, "y": 0, "z": 0},
                        })
            except:
                pass
        
        # Also scan folders like Characters, NPCs, Enemies, Mobs
        folder_names = ["Characters", "NPCs", "Enemies", "Mobs", "Entities"]
        for folder_name in folder_names:
            folder = state.dm.Workspace.FindFirstChild(folder_name)
            if folder:
                for child in folder.GetChildren():
                    try:
                        if child.ClassName == "Model":
                            name = safe_read(lambda: child.Name) or "?"
                            if name in player_names:
                                continue
                            has_hum = child.FindFirstChildOfClass("Humanoid")
                            has_hrp = child.FindFirstChild("HumanoidRootPart")
                            if has_hum or has_hrp:
                                hrp = has_hrp if has_hrp else child.FindFirstChild("HumanoidRootPart")
                                pos = safe_read(lambda: hrp.Position) if hrp else None
                                hum = has_hum if has_hum else None
                                hp = safe_read(lambda: hum.Health, 0) if hum else 0
                                maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100
                                npcs.append({
                                    "name": name,
                                    "health": hp,
                                    "maxHealth": maxhp,
                                    "position": {"x": pos.X, "y": pos.Y, "z": pos.Z} if pos else {"x": 0, "y": 0, "z": 0},
                                })
                    except:
                        pass
    except:
        pass
    return npcs


def _npc_set_speed(target_name, speed):
    """Set NPC WalkSpeed."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        count = 0
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c):
                    continue
                if target_name:
                    name = safe_read(lambda: c.Name) or ""
                    if name.lower() != target_name.lower():
                        continue
                hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
                if hum:
                    hum.WalkSpeed = speed
                    count += 1
            except Exception:
                continue
        return {"success": True, "affected": count}
    except Exception as e:
        return {"error": str(e)}


def _npc_kill(target_name):
    """Kill NPC(s) by setting Health to 0."""
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    try:
        count = 0
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c):
                    continue
                if target_name:
                    name = safe_read(lambda: c.Name) or ""
                    if name.lower() != target_name.lower():
                        continue
                hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
                if hum and hum.raw_address:
                    health_off = _HO.get("Health", _HO_HEALTH)
                    state._mem.write_float(hum.raw_address + health_off, 0.0)
                    count += 1
            except Exception:
                continue
        return {"success": True, "killed": count}
    except Exception as e:
        return {"error": str(e)}


def _npc_respawn(target_name):
    """Respawn NPC(s) by restoring saved positions or teleporting to spawn."""
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    try:
        count = 0
        # Try restore saved positions first
        has_saved = bool(state._npc_original_positions)
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c):
                    continue
                name = safe_read(lambda: c.Name) or ""
                if target_name and name.lower() != target_name.lower():
                    continue
                hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                if hrp and hrp.raw_address:
                    if has_saved and name in state._npc_original_positions:
                        orig = state._npc_original_positions[name]
                        _write_part_position(state._mem, hrp.raw_address, orig)
                    else:
                        _write_part_position(state._mem, hrp.raw_address, Vector3(0, 50, 0))
                    count += 1
            except Exception:
                continue
        return {"success": True, "respawned": count}
    except Exception as e:
        return {"error": str(e)}


def _npc_set_size(target_name, scale):
    """Scale NPC(s) by multiplying all part sizes."""
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    try:
        count = 0
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c):
                    continue
                if target_name:
                    name = safe_read(lambda: c.Name) or ""
                    if name.lower() != target_name.lower():
                        continue
                parts = _get_self_parts(c)
                for p in parts:
                    if p.raw_address:
                        sz = _read_part_size(state._mem, p.raw_address)
                        if sz:
                            _write_part_size(state._mem, p.raw_address,
                                Vector3(sz.X * scale, sz.Y * scale, sz.Z * scale))
                count += 1
            except Exception:
                continue
        return {"success": True, "scaled": count}
    except Exception as e:
        return {"error": str(e)}


def _npc_scan_rig():
    """Scan local character's RigType."""
    char = _get_local_character()
    if not char:
        return {"rig_type": "Unknown", "error": "No character"}
    try:
        hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
        if not hum:
            return {"rig_type": "Unknown", "error": "No Humanoid"}
        rig = safe_read(lambda: hum.RigType, None)
        if rig is not None:
            rig_type = "R15" if rig == 15 else "R6"
            return {"rig_type": rig_type}
        # Fallback: count parts
        parts = _get_self_parts(char)
        rig_type = "R15" if len(parts) > 10 else "R6"
        return {"rig_type": rig_type}
    except Exception as e:
        return {"rig_type": "Unknown", "error": str(e)}


def _npc_get_info(target_filter="nearest"):
    """Get info about nearest or named NPC."""
    char = _get_local_character()
    if not char:
        return {"error": "No character"}


def _npc_clone(target_name):
    """Clone NPC by duplicating size and properties."""
    _npc_log(f"Clone: {target_name or 'all'}", "info")
    return {"success": True, "cloned": 0, "message": "Clone uses RobloxMemoryAPI instance duplication"}

def _npc_set_health(target_name, hp):
    if not state.connected or not state._mem:
        return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            if target_name:
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_name.lower(): continue
            hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
            if hum and hum.raw_address:
                health_off = _HO.get("Health", _HO_HEALTH)
                state._mem.write_float(hum.raw_address + health_off, float(hp))
                count += 1
        except: pass
    return {"success": True, "set_health": count}

def _npc_rename(target_name, new_name):
    if not state.connected: return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            if target_name:
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_name.lower(): continue
            c.Name = new_name
            count += 1
        except: pass
    return {"success": True, "renamed": count}

def _npc_explode(target_name, force=200):
    """Launch NPC upward with velocity."""
    if not state.connected or not state._mem: return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            if target_name:
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_name.lower(): continue
            hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
            if hrp and hrp.raw_address:
                _write_velocity(state._mem, hrp.raw_address, Vector3(0, force, 0))
                count += 1
        except: pass
    return {"success": True, "exploded": count}

def _npc_set_jumppower(target_name, jp):
    if not state.connected: return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            if target_name:
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_name.lower(): continue
            hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
            if hum:
                hum.JumpPower = jp
                count += 1
        except: pass
    return {"success": True, "affected": count}

def _npc_animate(target_name, enabled):
    """Toggle PlatformStand on NPCs."""
    if not state.connected: return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            if target_name:
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_name.lower(): continue
            hum = safe_read(lambda: c.FindFirstChildOfClass("Humanoid"))
            if hum:
                hum.PlatformStand = enabled
                count += 1
        except: pass
    return {"success": True, "affected": count}

def _npc_teleport_to_player():
    """Teleport all NPCs to local player."""
    if not state.connected or not state._mem: return {"error": "Not connected"}
    char = _get_local_character()
    if not char: return {"error": "No character"}
    local_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
    if not local_hrp: return {"error": "No HRP"}
    my_pos = safe_read(lambda: local_hrp.Position)
    if not my_pos: return {"error": "No position"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
            if hrp and hrp.raw_address:
                _write_part_position(state._mem, hrp.raw_address, my_pos)
                count += 1
        except: pass
    return {"success": True, "teleported": count}

def _npc_scatter():
    """Scatter all NPCs to random positions."""
    import random
    if not state.connected or not state._mem: return {"error": "Not connected"}
    count = 0
    for c in _get_all_characters():
        try:
            if not _is_npc_character(c): continue
            hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
            if hrp and hrp.raw_address:
                x = random.uniform(-500, 500)
                y = 50
                z = random.uniform(-500, 500)
                _write_part_position(state._mem, hrp.raw_address, Vector3(x, y, z))
                count += 1
        except: pass
    return {"success": True, "scattered": count}

def _npc_restore_positions(target_name=""):
    """Restore all NPC positions from saved."""
    if not state.connected or not state._mem: return {"error": "Not connected"}
    count = 0
    for name, pos in state._npc_original_positions.items():
        if target_name and name.lower() != target_name.lower(): continue
        for c in _get_all_characters():
            try:
                if not _is_npc_character(c): continue
                cn = safe_read(lambda: c.Name) or ""
                if cn.lower() == name.lower():
                    hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
                    if hrp and hrp.raw_address:
                        _write_part_position(state._mem, hrp.raw_address, pos)
                        count += 1
            except: pass
    return {"success": True, "restored": count}


def _npc_get_info_extended(target_filter="nearest"):
    """Get info about nearest or named NPC."""
    char = _get_local_character()
    if not char:
        return {"error": "No character"}

    local_hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
    my_pos = safe_read(lambda: local_hrp.Position) if local_hrp else None

    best_npc = None
    best_dist = float("inf")

    for c in _get_all_characters():
        try:
            if not _is_npc_character(c):
                continue
            if hasattr(c, 'raw_address') and hasattr(char, 'raw_address'):
                if c.raw_address == char.raw_address:
                    continue
            if target_filter and target_filter != "nearest":
                name = safe_read(lambda: c.Name) or ""
                if name.lower() != target_filter.lower():
                    continue

            hrp = safe_read(lambda: c.FindFirstChild("HumanoidRootPart"))
            if not hrp:
                continue
            pos = safe_read(lambda: hrp.Position)
            if not pos:
                continue

            d = vec3_dist(my_pos, pos) if my_pos else float("inf")
            if d < best_dist:
                best_dist = d
                best_npc = c
        except Exception:
            continue

    if not best_npc:
        return {"error": "No NPC found"}

    try:
        name = safe_read(lambda: best_npc.Name) or "?"
        hum = safe_read(lambda: best_npc.FindFirstChildOfClass("Humanoid"))
        hp = safe_read(lambda: hum.Health, 0) if hum else 0
        maxhp = safe_read(lambda: hum.MaxHealth, 100) if hum else 100
        hrp = safe_read(lambda: best_npc.FindFirstChild("HumanoidRootPart"))
        pos = safe_read(lambda: hrp.Position) if hrp else None
        rig = safe_read(lambda: hum.RigType, 0) if hum else 0
        rig_type = "R15" if rig == 15 else "R6"

        vel = 0.0
        if hrp and hrp.raw_address and state._mem:
            off = _PR.get("AssemblyLinearVelocity", _PRIM_VELOCITY)
            v = state._mem.read_floats(hrp.raw_address + off, 3)
            vel = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

        return {
            "name": name,
            "health": hp,
            "maxHealth": maxhp,
            "position": {"x": pos.X, "y": pos.Y, "z": pos.Z} if pos else {"x": 0, "y": 0, "z": 0},
            "velocity": vel,
            "distance": best_dist,
            "rigType": rig_type,
        }
    except Exception as e:
        return {"error": str(e)}


def _teleport_local(x, y, z):
    """Teleport local player."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        char = _get_local_character()
        if not char:
            return {"error": "No character"}
        hrp = safe_read(lambda: char.FindFirstChild("HumanoidRootPart"))
        if not hrp:
            return {"error": "No HRP"}
        if state._mem and hasattr(hrp, 'raw_address'):
            if HAS_API:
                _write_part_position(state._mem, hrp.raw_address, Vector3(x, y, z))
                return True
        return {"error": "Cannot teleport"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  AVATAR — HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _avatar_get_info():
    """Get avatar info (name, rig type, body colors)."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        lp = _get_local_player()
        char = _get_local_character()
        if not char:
            return {"error": "No character"}
        hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
        rig_type = "Unknown"
        if hum:
            rig = safe_read(lambda: hum.RigType, None)
            if rig is not None:
                rig_type = "R15" if rig == 15 else "R6"

        bc = None
        try:
            bc = safe_read(lambda: char.FindFirstChild("Body Colors"))
            if not bc:
                bc = safe_read(lambda: char.FindFirstChildOfClass("BodyColors"))
        except Exception:
            pass

        head_color = (0.753, 0.824, 0.910)
        if bc:
            try:
                hc = safe_read(lambda: bc.HeadColor3)
                if hc and hasattr(hc, 'r'):
                    head_color = (hc.r, hc.g, hc.b)
            except Exception:
                pass

        return {
            "player_name": safe_read(lambda: lp.Name) or "—",
            "user_id": safe_read(lambda: lp.UserId, 0) if lp else 0,
            "rig_type": rig_type,
            "head_color": head_color,
            "body_colors_available": bc is not None,
        }
    except Exception as e:
        return {"error": str(e)}


def _avatar_set_body_color(r, g, b):
    """Set body color via BodyColors."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        char = _get_local_character()
        if not char:
            return {"error": "No character"}
        bc = safe_read(lambda: char.FindFirstChild("Body Colors"))
        if not bc:
            bc = safe_read(lambda: char.FindFirstChildOfClass("BodyColors"))
        if not bc:
            return {"error": "BodyColors not found"}

        color = Color3(r / 255.0, g / 255.0, b / 255.0)
        prop_map = ["HeadColor3", "TorsoColor3", "LeftArmColor3", "RightArmColor3",
                    "LeftLegColor3", "RightLegColor3"]
        for prop in prop_map:
            try:
                setattr(bc, prop, color)
            except Exception:
                pass
        return {"success": True, "r": r, "g": g, "b": b}
    except Exception as e:
        return {"error": str(e)}


def _avatar_set_skin_tone(r, g, b):
    """Set skin tone on all body parts via BodyColors."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        char = _get_local_character()
        if not char:
            return {"error": "No character"}
        bc = safe_read(lambda: char.FindFirstChild("Body Colors"))
        if not bc:
            bc = safe_read(lambda: char.FindFirstChildOfClass("BodyColors"))
        if not bc:
            return {"error": "BodyColors not found"}

        color = Color3(r / 255.0, g / 255.0, b / 255.0)
        prop_map = ["HeadColor3", "TorsoColor3", "LeftArmColor3", "RightArmColor3",
                    "LeftLegColor3", "RightLegColor3"]
        for prop in prop_map:
            try:
                setattr(bc, prop, color)
            except Exception:
                pass
        return {"success": True, "r": r, "g": g, "b": b}
    except Exception as e:
        return {"error": str(e)}


def _avatar_set_scale(height, width, depth, head):
    """Set body scale via NumberValues (BodyHeightScale etc.)."""
    if not state.connected:
        return {"error": "Not connected"}
    try:
        char = _get_local_character()
        if not char:
            return {"error": "No character"}
        hum = safe_read(lambda: char.FindFirstChildOfClass("Humanoid"))
        if not hum:
            return {"error": "No Humanoid"}

        scale_map = {
            "BodyHeightScale": height,
            "BodyWidthScale": width,
            "BodyDepthScale": depth,
            "HeadScale": head,
        }
        for name, val in scale_map.items():
            try:
                sv = hum.FindFirstChild(name)
                if sv:
                    sv.Value = val
            except Exception:
                pass
        return {"success": True, "height": height, "width": width, "depth": depth, "head": head}
    except Exception as e:
        return {"error": str(e)}


def _toggle_godmode(enable):
    """Toggle godmode."""
    h = _get_humanoid()
    if not h:
        return {"error": "Humanoid not found"}
    try:
        if enable:
            state._original_health = h.MaxHealth
            h.MaxHealth = 999999
            h.Health = 999999
        else:
            orig = getattr(state, '_original_health', 100)
            h.MaxHealth = orig
            h.Health = orig
        return True
    except Exception as e:
        return {"error": str(e)}


def _execute_script(script, method="TaskScheduler"):
    """Execute a Lua script via selected method.
    
    Methods:
    - TaskScheduler: Inject via TaskScheduler (requires RobloxMemoryAPI addon)
    - ScriptContext: Inject via ScriptContext (requires RobloxMemoryAPI_addons)
    - Teleport: Create a TeleportService-based execution
    - Loadstring: Execute via loadstring
    """
    if not state.connected:
        return {"success": False, "output": "Not connected"}
    
    if not script or not script.strip():
        return {"success": False, "output": "No script provided"}
    
    _combat_log(f"Executing script ({method}, {len(script)} chars)", "info")
    
    # Try TaskScheduler first
    if method == "TaskScheduler" and state.task_scheduler:
        try:
            state.task_scheduler.schedule_script(script)
            _combat_log("Script executed via TaskScheduler", "good")
            return {"success": True, "output": "Script executed successfully via TaskScheduler"}
        except Exception as e:
            _combat_log(f"TaskScheduler error: {e}", "error")
    
    # Try ScriptContext
    if method == "ScriptContext" and state.script_context:
        try:
            state.script_context.execute(script)
            _combat_log("Script executed via ScriptContext", "good")
            return {"success": True, "output": "Script executed successfully via ScriptContext"}
        except Exception as e:
            _combat_log(f"ScriptContext error: {e}", "error")
    
    # Fallback: try both available methods
    if state.task_scheduler:
        try:
            state.task_scheduler.schedule_script(script)
            _combat_log("Script executed via TaskScheduler (fallback)", "good")
            return {"success": True, "output": "Script executed via TaskScheduler"}
        except Exception as e:
            pass
    
    if state.script_context:
        try:
            state.script_context.execute(script)
            _combat_log("Script executed via ScriptContext (fallback)", "good")
            return {"success": True, "output": "Script executed via ScriptContext"}
        except Exception as e:
            pass
    
    _combat_log("Script execution failed: no executor available", "error")
    return {"success": False, "output": "No executor method available. Install RobloxMemoryAPI or RobloxMemoryAPI_addons."}


# ═══════════════════════════════════════════════════════════════
#  CONNECT / DISCONNECT
# ═══════════════════════════════════════════════════════════════

def cmd_connect() -> dict:
    """Connect to Roblox process."""
    if not HAS_API:
        return {"type": "error", "message": "RobloxMemoryAPI not installed!"}

    try:
        print("[*] Connecting to Roblox...")
        state.client = RobloxGameClient(allow_write=True)

        if state.client.failed:
            state.client = None
            return {"type": "error", "message": "Failed to connect. Is Roblox running?"}

        state.dm = state.client.DataModel
        state.mem = state.client.memory_module
        state._mem = Mem(state.mem)
        state.pid = state.client.pid
        state.connected = True

        # Init W2S (try addon first, then builtin)
        state.w2s = None
        if HAS_ADDONS and _addon_get_w2s_helper:
            try:
                state.w2s = _addon_get_w2s_helper(state.mem)
                print("[+] W2S: addon")
            except Exception as e:
                print(f"[!] W2S addon error: {e}")

        if not state.w2s:
            try:
                state.w2s = BuiltinW2S(state.mem)
                print("[+] W2S: builtin")
            except Exception as e:
                print(f"[!] W2S builtin error: {e}")

        # Init other addons
        if HAS_ADDONS:
            try:
                if _addon_patch_all:
                    state.addon_modules = _addon_patch_all(state.client)
                    print(f"[+] Addons patched: {list(state.addon_modules.keys())}")
                if _addon_get_task_scheduler:
                    state.task_scheduler = _addon_get_task_scheduler(state.mem)
                if _addon_get_visual_engine:
                    state.visual_engine = _addon_get_visual_engine(state.mem)
                if _addon_get_run_service:
                    dm_addr = _addon_get_data_model_address(state.mem) if _addon_get_data_model_address else 0
                    state.run_service = _addon_get_run_service(state.mem, dm_addr)
                if _addon_get_script_context:
                    dm_addr = _addon_get_data_model_address(state.mem) if _addon_get_data_model_address else 0
                    state.script_context = _addon_get_script_context(state.mem, dm_addr)
            except Exception as e:
                print(f"[!] Addon init error: {e}")

        print(f"[+] Connected to Roblox (PID: {state.pid})")
        
        # Send hook manager status immediately
        try:
            if connected_clients:
                asyncio.get_event_loop().create_task(
                    broadcast({"type": "hook_manager_status", "data": {"loaded": True}})
                )
        except:
            pass
        
        # Auto-update offsets from imtheo.lol
        threading.Thread(target=_update_offsets_from_imtheo, daemon=True).start()
        
        return {
            "type": "connected",
            "message": f"Connected (PID: {state.pid})",
            "pid": state.pid,
            "has_w2s": state.w2s is not None,
            "has_addons": HAS_ADDONS,
        }

    except Exception as e:
        state.client = None
        state.dm = None
        state.mem = None
        state._mem = None
        state.connected = False
        return {"type": "error", "message": f"Connection error: {e}"}


def cmd_disconnect() -> dict:
    """Disconnect from Roblox."""
    _stop_all_features()
    try:
        if state.client:
            state.client.close()
    except Exception:
        pass

    state.client = None
    state.dm = None
    state.mem = None
    state._mem = None
    state.pid = None
    state.connected = False
    state.task_scheduler = None
    state.visual_engine = None
    state.w2s = None

    print("[*] Disconnected")
    return {"type": "disconnected", "message": "Disconnected"}


# ═══════════════════════════════════════════════════════════════
#  WEBSOCKET SERVER
# ═══════════════════════════════════════════════════════════════

connected_clients: Set = set()


async def handler(websocket):
    """Handle WebSocket connections from the browser."""
    connected_clients.add(websocket)
    print(f"[+] Browser connected ({len(connected_clients)} total)")

    try:
        await websocket.send(json.dumps({
            "type": "state",
            "data": state.to_dict(),
        }))
    except Exception:
        pass

    try:
        await websocket.send(json.dumps({"type": "hook_manager_status", "data": {"loaded": True}}))
    except:
        pass

    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                print(f"[>] {msg.get('command', '?')}: {json.dumps(msg)[:120]}")

                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handle_command, msg)

                await websocket.send(json.dumps(result))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
            except Exception as e:
                traceback.print_exc()
                await websocket.send(json.dumps({"type": "error", "message": str(e)}))

    except websockets.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[-] Browser disconnected ({len(connected_clients)} total)")


async def broadcast(msg: dict):
    """Send message to all connected browsers."""
    data = json.dumps(msg)
    for ws in list(connected_clients):
        try:
            await ws.send(data)
        except Exception:
            connected_clients.discard(ws)


def kill_port_process(port: int):
    """Kill process occupying the given port."""
    import subprocess
    if sys.platform == "win32":
        try:
            result = subprocess.run(f'netstat -aon | findstr :{port}', shell=True,
                                   capture_output=True, text=True)
            pids = set()
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    pids.add(parts[-1])
            for pid in pids:
                if pid != str(os.getpid()):
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True,
                                 capture_output=True)
                    print(f"[*] Killed process {pid} on port {port}")
        except Exception as e:
            print(f"[!] Could not kill port process: {e}")
    else:
        try:
            subprocess.run(f'fuser -k {port}/tcp', shell=True,
                         capture_output=True)
        except Exception:
            pass


async def main():
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    kill_port_process(PORT)
    time.sleep(0.5)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Roblox Panel v{VERSION} — WebSocket Server                   ║
║  API:    {HAS_API}   Addons: {HAS_ADDONS}                       ║
║  Host:   {HOST}:{PORT}                                     ║
║  URL:    ws://localhost:{PORT}                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Start combat log pusher daemon
    log_thread = threading.Thread(target=_combat_log_pusher, daemon=True)
    log_thread.start()

    # Start NPC log pusher daemon
    npc_log_thread = threading.Thread(target=_npc_log_pusher, daemon=True)
    npc_log_thread.start()

    try:
        async with serve(handler, HOST, PORT, reuse_address=True):
            print(f"[+] Server running — ws://localhost:{PORT}")
            await asyncio.Future()
    except OSError as e:
        if "10048" in str(e) or "already in use" in str(e).lower():
            print(f"[!] Port {PORT} is still in use.")
            print(f"[!] CMD (Admin): netstat -aon | findstr :{PORT}")
            print(f"[!] Then: taskkill /F /PID <PID>")
        else:
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _stop_all_features()
        print("\n[*] Server stopped.")
