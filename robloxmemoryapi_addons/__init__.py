"""
RobloxMemoryAPI Addons — Полный набор дополнительных модулей

Дополнительные модули для RobloxMemoryAPI, покрывающие:
  - TaskScheduler (Job system, MaxFPS)
  - VisualEngine (ViewMatrix, W2S, Dimensions)
  - RunService (HeartbeatFPS)
  - Terrain (Water, MaterialColors, Atmosphere)
  - Sky (Skybox, Sun, Moon)
  - Post-Processing (Bloom, DepthOfField, SunRays)
  - DragDetector
  - ScriptContext
  - PlayerMouse
  - Enhanced properties for existing classes
  - Hook System (inline hooks, shellcode injection, presets)
  - Memory Script Executor (Lua без RequireBypass, RSB1, bytecode)

Использование:
    from robloxmemoryapi_addons import patch_all
    patch_all(client)  # автоматически расширит RBXInstance

Или индивидуально:
    from robloxmemoryapi_addons.task_scheduler import TaskScheduler
    from robloxmemoryapi_addons.hook_system import HookManager, Shellcode
    from robloxmemoryapi_addons.memory_executor import MemoryScriptExecutor, RSB1Encryptor

v1.2.0 — Добавлены:
  - Shellcode (x86-64 builder: JMP, CALL, RET, INT3, NOP, PUSH, MOV RCX/RDX, SUB/ADD RSP)
  - RSB1Encryptor (шифрование/дешифрование Roblox bytecode)
  - Полный экспорт всех классов из hook_system и memory_executor

v1.3.0 — Добавлены:
  - OffsetUpdater (автоматическое обновление оффсетов с imtheo.lol/Offsets)
  - OffsetUpdateWorker (фоновый поток для GUI)
  - Покрытие 15 файлов, ~170 оффсетных ключей
"""

__version__ = "1.4.0"
__all__ = [
    # patch.py helpers
    "patch_all",
    "get_visual_engine",
    "get_w2s_helper",
    "get_task_scheduler",
    "get_run_service",
    "get_script_context",
    "get_data_model_address",
    "wrap_terrain",
    "wrap_sky",
    "wrap_atmosphere",
    "wrap_bloom",
    "wrap_dof",
    "wrap_sunrays",
    "wrap_drag_detector",
    "wrap_player_mouse",
    # Core wrappers
    "TaskScheduler",
    "VisualEngine",
    "RenderView",
    "W2SHelper",
    "RunServiceWrapper",
    "TerrainWrapper",
    "MaterialColors",
    "AtmosphereWrapper",
    "SkyWrapper",
    "BloomEffectWrapper",
    "DepthOfFieldEffectWrapper",
    "SunRaysEffectWrapper",
    "DragDetectorWrapper",
    "ScriptContextWrapper",
    "PlayerMouseWrapper",
    # v1.1.0 — Hook System
    "HookManager",
    "HookLogger",
    "Shellcode",
    "build_jmp_abs",
    "build_call_abs",
    "build_ret",
    "build_int3",
    "build_nop_sled",
    "build_push",
    "build_mov_rcx",
    "build_mov_rdx",
    "build_sub_rsp",
    "build_add_rsp",
    "nop_function",
    "patch_byte",
    # v1.2.0 — Memory Executor
    "MemoryScriptExecutor",
    "BytecodeBuilder",
    "RSB1Encryptor",
    # v1.3.0 — Offset Updater
    "OffsetUpdater",
    # v1.4.0 — Game Overlay
    "GameOverlay",
]

# ── Импортируем хелперы из patch.py для прямого доступа ────────
from .patch import (
    get_visual_engine,
    get_w2s_helper,
    get_task_scheduler,
    get_run_service,
    get_script_context,
    get_data_model_address,
    wrap_terrain,
    wrap_sky,
    wrap_atmosphere,
    wrap_bloom,
    wrap_dof,
    wrap_sunrays,
    wrap_drag_detector,
    wrap_player_mouse,
)


