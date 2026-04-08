"""
Integration Patch — Единая точка интеграции с RobloxMemoryAPI

Позволяет одним вызовом подключить ВСЕ новые модули к DataModel
и RobloxGameClient.

Usage:
    from robloxmemoryapi import RobloxGameClient
    from robloxmemoryapi_addons import patch_all, get_visual_engine, get_task_scheduler

    client = RobloxGameClient()
    modules = patch_all(client)

    # Теперь можно использовать:
    ve = modules["VisualEngine"](client.memory_module)
    w2s = modules["W2SHelper"](ve)
    ts = modules["TaskScheduler"](client.memory_module)

    screen = w2s.world_to_screen(some_vector3)
    print(ts.max_fps)
    ts.max_fps = 999
"""

from .task_scheduler import TaskScheduler
from .visual_engine import VisualEngine, W2SHelper, RenderView
from .run_service import RunServiceWrapper
from .terrain import TerrainWrapper, MaterialColors, WorldWrapper
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
from .enhanced_instance import patch_rbx_instance


# ──────────────────────────────────────────────────────────────
# DataModel pointer chain
# ──────────────────────────────────────────────────────────────

FAKEDATAMODEL_POINTER = 0x834a988
FAKEDATAMODEL_TO_REAL = 0x1c0


def get_data_model_address(memory_module) -> int:
    """
    Получить адрес реального DataModel через FakeDataModel pointer chain.

    Args:
        memory_module: EvasiveProcess

    Returns:
        int: адрес DataModel, или 0
    """
    try:
        fake_dm_ptr = memory_module.base + FAKEDATAMODEL_POINTER
        fake_dm_addr = memory_module.get_pointer(fake_dm_ptr)
        if fake_dm_addr == 0:
            return 0
        real_dm_addr = memory_module.get_pointer(fake_dm_addr + FAKEDATAMODEL_TO_REAL)
        return real_dm_addr
    except Exception:
        return 0


def get_visual_engine(memory_module) -> VisualEngine:
    """Быстрое создание VisualEngine."""
    return VisualEngine(memory_module)


def get_task_scheduler(memory_module) -> TaskScheduler:
    """Быстрое создание TaskScheduler."""
    return TaskScheduler(memory_module)


def get_w2s_helper(memory_module) -> W2SHelper:
    """
    Быстрое создание W2SHelper.
    Автоматически создаёт VisualEngine внутри.
    """
    ve = VisualEngine(memory_module)
    return W2SHelper(ve)


def get_run_service(memory_module, data_model_address: int) -> RunServiceWrapper:
    """Быстрое создание RunService."""
    return RunServiceWrapper(memory_module, data_model_address)


def get_script_context(memory_module, data_model_address: int) -> ScriptContextWrapper:
    """Быстрое создание ScriptContext."""
    return ScriptContextWrapper(memory_module, data_model_address)


# ──────────────────────────────────────────────────────────────
# Helper wrappers для RBXInstance
# ──────────────────────────────────────────────────────────────

def wrap_terrain(instance) -> TerrainWrapper:
    """Обернуть RBXInstance (Terrain) в TerrainWrapper."""
    return TerrainWrapper(instance)


def wrap_sky(instance) -> SkyWrapper:
    """Обернуть RBXInstance (Sky) в SkyWrapper."""
    return SkyWrapper(instance)


def wrap_atmosphere(instance) -> AtmosphereWrapper:
    """Обернуть RBXInstance (Atmosphere) в AtmosphereWrapper."""
    return AtmosphereWrapper(instance)


def wrap_bloom(instance) -> BloomEffectWrapper:
    """Обернуть RBXInstance (BloomEffect) в BloomEffectWrapper."""
    return BloomEffectWrapper(instance)


def wrap_dof(instance) -> DepthOfFieldEffectWrapper:
    """Обернуть RBXInstance (DepthOfFieldEffect)."""
    return DepthOfFieldEffectWrapper(instance)


def wrap_sunrays(instance) -> SunRaysEffectWrapper:
    """Обернуть RBXInstance (SunRaysEffect)."""
    return SunRaysEffectWrapper(instance)


def wrap_drag_detector(instance) -> DragDetectorWrapper:
    """Обернуть RBXInstance (DragDetector)."""
    return DragDetectorWrapper(instance)


def wrap_player_mouse(player_instance) -> PlayerMouseWrapper:
    """Обернуть Player RBXInstance в PlayerMouseWrapper."""
    return PlayerMouseWrapper(player_instance)


# ──────────────────────────────────────────────────────────────
# Сводная таблица всех новых свойств
# ──────────────────────────────────────────────────────────────

NEW_PROPERTIES_SUMMARY = {
    "BasePart": [
        "CastShadow (bool, r/w)",
        "Shape (int, read-only)",
        "Material (int, r/w)",
    ],
    "Model": [
        "ModelScale (float, r/w)",
    ],
    "SpecialMesh": [
        "MeshScale (Vector3, r/w)",
        "MeshId (str, r/w)",
    ],
    "Decal/Texture": [
        "Texture (str, r/w)",
    ],
    "UnionOperation": [
        "AssetId (str, r/w)",
    ],
    "ProximityPrompt": [
        "KeyCode (int, read-only)",
        "GamepadKeyCode (int, read-only)",
    ],
    "Lighting": [
        "LightColor (Color3, r/w)",
        "GradientTop (Color3, r/w)",
        "GradientBottom (Color3, r/w)",
        "LightDirection (Vector3, read-only)",
    ],
    "SurfaceAppearance": [
        "ColorMap (str, read-only)",
        "EmissiveMaskContent (str, read-only)",
        "EmissiveTint (Color3, r/w)",
        "MetalnessMap (str, read-only)",
        "NormalMap (str, read-only)",
        "RoughnessMap (str, read-only)",
    ],
    "BloomEffect/DoF/SunRays/ColorCorrection/ColorGrading/Blur": [
        "PostEnabled (bool, r/w)",
    ],
}

NEW_MODULES_SUMMARY = {
    "TaskScheduler": "Job system, MaxFPS, перечисление задач",
    "VisualEngine": "ViewMatrix, Dimensions, RenderView",
    "W2SHelper": "World-to-Screen для ESP/aimbot",
    "RenderView": "LightingValid, SkyValid, DeviceD3D11",
    "RunServiceWrapper": "HeartbeatFPS, is_running",
    "TerrainWrapper": "Water, Grass, MaterialColors",
    "MaterialColors": "22 материала (Asphalt, Grass, Snow, ...)",
    "AtmosphereWrapper": "Density, Haze, Glare, Color, Decay",
    "SkyWrapper": "Skybox (6 граней), Sun, Moon, Stars",
    "BloomEffectWrapper": "Intensity, Size, Threshold, Enabled",
    "DepthOfFieldEffectWrapper": "FocusDistance, NearInt, FarInt, Radius",
    "SunRaysEffectWrapper": "Intensity, Spread, Enabled",
    "DragDetectorWrapper": "Force, Torque, Responsiveness, Drag",
    "ScriptContextWrapper": "RequireBypass",
    "PlayerMouseWrapper": "Icon, Workspace",
    "WorldWrapper": "PrimitiveCount",
}
