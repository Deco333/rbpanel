"""
Offset Auto-Updater — Автоматическое обновление оффсетов Roblox

Автоматизирует процесс обновления оффсетов во всех файлах проекта при выходе
новой версии Roblox. Источник истины: https://imtheo.lol/Offsets/Offsets.json

Функции:
  - Загрузка оффсетов с сервера (с обработкой HTML-обёртки)
  - Сравнение локальной и удалённой версии
  - Генерация плана обновлений (dry-run)
  - Применение обновлений к файлам
  - Создание резервных копий (.bak)
  - Откат к предыдущей версии
  - Сбор текущих оффсетов со всех файлов

Usage:
    from robloxmemoryapi_addons.offset_updater import OffsetUpdater

    updater = OffsetUpdater()

    # Проверить наличие обновлений
    info = updater.compare_versions()
    if info["is_update_available"]:
        plan = updater.get_update_plan()
        for change in plan:
            print(f"  {change['file']}: {change['var']} -> {change['new_value']}")

        # Применить (dry-run сначала)
        report = updater.apply_updates(dry_run=True)
        print(f"Would change {report['total_changes']} values in {report['files_affected']} files")

        # Реальное применение
        updater.backup_files()
        report = updater.apply_updates(dry_run=False)
"""

import json
import logging
import os
import re
import shutil
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

import urllib.request
import urllib.error

logger = logging.getLogger("offset_updater")


# ══════════════════════════════════════════════════════════════════════════════
# FILE_MAPPING — Полное соответствие JSON классов → Python файлам/переменным
# ══════════════════════════════════════════════════════════════════════════════
#
# Структура: {relative_path: [entry, ...]}
# Каждая entry — dict:
#   type="dict":  var — имя Python-словаря, source — JSON класс,
#                 keys — {json_key: python_dict_key, ...}
#   type="const": var — имя Python-константы, source — JSON класс,
#                 key — JSON ключ (для скалярных значений)