def patch_all(client):
    """
    Патчит RBXInstance и добавляет все новые свойства/классы.
    Вызывать после создания RobloxGameClient.

    Returns:
        dict — все классы и обёртки для ручного использования

    Example:
        wrappers = patch_all(client)
        ts = wrappers["TaskScheduler"](client)
        hm = wrappers["HookManager"](client.memory_module)
        executor = wrappers["MemoryScriptExecutor"](client.memory_module)
    """
    from . import enhanced_instance
    enhanced_instance.patch_rbx_instance()

    from .task_scheduler import TaskScheduler
    from .visual_engine import VisualEngine, W2SHelper
    from .run_service import RunServiceWrapper
    from .terrain import TerrainWrapper, MaterialColors
    from .sky import SkyWrapper
    from .atmosphere import AtmosphereWrapper
    from .post_processing import (
        BloomEffectWrapper,
        DepthOfFieldEffectWrapper,
        SunRaysEffectWrapper,
    )
    from .drag_detector import DragDetectorWrapper
    from .script_context import ScriptContextWrapper
    from .player_mouse import PlayerMouseWrapper
    from .hook_system import HookManager, HookLogger, Shellcode
    from .memory_executor import MemoryScriptExecutor, BytecodeBuilder, RSB1Encryptor

    return {
        # Core wrappers
        "TaskScheduler": TaskScheduler,
        "VisualEngine": VisualEngine,
        "W2SHelper": W2SHelper,
        "RunService": RunServiceWrapper,
        "Terrain": TerrainWrapper,
        "MaterialColors": MaterialColors,
        "Sky": SkyWrapper,
        "Atmosphere": AtmosphereWrapper,
        "BloomEffect": BloomEffectWrapper,
        "DepthOfFieldEffect": DepthOfFieldEffectWrapper,
        "SunRaysEffect": SunRaysEffectWrapper,
        "DragDetector": DragDetectorWrapper,
        "ScriptContext": ScriptContextWrapper,
        "PlayerMouse": PlayerMouseWrapper,
        # Hook System
        "HookManager": HookManager,
        "HookLogger": HookLogger,
        "Shellcode": Shellcode,
        # Memory Executor
        "MemoryScriptExecutor": MemoryScriptExecutor,
        "BytecodeBuilder": BytecodeBuilder,
        "RSB1Encryptor": RSB1Encryptor,
        # Offset Updater
        "OffsetUpdater": None,  # загружается лениво через offset_updater
    }


# ── Ленивые импорты shellcode builder функций ─────────────────
def build_jmp_abs(addr: int) -> bytes:
    """Абсолютный JMP (14 байт): FF 25 00 00 00 00 [addr:8]"""
    from .hook_system import Shellcode
    return Shellcode.build_jmp_abs(addr)


def build_call_abs(addr: int) -> bytes:
    """Абсолютный CALL через trampoline (12 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_call_abs(addr)


def build_ret() -> bytes:
    """RET (1 байт)"""
    return b'\xC3'


def build_int3() -> bytes:
    """INT3 breakpoint (1 байт)"""
    return b'\xCC'


def build_nop_sled(count: int) -> bytes:
    """NOP sled — N штук NOP"""
    return b'\x90' * max(1, int(count))


def build_push(value: int) -> bytes:
    """PUSH imm32 (5 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_push(value)


def build_mov_rcx(value: int) -> bytes:
    """MOV RCX, imm64 (10 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_mov_rcx(value)


def build_mov_rdx(value: int) -> bytes:
    """MOV RDX, imm64 (10 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_mov_rdx(value)


def build_sub_rsp(value: int) -> bytes:
    """SUB RSP, imm (4-7 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_sub_rsp(value)


def build_add_rsp(value: int) -> bytes:
    """ADD RSP, imm (4-7 байт)"""
    from .hook_system import Shellcode
    return Shellcode.build_add_rsp(value)


def nop_function(hook_manager, addr: int, num_bytes: int = 14):
    """NOP-нуть функцию через HookManager"""
    return hook_manager.nop_function(addr, num_bytes)


def patch_byte(hook_manager, addr: int, new_byte: int, original_byte: int = None):
    """Патчить один байт через HookManager"""
    return hook_manager.patch_byte(addr, new_byte, original_byte)
