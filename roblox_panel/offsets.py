"""
Roblox Panel v4.1 — Offset Configuration
Актуальные оффсеты с https://imtheo.lol/Offsets
Roblox Version: version-689e359b09ad43b0
Dumped: 00:18 02/04/2026

Этот файл централизует все оффсеты для удобного обновления.
"""

# ═══════════════════════════════════════════════════════════════
# VISUAL ENGINE (World-to-Screen)
# ═══════════════════════════════════════════════════════════════
VISUAL_ENGINE_OFFSETS = {
    "Pointer": 0x7EF81D8,      # VisualEngine базовый указатель
    "Dimensions": 0xA60,       # Смещение к размерам экрана (width, height)
    "ViewMatrix": 0x130,       # Смещение к матрице вида (4x4 float)
    "RenderView": 0xB40,       # RenderView pointer
    "FakeDataModel": 0xA40,    # FakeDataModel pointer
}

# Для совместимости со server.py
_VISUAL_ENGINE_PTR = VISUAL_ENGINE_OFFSETS["Pointer"]
_VISUAL_ENGINE_DIMS = VISUAL_ENGINE_OFFSETS["Dimensions"]
_VISUAL_ENGINE_VM = VISUAL_ENGINE_OFFSETS["ViewMatrix"]

# ═══════════════════════════════════════════════════════════════
# TASK SCHEDULER (FPS, Jobs)
# ═══════════════════════════════════════════════════════════════
TASK_SCHEDULER_OFFSETS = {
    "Pointer": 0x8428188,      # TaskScheduler базовый указатель
    "JobStart": 0xC8,          # Начало списка задач
    "JobEnd": 0xD0,            # Конец списка задач
    "JobName": 0x18,           # Смещение к имени задачи
    "MaxFPS": 0xB0,            # Смещение к лимиту FPS
}

# ═══════════════════════════════════════════════════════════════
# HUMANOID (Health, Stats)
# ═══════════════════════════════════════════════════════════════
HUMANOID_OFFSETS = {
    "Health": 0x194,           # Текущее здоровье
    "MaxHealth": 0x1B4,        # Максимальное здоровье
    "WalkSpeed": 0x1CC,        # Скорость ходьбы (468 dec)
    "JumpPower": 0x1B0,        # Сила прыжка (432 dec)
    "RootPart": 0x478,         # HumanoidRootPart reference (1144 dec)
}

# ═══════════════════════════════════════════════════════════════
# PRIMITIVE / BASEPART (Position, Velocity)
# Применяется к HumanoidRootPart и другим частям
# ═══════════════════════════════════════════════════════════════
PRIMITIVE_OFFSETS = {
    "Position": 0xE4,          # Vector3 позиция (228 dec)
    "Velocity": 0xF0,          # AssemblyLinearVelocity (240 dec)
    "Size": 0x1B0,             # Размеры части
    "Rotation": 0xC0,          # Матрица поворота (192 dec)
}

# ═══════════════════════════════════════════════════════════════
# PLAYER (Team, Info)
# ═══════════════════════════════════════════════════════════════
PLAYER_OFFSETS = {
    "LocalPlayer": 0x130,      # LocalPlayer pointer
    "UserId": 0x2C8,           # ID пользователя
    "Team": 0x2A0,             # Team reference
    "Character": 0x398,        # ModelInstance (Character)
    "DisplayName": 0x130,      # Display name string
}

# ═══════════════════════════════════════════════════════════════
# CAMERA (Для альтернативного W2S)
# ═══════════════════════════════════════════════════════════════
CAMERA_OFFSETS = {
    "Position": 0x11C,         # Позиция камеры (284 dec)
    "ViewportSizeX": 0x128,    # Ширина вьюпорта
    "ViewportSizeY": 0x12C,    # Высота вьюпорта
    "FOV": 0x130,              # Поле зрения
}

# ═══════════════════════════════════════════════════════════════
# DATA MODEL (Game info)
# ═══════════════════════════════════════════════════════════════
DATAMODEL_OFFSETS = {
    "PlaceId": 0x198,          # Place ID (408 dec)
    "GameId": 0x190,           # Game ID (400 dec)
    "Workspace": 0x178,        # Workspace pointer (376 dec)
    "ScriptContext": 0x3F0,    # ScriptContext (1008 dec)
}

# ═══════════════════════════════════════════════════════════════
# INSTANCES (General)
# ═══════════════════════════════════════════════════════════════
INSTANCE_OFFSETS = {
    "Name": 0xB0,              # Имя объекта (176 dec)
    "Parent": 0x70,            # Родительский объект (112 dec)
    "Children": 0x78,          # Дети (начало списка)
    "ClassName": 0x8,          # Имя класса
}

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_all_offsets() -> dict:
    """Возвращает все оффсеты в одном словаре."""
    return {
        "VisualEngine": VISUAL_ENGINE_OFFSETS,
        "TaskScheduler": TASK_SCHEDULER_OFFSETS,
        "Humanoid": HUMANOID_OFFSETS,
        "Primitive": PRIMITIVE_OFFSETS,
        "Player": PLAYER_OFFSETS,
        "Camera": CAMERA_OFFSETS,
        "DataModel": DATAMODEL_OFFSETS,
        "Instance": INSTANCE_OFFSETS,
    }

def print_offsets():
    """Выводит все оффсеты в консоль."""
    import json
    print(json.dumps(get_all_offsets(), indent=2, default=lambda x: hex(x)))

if __name__ == "__main__":
    print("=" * 60)
    print("ROBLOX PANEL v4.1 - OFFSETS")
    print(f"Source: https://imtheo.lol/Offsets")
    print(f"Version: version-689e359b09ad43b0")
    print("=" * 60)
    print_offsets()