FILE_MAPPING: Dict[str, List[Dict[str, Any]]] = {
    # ── 1. task_scheduler.py ──────────────────────────────────────────────
    "robloxmemoryapi_addons/task_scheduler.py": [
        {
            "var": "TASK_SCHEDULER_OFFSETS",
            "type": "dict",
            "source": "TaskScheduler",
            "keys": {
                "Pointer": "Pointer",
                "JobStart": "JobStart",
                "JobEnd": "JobEnd",
                "JobName": "JobName",
                "MaxFPS": "MaxFPS",
            },
        },
    ],

    # ── 2. visual_engine.py ───────────────────────────────────────────────
    "robloxmemoryapi_addons/visual_engine.py": [
        {
            "var": "VISUAL_ENGINE_OFFSETS",
            "type": "dict",
            "source": "VisualEngine",
            "keys": {
                "Pointer": "Pointer",
                "Dimensions": "Dimensions",
                "ViewMatrix": "ViewMatrix",
                "RenderView": "RenderView",
                "FakeDataModel": "FakeDataModel",
            },
        },
        {
            "var": "RENDER_VIEW_OFFSETS",
            "type": "dict",
            "source": "RenderView",
            "keys": {
                "LightingValid": "LightingValid",
                "SkyValid": "SkyValid",
                "VisualEngine": "VisualEngine",
                "DeviceD3D11": "DeviceD3D11",
            },
        },
    ],

    # ── 3. terrain.py ─────────────────────────────────────────────────────
    "robloxmemoryapi_addons/terrain.py": [
        {
            "var": "TERRAIN_OFFSETS",
            "type": "dict",
            "source": "Terrain",
            "keys": {
                "GrassLength": "GrassLength",
                "WaterReflectance": "WaterReflectance",
                "WaterTransparency": "WaterTransparency",
                "WaterWaveSize": "WaterWaveSize",
                "WaterWaveSpeed": "WaterWaveSpeed",
                "WaterColor": "WaterColor",
                "MaterialColors": "MaterialColors",
            },
        },
        {
            "var": "MATERIAL_COLORS_OFFSETS",
            "type": "dict",
            "source": "MaterialColors",
            "keys": {
                "Asphalt": "Asphalt", "Basalt": "Basalt", "Brick": "Brick",
                "Cobblestone": "Cobblestone", "Concrete": "Concrete",
                "CrackedLava": "CrackedLava", "Glacier": "Glacier",
                "Grass": "Grass", "Ground": "Ground", "Ice": "Ice",
                "LeafyGrass": "LeafyGrass", "Limestone": "Limestone",
                "Mud": "Mud", "Pavement": "Pavement", "Rock": "Rock",
                "Salt": "Salt", "Sand": "Sand", "Sandstone": "Sandstone",
                "Slate": "Slate", "Snow": "Snow", "WoodPlanks": "WoodPlanks",
            },
        },
        {
            "var": "WORLD_OFFSETS",
            "type": "dict",
            "source": "World",
            "keys": {
                "Gravity": "Gravity",
                "worldStepsPerSec": "worldStepsPerSec",
                "FallenPartsDestroyHeight": "FallenPartsDestroyHeight",
                "AirProperties": "AirProperties",
                "Primitives": "Primitives",
            },
        },
    ],

    # ── 4. sky.py ─────────────────────────────────────────────────────────
    "robloxmemoryapi_addons/sky.py": [
        {
            "var": "SKY_OFFSETS",
            "type": "dict",
            "source": "Sky",
            "keys": {
                "SkyboxBk": "SkyboxBk", "SkyboxDn": "SkyboxDn",
                "SkyboxFt": "SkyboxFt", "SkyboxLf": "SkyboxLf",
                "SkyboxRt": "SkyboxRt", "SkyboxUp": "SkyboxUp",
                "SunAngularSize": "SunAngularSize",
                "MoonAngularSize": "MoonAngularSize",
                "SunTextureId": "SunTextureId", "MoonTextureId": "MoonTextureId",
                "SkyboxOrientation": "SkyboxOrientation", "StarCount": "StarCount",
            },
        },
    ],

    # ── 5. atmosphere.py ──────────────────────────────────────────────────
    "robloxmemoryapi_addons/atmosphere.py": [
        {
            "var": "ATMOSPHERE_OFFSETS",
            "type": "dict",
            "source": "Atmosphere",
            "keys": {
                "Density": "Density", "Offset": "Offset", "Color": "Color",
                "Decay": "Decay", "Glare": "Glare", "Haze": "Haze",
            },
        },
    ],

    # ── 6. post_processing.py ─────────────────────────────────────────────
    "robloxmemoryapi_addons/post_processing.py": [
        {
            "var": "BLOOM_OFFSETS",
            "type": "dict",
            "source": "BloomEffect",
            "keys": {
                "Intensity": "Intensity", "Size": "Size",
                "Threshold": "Threshold", "Enabled": "Enabled",
            },
        },
        {
            "var": "DOF_OFFSETS",
            "type": "dict",
            "source": "DepthOfFieldEffect",
            "keys": {
                "FocusDistance": "FocusDistance", "FarIntensity": "FarIntensity",
                "NearIntensity": "NearIntensity", "InFocusRadius": "InFocusRadius",
                "Enabled": "Enabled",
            },
        },
        {
            "var": "SUNRAYS_OFFSETS",
            "type": "dict",
            "source": "SunRaysEffect",
            "keys": {
                "Intensity": "Intensity", "Spread": "Spread", "Enabled": "Enabled",
            },
        },
    ],

    # ── 7. drag_detector.py ───────────────────────────────────────────────
    "robloxmemoryapi_addons/drag_detector.py": [
        {
            "var": "DRAG_DETECTOR_OFFSETS",
            "type": "dict",
            "source": "DragDetector",
            "keys": {
                "ReferenceInstance": "ReferenceInstance",
                "MaxActivationDistance": "MaxActivationDistance",
                "MaxDragAngle": "MaxDragAngle",
                "MaxDragTranslation": "MaxDragTranslation",
                "MinDragAngle": "MinDragAngle",
                "MinDragTranslation": "MinDragTranslation",
                "ActivatedCursorIcon": "ActivatedCursorIcon",
                "CursorIcon": "CursorIcon",
                "MaxForce": "MaxForce", "MaxTorque": "MaxTorque",
                "Responsiveness": "Responsiveness",
            },
        },
    ],

    # ── 8. script_context.py ──────────────────────────────────────────────
    "robloxmemoryapi_addons/script_context.py": [
        {
            "var": "SCRIPT_CONTEXT_OFFSETS",
            "type": "dict",
            "source": None,  # Multi-source — assembled from different JSON classes
            "multi_source": {
                "ScriptContext": "RequireBypass",
                "DataModel": "ScriptContext",
            },
            "keys": {
                "ScriptContext": "ScriptContext",   # → DataModel.ScriptContext
                "RequireBypass": "RequireBypass",   # → ScriptContext.RequireBypass
            },
        },
    ],

    # ── 9. player_mouse.py ───────────────────────────────────────────────
    "robloxmemoryapi_addons/player_mouse.py": [
        {
            "var": "PLAYER_MOUSE_OFFSETS",
            "type": "dict",
            "source": None,
            "multi_source": {
                "Player": "Mouse",
                "PlayerMouse": None,  # remaining keys
            },
            "keys": {
                "Mouse": "Mouse",        # → Player.Mouse
                "Workspace": "Workspace",  # → PlayerMouse.Workspace
                "Icon": "Icon",          # → PlayerMouse.Icon
            },
        },
    ],

    # ── 10. run_service.py ────────────────────────────────────────────────
    "robloxmemoryapi_addons/run_service.py": [
        {
            "var": "RUN_SERVICE_OFFSETS",
            "type": "dict",
            "source": "RunService",
            "keys": {
                "HeartbeatTask": "HeartbeatTask", "HeartbeatFPS": "HeartbeatFPS",
            },
        },
    ],

    # ── 11. patch.py ──────────────────────────────────────────────────────
    "robloxmemoryapi_addons/patch.py": [
        {
            "var": "FAKEDATAMODEL_POINTER",
            "type": "const",
            "source": "FakeDataModel",
            "key": "Pointer",
        },
        {
            "var": "FAKEDATAMODEL_TO_REAL",
            "type": "const",
            "source": "FakeDataModel",
            "key": "RealDataModel",
        },
    ],

    # ── 12. hook_system.py ───────────────────────────────────────────────
    "robloxmemoryapi_addons/hook_system.py": [
        {"var": "FAKEDATAMODEL_POINTER", "type": "const", "source": "FakeDataModel", "key": "Pointer"},
        {"var": "FAKEDATAMODEL_TO_REAL", "type": "const", "source": "FakeDataModel", "key": "RealDataModel"},
        {"var": "SCRIPT_CONTEXT_OFFSET", "type": "const", "source": "DataModel", "key": "ScriptContext"},
        {"var": "REQUIRE_BYPASS_OFFSET", "type": "const", "source": "ScriptContext", "key": "RequireBypass"},
        {"var": "TASK_SCHEDULER_POINTER", "type": "const", "source": "TaskScheduler", "key": "Pointer"},
        {"var": "TASK_SCHEDULER_MAX_FPS", "type": "const", "source": "TaskScheduler", "key": "MaxFPS"},
        {"var": "WORKSPACE_OFFSET", "type": "const", "source": "DataModel", "key": "Workspace"},
        {"var": "WORLD_OFFSET", "type": "const", "source": "Workspace", "key": "World"},
        {"var": "WORLD_GRAVITY", "type": "const", "source": "World", "key": "Gravity"},
    ],

    # ── 13. memory_executor.py ────────────────────────────────────────────
    "robloxmemoryapi_addons/memory_executor.py": [
        {"var": "FAKEDATAMODEL_POINTER", "type": "const", "source": "FakeDataModel", "key": "Pointer"},
        {"var": "FAKEDATAMODEL_TO_REAL", "type": "const", "source": "FakeDataModel", "key": "RealDataModel"},
        {"var": "INSTANCE_NAME", "type": "const", "source": "Instance", "key": "Name"},
        {"var": "INSTANCE_CLASS_DESCRIPTOR", "type": "const", "source": "Instance", "key": "ClassDescriptor"},
        {"var": "INSTANCE_CLASS_NAME", "type": "const", "source": "Instance", "key": "ClassName"},
        {"var": "INSTANCE_CHILDREN_START", "type": "const", "source": "Instance", "key": "ChildrenStart"},
        {"var": "INSTANCE_CHILDREN_END", "type": "const", "source": "Instance", "key": "ChildrenEnd"},
        {"var": "INSTANCE_CHILDREN_STRIDE", "type": "const", "source": None, "key": None},
        {"var": "INSTANCE_PARENT", "type": "const", "source": "Instance", "key": "Parent"},
        {"var": "LOCALSCRIPT_BYTECODE", "type": "const", "source": "LocalScript", "key": "ByteCode"},
        {"var": "MODULESCRIPT_BYTECODE", "type": "const", "source": "ModuleScript", "key": "ByteCode"},
        {"var": "SCRIPT_BYTECODE", "type": "const", "source": "Script", "key": "ByteCode"},
        {"var": "BYTECODE_POINTER", "type": "const", "source": "ByteCode", "key": "Pointer"},
        {"var": "BYTECODE_SIZE", "type": "const", "source": "ByteCode", "key": "Size"},
        {"var": "SCRIPT_CONTEXT_OFFSET", "type": "const", "source": "DataModel", "key": "ScriptContext"},
        {"var": "REQUIRE_BYPASS_OFFSET", "type": "const", "source": "ScriptContext", "key": "RequireBypass"},
        {"var": "TASK_SCHEDULER_POINTER", "type": "const", "source": "TaskScheduler", "key": "Pointer"},
    ],

    # ── 14. enhanced_instance.py ──────────────────────────────────────────
    "robloxmemoryapi_addons/enhanced_instance.py": [
        {
            "var": "BASE_PART_EXTRA", "type": "dict", "source": "BasePart",
            "keys": {"CastShadow": "CastShadow", "Shape": "Shape"},
        },
        {
            "var": "PRIMITIVE_EXTRA", "type": "dict", "source": "Primitive",
            "keys": {"Material": "Material"},
        },
        {
            "var": "MODEL_EXTRA", "type": "dict", "source": "Model",
            "keys": {"Scale": "Scale"},
        },
        {
            "var": "SPECIAL_MESH", "type": "dict", "source": "SpecialMesh",
            "keys": {"Scale": "Scale", "MeshId": "MeshId"},
        },
        {
            "var": "ATTACHMENT_EXTRA", "type": "dict", "source": "Attachment",
            "keys": {"Position": "Position"},
        },
        {
            "var": "TEXTURES", "type": "dict", "source": "Textures",
            "keys": {"Texture": "Decal_Texture"},
        },
        {
            "var": "UNION_OPERATION", "type": "dict", "source": "UnionOperation",
            "keys": {"AssetId": "AssetId"},
        },
        {
            "var": "PROXIMITY_PROMPT_EXTRA", "type": "dict", "source": "ProximityPrompt",
            "keys": {"KeyCode": "KeyCode", "GamepadKeyCode": "GamepadKeyCode"},
        },
        {
            "var": "LIGHTING_EXTRA", "type": "dict", "source": "Lighting",
            "keys": {
                "LightColor": "LightColor", "GradientTop": "GradientTop",
                "LightDirection": "LightDirection", "GradientBottom": "GradientBottom",
            },
        },
        {
            "var": "SURFACE_APPEARANCE_EXTRA", "type": "dict", "source": "SurfaceAppearance",
            "keys": {
                "ColorMap": "ColorMap", "EmissiveMaskContent": "EmissiveMaskContent",
                "EmissiveTint": "EmissiveTint", "MetalnessMap": "MetalnessMap",
                "NormalMap": "NormalMap", "RoughnessMap": "RoughnessMap",
            },
        },
        {
            "var": "POST_PROCESS_ENABLED", "type": "const", "source": "BloomEffect",
            "key": "Enabled",
        },
    ],

    # ── 15. panel_new_v2.py ──────────────────────────────────────────────
    "roblox_panel/panel_new_v2.py": [
        # Primitive fallbacks
        {"var": "_PRIM_POSITION", "type": "const", "source": "Primitive", "key": "Position"},
        {"var": "_PRIM_SIZE", "type": "const", "source": "Primitive", "key": "Size"},
        {"var": "_PRIM_VELOCITY", "type": "const", "source": "Primitive", "key": "AssemblyLinearVelocity"},
        {"var": "_PRIM_ANGULAR_VEL", "type": "const", "source": "Primitive", "key": "AssemblyAngularVelocity"},
        {"var": "_PRIM_FLAGS", "type": "const", "source": "Primitive", "key": "Flags"},
        {"var": "_BP_TRANSPARENCY", "type": "const", "source": "BasePart", "key": "Transparency"},
        {"var": "_BP_COLOR3", "type": "const", "source": "BasePart", "key": "Color3"},
        # Humanoid fallbacks
        {"var": "_HO_WALKSPEED", "type": "const", "source": "Humanoid", "key": "Walkspeed"},
        {"var": "_HO_HEALTH", "type": "const", "source": "Humanoid", "key": "Health"},
        {"var": "_HO_MAXHEALTH", "type": "const", "source": "Humanoid", "key": "MaxHealth"},
        {"var": "_HO_JUMPPower", "type": "const", "source": "Humanoid", "key": "JumpPower"},
        {"var": "_HO_PLATFORMSTAND", "type": "const", "source": "Humanoid", "key": "PlatformStand"},
        {"var": "_HO_HIPHEIGHT", "type": "const", "source": "Humanoid", "key": "HipHeight"},
        {"var": "_HO_USEJUMPPOWER", "type": "const", "source": "Humanoid", "key": "UseJumpPower"},
        # Bytecode fallbacks
        {"var": "_LS_BC_OFF", "type": "const", "source": "LocalScript", "key": "ByteCode"},
        {"var": "_MS_BC_OFF", "type": "const", "source": "ModuleScript", "key": "ByteCode"},
        {"var": "_S_BC_OFF", "type": "const", "source": "Script", "key": "ByteCode"},
        {"var": "_BC_PTR_OFF", "type": "const", "source": "ByteCode", "key": "Pointer"},
        {"var": "_BC_SIZE_OFF", "type": "const", "source": "ByteCode", "key": "Size"},
        # Visual Engine fallbacks
        {"var": "_VISUAL_ENGINE_PTR", "type": "const", "source": "VisualEngine", "key": "Pointer"},
        {"var": "_VISUAL_ENGINE_DIMS", "type": "const", "source": "VisualEngine", "key": "Dimensions"},
        {"var": "_VISUAL_ENGINE_VM", "type": "const", "source": "VisualEngine", "key": "ViewMatrix"},
        # Primitive flags (maps to bit values, not offsets — include but note)
        {"var": "_FLAG_CANCOLLIDE", "type": "const", "source": "PrimitiveFlags", "key": "CanCollide"},
        {"var": "_FLAG_ANCHORED", "type": "const", "source": "PrimitiveFlags", "key": "Anchored"},
    ],
}


class OffsetUpdater:
    """
    Автоматический обновлятор оффсетов Roblox.

    Загружает оффсеты с imtheo.lol, сравнивает с локальными,
    и обновляет все Python файлы проекта.

    Attributes:
        base_dir: Корневая директория проекта (откуда разрешаются
                  относительные пути из FILE_MAPPING).
        remote_data: Последние загруженные данные с сервера.
        local_data: Последние загруженные локальные данные.
    """

    OFFSETS_SOURCE_URL: str = "https://imtheo.lol/Offsets/Offsets.json"
    FFLAGS_SOURCE_URL: str = "https://imtheo.lol/Offsets/FFlags.json"

    def __init__(self, base_dir: Optional[str] = None):
        """
        Args:
            base_dir: Корневая директория проекта. По умолчанию —
                      на два уровня выше расположения этого модуля.
        """
        if base_dir is None:
            # Модуль в robloxmemoryapi_addons/, проект на уровне download/
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = os.path.abspath(base_dir)

        self.remote_data: Optional[Dict] = None
        self.local_data: Optional[Dict] = None
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def remote_version(self) -> Optional[str]:
        """Версия Roblox из удалённых данных."""
        if self.remote_data:
            return self.remote_data.get("Roblox Version")
        return None

    @property
    def local_version(self) -> Optional[str]:
        """Версия Roblox из локальных данных."""
        if self.local_data:
            return self.local_data.get("Roblox Version")
        return None

    @property
    def remote_offsets(self) -> Dict:
        """Словарь оффсетов из удалённых данных."""
        if self.remote_data:
            return self.remote_data.get("Offsets", {})
        return {}

    @property
    def local_offsets(self) -> Dict:
        """Словарь оффсетов из локальных данных."""
        if self.local_data:
            return self.local_data.get("Offsets", {})
        return {}

    # ── Data Loading ─────────────────────────────────────────────────────

    def _resolve_abs_path(self, relative_path: str) -> str:
        """Преобразует относительный путь в абсолютный относительно base_dir."""
        return os.path.normpath(os.path.join(self.base_dir, relative_path))

    @staticmethod
    def _extract_json_from_html(text: str) -> str:
        """
        Извлекает JSON из HTML-обёрнутого ответа.

        imtheo.lol возвращает JSON внутри <pre> тегов:
            <html>...<pre>{...json...}</pre>...</html>

        Также обрабатывает случай когда API возвращает JSON с полем data.html.
        """
        # Случай 1: JSON обёрнут в <pre> теги
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL)
        if pre_match:
            json_str = pre_match.group(1).strip()
            # HTML entity decode
            json_str = json_str.replace("&lt;", "<").replace("&gt;", ">")
            json_str = json_str.replace("&amp;", "&").replace("&quot;", '"')
            try:
                parsed = json.loads(json_str)
                if "Offsets" in parsed:
                    return json.dumps(parsed)
            except json.JSONDecodeError:
                pass

        # Случай 2: Ответ API с полем data.html (web-reader формат)
        try:
            outer = json.loads(text)
            if isinstance(outer, dict):
                # data.html field
                html_content = outer.get("data", {}).get("html", "") if isinstance(outer.get("data"), dict) else ""
                if html_content:
                    return OffsetUpdater._extract_json_from_html(html_content)
                # Может быть уже чистый JSON
                if "Offsets" in outer:
                    return json.dumps(outer)
        except (json.JSONDecodeError, AttributeError):
            pass

        # Случай 3: Чистый JSON без обёртки
        try:
            parsed = json.loads(text)
            if "Offsets" in parsed:
                return json.dumps(parsed)
        except json.JSONDecodeError:
            pass

        raise ValueError("Не удалось извлечь JSON из ответа сервера")

    def fetch_live_offsets(self, timeout: float = 15.0) -> Dict:
        """
        Загружает оффсеты с сервера imtheo.lol.

        Args:
            timeout: Таймаут HTTP запроса в секундах.

        Returns:
            Распарсенный словарь с оффсетами.

        Raises:
            ConnectionError: При ошибке сети.
            ValueError: При ошибке парсинга JSON.
        """
        logger.info("Загрузка оффсетов с %s", self.OFFSETS_SOURCE_URL)

        text = None

        # Метод 1: requests (если установлен)
        if HAS_REQUESTS:
            try:
                resp = _requests.get(
                    self.OFFSETS_SOURCE_URL,
                    timeout=timeout,
                    headers={"User-Agent": "OffsetUpdater/1.0"},
                )
                resp.raise_for_status()
                text = resp.text
            except Exception as e:
                logger.warning("requests не удалось: %s, пробуем urllib", e)

        # Метод 2: urllib (stdlib fallback)
        if text is None:
            try:
                req = urllib.request.Request(
                    self.OFFSETS_SOURCE_URL,
                    headers={"User-Agent": "OffsetUpdater/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                raise ConnectionError(
                    f"Не удалось загрузить оффсеты: {e}"
                ) from e

        if not text:
            raise ValueError("Пустой ответ от сервера")

        # Извлекаем JSON из возможной HTML обёртки
        json_str = self._extract_json_from_html(text)
        data = json.loads(json_str)

        if "Offsets" not in data:
            raise ValueError("JSON не содержит поле 'Offsets'")

        with self._lock:
            self.remote_data = data

        logger.info(
            "Оффсеты загружены: версия=%s, всего=%s",
            data.get("Roblox Version", "?"),
            data.get("Total Offsets", "?"),
        )
        return data

    def load_local_offsets(self, path: Optional[str] = None) -> Dict:
        """
        Загружает локальный JSON файл с оффсетами.

        Args:
            path: Путь к JSON файлу. По умолчанию — offsets_new.json
                  в base_dir.

        Returns:
            Распарсенный словарь с оффсетами.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: При ошибке парсинга.
        """
        if path is None:
            path = self._resolve_abs_path("offsets_new.json")
        else:
            path = os.path.abspath(path)

        logger.info("Загрузка локальных оффсетов из %s", path)

        if not os.path.isfile(path):
            raise FileNotFoundError(f"Файл не найден: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "Offsets" not in data:
            raise ValueError("Локальный JSON не содержит поле 'Offsets'")

        with self._lock:
            self.local_data = data

        logger.info(
            "Локальные оффсеты: версия=%s",
            data.get("Roblox Version", "?"),
        )
        return data

    # ── Version Comparison ───────────────────────────────────────────────

    def compare_versions(self) -> Dict:
        """
        Сравнивает локальную и удалённую версии Roblox.

        Returns:
            {
                "is_update_available": bool,
                "local_version": str | None,
                "remote_version": str | None,
                "changed_classes": [str, ...],
                "total_changed_keys": int,
            }

        Note:
            Требует предварительной загрузки через fetch_live_offsets()
            и/или load_local_offsets().
        """
        lv = self.local_version
        rv = self.remote_version

        result = {
            "is_update_available": False,
            "local_version": lv,
            "remote_version": rv,
            "changed_classes": [],
            "total_changed_keys": 0,
        }

        if not rv:
            logger.warning("Нет удалённых данных для сравнения")
            return result

        if lv == rv:
            logger.info("Версии совпадают: %s", lv)
            return result

        if lv is None:
            # Нет локальных данных — всё считается изменённым
            result["is_update_available"] = True
            result["changed_classes"] = list(self.remote_offsets.keys())
            result["total_changed_keys"] = len(self.remote_offsets)
            return result

        # Сравниваем по ключам в каждом классе
        local_offs = self.local_offsets
        remote_offs = self.remote_offsets

        for class_name, remote_keys in remote_offs.items():
            local_keys = local_offs.get(class_name, {})
            for key, new_val in remote_keys.items():
                if local_keys.get(key) != new_val:
                    if class_name not in result["changed_classes"]:
                        result["changed_classes"].append(class_name)
                    result["total_changed_keys"] += 1

        result["is_update_available"] = result["total_changed_keys"] > 0

        logger.info(
            "Сравнение: local=%s remote=%s changed=%s classes=%s",
            lv, rv, result["total_changed_keys"],
            len(result["changed_classes"]),
        )
        return result

    # ── Value Resolution ─────────────────────────────────────────────────

    def _resolve_dict_values(self, entry: Dict, offsets: Dict) -> Dict[str, int]:
        """
        Получает словарь новых значений для dict-type записи.

        Обрабатывает как single-source так и multi-source записи.

        Args:
            entry: Описание переменной из FILE_MAPPING.
            offsets: Словарь оффсетов (remote или local).

        Returns:
            Словарь {python_key: new_value, ...}.
        """
        keys = entry.get("keys", {})
        source = entry.get("source")
        result: Dict[str, int] = {}

        # Multi-source: ключи берутся из разных JSON классов
        if entry.get("multi_source"):
            multi = entry["multi_source"]
            for py_key, json_key in keys.items():
                for src_cls, src_key in multi.items():
                    if src_key is not None and src_key == json_key:
                        val = offsets.get(src_cls, {}).get(json_key)
                        if val is not None:
                            result[py_key] = val
                        break
                    elif src_key is None:
                        # remaining keys — ищем в этом классе
                        val = offsets.get(src_cls, {}).get(json_key)
                        if val is not None:
                            result[py_key] = val
                        break
        elif source:
            # Single source: все ключи из одного JSON класса
            src_data = offsets.get(source, {})
            for py_key, json_key in keys.items():
                val = src_data.get(json_key)
                if val is not None:
                    result[py_key] = val

        return result

    def _resolve_const_value(self, entry: Dict, offsets: Dict) -> Optional[int]:
        """
        Получает значение оффсета для const-type записи.

        Args:
            entry: Описание переменной из FILE_MAPPING.
            offsets: Словарь оффсетов (remote или local).

        Returns:
            Числовое значение оффсета, или None если не найдено.
        """
        source = entry.get("source")
        key = entry.get("key")
        if source is None or key is None:
            return None
        return offsets.get(source, {}).get(key)

    # ── Hex Formatting ───────────────────────────────────────────────────

    @staticmethod
    def _to_hex(value: int) -> str:
        """
        Форматирует число как hex строку: 0x + uppercase hex digits.

        Examples:
            >>> _to_hex(200)
            '0xC8'
            >>> _to_hex(0)
            '0x0'
        """
        return f"0x{value:X}"

    @staticmethod
    def _parse_hex_or_int(text: str) -> Optional[int]:
        """Парсит hex (0x...) или десятичное число из строки."""
        text = text.strip()
        if not text:
            return None
        try:
            if text.startswith("0x") or text.startswith("0X"):
                return int(text, 16)
            return int(text)
        except ValueError:
            return None

    # ── Update Plan ──────────────────────────────────────────────────────

    def get_update_plan(self) -> List[Dict]:
        """
        Генерирует план обновлений.

        Returns:
            Список изменений:
            [{
                "file": str,           # Относительный путь
                "var": str,            # Имя переменной
                "key": str | None,     # Ключ в словаре (None для констант)
                "old_value": int | None,  # Текущее значение (None если не найдено)
                "new_value": int,      # Новое значение из JSON
                "source": str,         # JSON класс
                "line": int | None,    # Номер строки (если найдена)
            }, ...]
        """
        if not self.remote_offsets:
            logger.warning("Нет удалённых данных — вызовите fetch_live_offsets()")
            return []

        plan: List[Dict] = []

        for rel_path, entries in FILE_MAPPING.items():
            abs_path = self._resolve_abs_path(rel_path)

            if not os.path.isfile(abs_path):
                logger.debug("Файл не найден: %s", abs_path)
                continue

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    source = f.read()
            except Exception as e:
                logger.warning("Не удалось прочитать %s: %s", abs_path, e)
                continue

            for entry in entries:
                entry_type = entry.get("type")

                if entry_type == "dict":
                    new_vals = self._resolve_dict_values(entry, self.remote_offsets)
                    if not new_vals:
                        continue
                    for py_key, val in new_vals.items():
                        plan.append({
                            "file": rel_path,
                            "var": entry["var"],
                            "key": py_key,
                            "old_value": self._find_current_dict_value(
                                source, entry["var"], py_key
                            ),
                            "new_value": val,
                            "source": entry.get("source", "?"),
                            "line": self._find_line_number(
                                source, entry["var"], py_key
                            ),
                        })

                elif entry_type == "const":
                    new_val = self._resolve_const_value(entry, self.remote_offsets)
                    if new_val is None:
                        continue
                    current = self._find_current_const_value(source, entry["var"])
                    plan.append({
                        "file": rel_path,
                        "var": entry["var"],
                        "key": None,
                        "old_value": current,
                        "new_value": new_val,
                        "source": entry.get("source", "?"),
                        "line": self._find_line_number(source, entry["var"]),
                    })

        return plan

    # ── Current Value Detection ──────────────────────────────────────────

    @staticmethod
    def _find_current_dict_value(source: str, var_name: str, dict_key: str) -> Optional[int]:
        """Находит текущее значение ключа в Python-словаре."""
        # Ищем: "Key": 0xABC или "Key": 123
        pattern = re.compile(
            rf'"{re.escape(dict_key)}"\s*:\s*(0x[0-9a-fA-F]+|\d+)',
            re.MULTILINE,
        )
        match = pattern.search(source)
        if match:
            val_str = match.group(1)
            try:
                if val_str.startswith("0x") or val_str.startswith("0X"):
                    return int(val_str, 16)
                return int(val_str)
            except ValueError:
                pass
        return None

    @staticmethod
    def _find_current_const_value(source: str, var_name: str) -> Optional[int]:
        """Находит текущее значение константы."""
        # Ищем: VARNAME = 0xABC или VARNAME = 123
        pattern = re.compile(
            rf'^{re.escape(var_name)}\s*=\s*(0x[0-9a-fA-F]+|\d+)',
            re.MULTILINE,
        )
        match = pattern.search(source)
        if match:
            val_str = match.group(1)
            try:
                if val_str.startswith("0x") or val_str.startswith("0X"):
                    return int(val_str, 16)
                return int(val_str)
            except ValueError:
                pass
        return None

    @staticmethod
    def _find_line_number(source: str, var_name: str, dict_key: Optional[str] = None) -> Optional[int]:
        """Находит номер строки, где определена переменная/ключ."""
        lines = source.splitlines()
        if dict_key:
            # Для ключей словаря — ищем по точному совпадению "Key":
            target = f'"{dict_key}"'
            for i, line in enumerate(lines, 1):
                if target in line and ":" in line:
                    return i
            return None
        else:
            # Для констант — ищем VARNAME =
            for i, line in enumerate(lines, 1):
                if re.match(rf'^{re.escape(var_name)}\s*=', line):
                    return i
            return None

    # ── Apply Updates ────────────────────────────────────────────────────

    def apply_updates(self, dry_run: bool = False) -> Dict:
        """
        Основная функция применения обновлений.

        Для каждого файла из FILE_MAPPING:
          1. Читает Python исходник
          2. Находит оффсет-константы/словари через regex
          3. Заменяет старые значения новыми из remote JSON
          4. Обновляет комментарий версии
          5. Записывает файл обратно

        Args:
            dry_run: Если True — только возвращает план, не пишет файлы.

        Returns:
            {
                "success": bool,
                "total_changes": int,
                "files_affected": int,
                "changes": [{...}, ...],
                "errors": [str, ...],
            }
        """
        if not self.remote_offsets:
            return {
                "success": False,
                "total_changes": 0,
                "files_affected": 0,
                "changes": [],
                "errors": ["Нет удалённых данных — вызовите fetch_live_offsets()"],
            }

        plan = self.get_update_plan()
        if not plan:
            return {
                "success": True,
                "total_changes": 0,
                "files_affected": 0,
                "changes": [],
                "errors": [],
            }

        # Группируем изменения по файлам
        files_changes: Dict[str, List[Dict]] = {}
        for change in plan:
            files_changes.setdefault(change["file"], []).append(change)

        report: Dict = {
            "success": True,
            "total_changes": len(plan),
            "files_affected": len(files_changes),
            "changes": [],
            "errors": [],
        }

        for rel_path, changes in files_changes.items():
            abs_path = self._resolve_abs_path(rel_path)

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    source = f.read()
            except Exception as e:
                msg = f"Не удалось прочитать {rel_path}: {e}"
                logger.error(msg)
                report["errors"].append(msg)
                report["success"] = False
                continue

            new_source = source
            file_changed = False

            for change in changes:
                old_val = change["old_value"]
                new_val = change["new_value"]

                # Пропускаем если значения совпадают
                if old_val is not None and old_val == new_val:
                    continue

                new_hex = self._to_hex(new_val)

                if change["key"] is not None:
                    # Dict-style: "Key": old_hex → "Key": new_hex
                    pattern = re.compile(
                        rf'("{re.escape(change["key"])}"\s*:\s*)'
                        rf'(?:0x[0-9a-fA-F]+|\d+)',
                    )
                    replacement = rf'\g<1>{new_hex}'
                    new_source, count = pattern.subn(replacement, new_source)
                    if count > 0:
                        file_changed = True
                        change["applied"] = True
                        change["applied_hex"] = new_hex
                    else:
                        change["applied"] = False
                        msg = f"Не найдено: {rel_path}::{change['var']}['{change['key']}']"
                        logger.warning(msg)
                        report["errors"].append(msg)
                else:
                    # Const-style: VARNAME = old_hex → VARNAME = new_hex
                    pattern = re.compile(
                        rf'(^{re.escape(change["var"])}\s*=\s*)'
                        rf'(?:0x[0-9a-fA-F]+|\d+)',
                        re.MULTILINE,
                    )
                    replacement = rf'\g<1>{new_hex}'
                    new_source, count = pattern.subn(replacement, new_source)
                    if count > 0:
                        file_changed = True
                        change["applied"] = True
                        change["applied_hex"] = new_hex
                    else:
                        change["applied"] = False
                        msg = f"Не найдено: {rel_path}::{change['var']}"
                        logger.warning(msg)
                        report["errors"].append(msg)

                report["changes"].append(change)

            # Обновляем комментарий версии в файле
            if file_changed and self.remote_version and not dry_run:
                new_source = self._update_version_comment(new_source)

            # Записываем файл
            if file_changed and not dry_run:
                try:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_source)
                    logger.info("Обновлён: %s (%s изменений)", rel_path, len(changes))
                except Exception as e:
                    msg = f"Не удалось записать {rel_path}: {e}"
                    logger.error(msg)
                    report["errors"].append(msg)
                    report["success"] = False

        return report

    def _update_version_comment(self, source: str) -> str:
        """
        Обновляет строку комментария с версией в файле.

        Ищет: # Updated: ... version-... (imtheo.lol)
        Заменяет на текущую версию.
        """
        if not self.remote_version:
            return source

        now = datetime.now().strftime("%m/%d/%Y")
        new_comment = f"# Updated: {now} — {self.remote_version} (imtheo.lol)"

        # Заменяем существующий комментарий
        pattern = re.compile(
            r"^#\s*Updated:.*\(imtheo\.lol\)",
            re.MULTILINE,
        )
        new_source, count = pattern.subn(new_comment, source)

        if count == 0:
            # Нет существующего комментария — не добавляем (предотвращаем мусор)
            pass

        return new_source

    # ── Patch Generation ─────────────────────────────────────────────────

    def generate_patches(self) -> List[Tuple[str, str, str, str]]:
        """
        Генерирует список патчей для UI отображения.

        Returns:
            Список кортежей: (file_path, old_line_text, new_line_text, var_name)
        """
        plan = self.get_update_plan()
        patches: List[Tuple[str, str, str, str]] = []

        for change in plan:
            if change["old_value"] is None:
                old_hex = "<???>"
            else:
                old_hex = self._to_hex(change["old_value"])
            new_hex = self._to_hex(change["new_value"])

            if old_hex == new_hex:
                continue

            if change["key"]:
                var_label = f'{change["var"]}["{change["key"]}"]'
            else:
                var_label = change["var"]

            old_line = f'{var_label} = {old_hex}'
            new_line = f'{var_label} = {new_hex}'

            patches.append((
                change["file"],
                old_line,
                new_line,
                var_label,
            ))

        return patches

    # ── Backup / Rollback ────────────────────────────────────────────────

    def backup_files(self) -> List[str]:
        """
        Создаёт .bak копии всех файлов из FILE_MAPPING.

        Returns:
            Список путей к созданным .bak файлам.
        """
        backed_up: List[str] = []

        for rel_path in FILE_MAPPING:
            abs_path = self._resolve_abs_path(rel_path)
            bak_path = abs_path + ".bak"

            if os.path.isfile(abs_path):
                try:
                    shutil.copy2(abs_path, bak_path)
                    backed_up.append(bak_path)
                    logger.info("Резервная копия: %s", bak_path)
                except Exception as e:
                    logger.warning("Не удалось создать резервную копию %s: %s", abs_path, e)

        return backed_up

    def rollback(self) -> Dict:
        """
        Восстанавливает файлы из .bak копий.

        Returns:
            {
                "restored": int,
                "failed": int,
                "details": [(file, status), ...],
            }
        """
        result = {"restored": 0, "failed": 0, "details": []}

        for rel_path in FILE_MAPPING:
            abs_path = self._resolve_abs_path(rel_path)
            bak_path = abs_path + ".bak"

            if os.path.isfile(bak_path):
                try:
                    shutil.copy2(bak_path, abs_path)
                    os.remove(bak_path)
                    result["restored"] += 1
                    result["details"].append((rel_path, "restored"))
                    logger.info("Восстановлен: %s", rel_path)
                except Exception as e:
                    result["failed"] += 1
                    result["details"].append((rel_path, f"failed: {e}"))
                    logger.error("Не удалось восстановить %s: %s", rel_path, e)
            else:
                result["details"].append((rel_path, "no backup"))

        return result

    # ── Scan Current Offsets ─────────────────────────────────────────────

    def get_all_current_offsets(self) -> Dict[str, Tuple[int, str, int]]:
        """
        Сканирует все файлы проекта и собирает текущие оффсеты.

        Returns:
            Словарь: {"ClassName.Key": (value, source_file, line_number)}

            Где ClassName.Key — составной идентификатор:
              - Для dict-переменных: "VAR_NAME.Key"
              - Для констант: "VAR_NAME"
        """
        result: Dict[str, Tuple[int, str, int]] = {}

        for rel_path, entries in FILE_MAPPING.items():
            abs_path = self._resolve_abs_path(rel_path)

            if not os.path.isfile(abs_path):
                continue

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    source = f.read()
            except Exception:
                continue

            for entry in entries:
                var_name = entry["var"]
                entry_type = entry.get("type")

                if entry_type == "dict":
                    keys = entry.get("keys", {})
                    for py_key in keys:
                        val = self._find_current_dict_value(source, var_name, py_key)
                        if val is not None:
                            line = self._find_line_number(source, var_name, py_key) or 0
                            label = f"{var_name}.{py_key}"
                            result[label] = (val, rel_path, line)
                elif entry_type == "const":
                    val = self._find_current_const_value(source, var_name)
                    if val is not None:
                        line = self._find_line_number(source, var_name) or 0
                        result[var_name] = (val, rel_path, line)

        return result


# ══════════════════════════════════════════════════════════════════════════════
# OffsetUpdateWorker — Фоновый поток для GUI интеграции
# ══════════════════════════════════════════════════════════════════════════════

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    _HAS_PYQT = True
except ImportError:
    try:
        from PyQt5.QtCore import QThread, pyqtSignal
        _HAS_PYQT = True
    except ImportError:
        _HAS_PYQT = False
        # Fallback — используем threading с callback'ами
        QThread = None  # type: ignore
        pyqtSignal = None  # type: ignore


def _run_updater_in_thread(
    updater: OffsetUpdater,
    local_path: Optional[str],
    dry_run: bool,
    progress_callback,
    finished_callback,
    error_callback,
):
    """
    Рабочая функция для фонового потока.

    Выполняет полный цикл: fetch → load → compare → backup → apply.
    """
    try:
        progress_callback("Загрузка оффсетов с сервера...")
        updater.fetch_live_offsets()

        if local_path:
            progress_callback("Загрузка локальных оффсетов...")
            updater.load_local_offsets(local_path)

        progress_callback("Сравнение версий...")
        comparison = updater.compare_versions()

        if not comparison["is_update_available"]:
            finished_callback({
                "success": True,
                "action": "none",
                "message": f"Обновлений нет (версия: {updater.remote_version})",
                "comparison": comparison,
            })
            return

        progress_callback(
            f"Найдено {comparison['total_changed_keys']} изменений. "
            f"Генерация плана..."
        )

        if not dry_run:
            progress_callback("Создание резервных копий...")
            updater.backup_files()

        progress_callback("Применение обновлений...")
        report = updater.apply_updates(dry_run=dry_run)

        action = "dry_run" if dry_run else "applied"
        msg = (
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Обновлено: {report['files_affected']} файлов, "
            f"{report['total_changes']} значений"
        )

        if report["errors"]:
            msg += f" ({len(report['errors'])} ошибок)"

        finished_callback({
            "success": report["success"],
            "action": action,
            "message": msg,
            "report": report,
            "comparison": comparison,
        })

    except Exception as e:
        error_callback(str(e))


if _HAS_PYQT and QThread is not None:

    class OffsetUpdateWorker(QThread):
        """
        Фоновый поток для обновления оффсетов (PyQt).

        Сигналы:
            signal_progress(str) — сообщение о прогрессе
            signal_finished(dict) — результат операции
            signal_error(str) — сообщение об ошибке
        """

        signal_progress = pyqtSignal(str)
        signal_finished = pyqtSignal(dict)
        signal_error = pyqtSignal(str)

        def __init__(
            self,
            updater: OffsetUpdater,
            local_path: Optional[str] = None,
            dry_run: bool = False,
            parent=None,
        ):
            super().__init__(parent)
            self._updater = updater
            self._local_path = local_path
            self._dry_run = dry_run

        def run(self) -> None:
            """Основной метод потока — вызывается при start()."""
            _run_updater_in_thread(
                self._updater,
                self._local_path,
                self._dry_run,
                self.signal_progress.emit,
                self.signal_finished.emit,
                self.signal_error.emit,
            )

else:

    class OffsetUpdateWorker(threading.Thread):
        """
        Фоновый поток для обновления оффсетов (threading fallback).

        Callbacks:
            on_progress: callable(str)
            on_finished: callable(dict)
            on_error: callable(str)
        """

        def __init__(
            self,
            updater: OffsetUpdater,
            local_path: Optional[str] = None,
            dry_run: bool = False,
            on_progress=None,
            on_finished=None,
            on_error=None,
        ):
            super().__init__(daemon=True)
            self._updater = updater
            self._local_path = local_path
            self._dry_run = dry_run
            self._on_progress = on_progress or (lambda msg: None)
            self._on_finished = on_finished or (lambda result: None)
            self._on_error = on_error or (lambda err: None)

        def run(self) -> None:
            """Основной метод потока."""
            _run_updater_in_thread(
                self._updater,
                self._local_path,
                self._dry_run,
                self._on_progress,
                self._on_finished,
                self._on_error,
            )


# ══════════════════════════════════════════════════════════════════════════════
# CLI interface для ручного запуска
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """CLI entry point: python -m robloxmemoryapi_addons.offset_updater."""
    import argparse

    parser = argparse.ArgumentParser(description="Offset Auto-Updater для Roblox")
    parser.add_argument("--base-dir", type=str, default=None, help="Корневая директория проекта")
    parser.add_argument("--local", type=str, default=None, help="Путь к локальному JSON файлу")
    parser.add_argument("--dry-run", action="store_true", help="Показать план без записи")
    parser.add_argument("--scan", action="store_true", help="Показать текущие оффсеты")
    parser.add_argument("--backup", action="store_true", help="Создать .bak копии")
    parser.add_argument("--rollback", action="store_true", help="Восстановить из .bak")
    parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    updater = OffsetUpdater(base_dir=args.base_dir)

    try:
        if args.rollback:
            result = updater.rollback()
            print(f"Восстановлено: {result['restored']}, Ошибок: {result['failed']}")
            return

        if args.backup:
            backed = updater.backup_files()
            print(f"Создано {len(backed)} резервных копий")
            return

        if args.scan:
            offsets = updater.get_all_current_offsets()
            print(f"\nТекущие оффсеты ({len(offsets)} найдено):\n")
            print(f"{'Переменная':<40} {'Значение':>10}  Файл")
            print("-" * 80)
            for name, (val, path, line) in sorted(offsets.items()):
                hex_val = OffsetUpdater._to_hex(val)
                print(f"{name:<40} {hex_val:>10}  {path}:{line}")
            return

        # Основной workflow
        updater.fetch_live_offsets()

        if args.local:
            updater.load_local_offsets(args.local)

        comparison = updater.compare_versions()

        if not comparison["is_update_available"]:
            print(f"✅ Обновлений нет (версия: {updater.remote_version})")
            return

        print(f"\n🔄 Доступно обновление:")
        print(f"   Удалённая версия: {updater.remote_version}")
        if updater.local_version:
            print(f"   Локальная версия: {updater.local_version}")
        print(f"   Изменено классов: {len(comparison['changed_classes'])}")
        print(f"   Изменено ключей:  {comparison['total_changed_keys']}")

        if args.dry_run:
            print(f"\n📋 План обновлений (dry-run):")
            plan = updater.get_update_plan()
            for change in plan:
                if change["old_value"] is None or change["old_value"] == change["new_value"]:
                    continue
                old_h = OffsetUpdater._to_hex(change["old_value"]) if change["old_value"] is not None else "???"
                new_h = OffsetUpdater._to_hex(change["new_value"])
                label = change["var"]
                if change["key"]:
                    label += f'["{change["key"]}"]'
                print(f"   {label}: {old_h} → {new_h}  ({change['file']})")
            print(f"\n   Всего: {len(plan)} записей")
        else:
            print(f"\n📦 Создание резервных копий...")
            updater.backup_files()

            print(f"⚡ Применение обновлений...")
            report = updater.apply_updates(dry_run=False)

            print(f"\n✅ Результат:")
            print(f"   Файлов обновлено: {report['files_affected']}")
            print(f"   Значений изменено: {report['total_changes']}")
            if report["errors"]:
                print(f"\n⚠️ Ошибки ({len(report['errors'])}):")
                for err in report["errors"]:
                    print(f"   - {err}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
