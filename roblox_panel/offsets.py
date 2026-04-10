"""
Roblox Panel v4.1 — Offset Configuration
Актуальные оффсеты с https://imtheo.lol/Offsets
Roblox Version: version-26c90be22e0d4758
Dumped: 21:56 09/04/2026

Этот файл централизует все оффсеты для удобного обновления.
"""

# ═══════════════════════════════════════════════════════════════
# VISUAL ENGINE (World-to-Screen)
# ═══════════════════════════════════════════════════════════════
VISUAL_ENGINE_OFFSETS = {
    "Pointer": 0x75CC058,       # VisualEngine базовый указатель (123519064 dec)
    "Dimensions": 0xA60,        # Смещение к размерам экрана (width, height) - 2656
    "ViewMatrix": 0x130,        # Смещение к матрице вида (4x4 float) - 304
    "RenderView": 0xB40,        # RenderView pointer - 2880
    "FakeDataModel": 0xA40,     # FakeDataModel pointer - 2624
}

# Для совместимости со server.py
_VISUAL_ENGINE_PTR = VISUAL_ENGINE_OFFSETS["Pointer"]
_VISUAL_ENGINE_DIMS = VISUAL_ENGINE_OFFSETS["Dimensions"]
_VISUAL_ENGINE_VM = VISUAL_ENGINE_OFFSETS["ViewMatrix"]

# ═══════════════════════════════════════════════════════════════
# TASK SCHEDULER (FPS, Jobs)
# ═══════════════════════════════════════════════════════════════
TASK_SCHEDULER_OFFSETS = {
    "Pointer": 0x7AF5090,       # TaskScheduler базовый указатель (128929936 dec)
    "JobStart": 0xC8,           # Начало списка задач - 200
    "JobEnd": 0xD0,             # Конец списка задач - 208
    "JobName": 0x18,            # Смещение к имени задачи - 24
    "MaxFPS": 0xB0,             # Смещение к лимиту FPS - 176
}

# ═══════════════════════════════════════════════════════════════
# HUMANOID (Health, Stats)
# ═══════════════════════════════════════════════════════════════
HUMANOID_OFFSETS = {
    "Health": 0x194,            # Текущее здоровье - 404
    "MaxHealth": 0x1B4,         # Максимальное здоровье - 436
    "WalkSpeed": 0x1D4,         # Скорость ходьбы - 468
    "JumpPower": 0x1B0,         # Сила прыжка - 432
    "RootPart": 0x478,          # HumanoidRootPart reference - 1144
    "PlatformStand": 0x1DF,     # PlatformStand - 479
    "Sit": 0x1E0,               # Sit - 480
    "Jump": 0x1DD,              # Jump - 477
}

# ═══════════════════════════════════════════════════════════════
# PRIMITIVE / BASEPART (Position, Velocity)
# Применяется к HumanoidRootPart и другим частям
# ═══════════════════════════════════════════════════════════════
PRIMITIVE_OFFSETS = {
    "Position": 0xE4,           # Vector3 позиция - 228
    "Velocity": 0xF0,           # AssemblyLinearVelocity - 240
    "Size": 0x1B0,              # Размеры части - 432
    "Rotation": 0xC0,           # Матрица поворота - 192
    "Flags": 0x1AE,             # Flags (CanCollide, Anchored) - 430
    "AngularVelocity": 0xFC,    # AssemblyAngularVelocity - 252
}

# BasePart специфичные оффсеты
BASEPART_OFFSETS = {
    "Primitive": 0x148,         # Pointer to Primitive - 328
    "Transparency": 0xF0,       # Transparency value - 240
    "Color3": 0x49,             # Color3 value - 73
    "Shape": 0x1B1,             # Shape type - 433
    "Massless": 0xF7,           # Massless flag - 247
    "CastShadow": 0xF5,         # CastShadow flag - 245
    "Locked": 0xF6,             # Locked flag - 246
    "Reflectance": 0xEC,        # Reflectance value - 236
}

# ═══════════════════════════════════════════════════════════════
# PLAYER (Team, Info)
# ═══════════════════════════════════════════════════════════════
PLAYER_OFFSETS = {
    "LocalPlayer": 0x130,       # LocalPlayer pointer - 304
    "UserId": 0x2C8,            # ID пользователя - 712
    "Team": 0x2A0,              # Team reference - 672
    "Character": 0x398,         # ModelInstance (Character) - 920
    "DisplayName": 0x130,       # Display name string - 304
    "Mouse": 0xFC8,             # Player Mouse - 4040
}

# ═══════════════════════════════════════════════════════════════
# CAMERA (Для альтернативного W2S)
# ═══════════════════════════════════════════════════════════════
CAMERA_OFFSETS = {
    "Position": 0x11C,          # Позиция камеры - 284
    "ViewportSizeX": 0x128,     # Ширина вьюпорта
    "ViewportSizeY": 0x12C,     # Высота вьюпорта
    "FOV": 0x130,               # Поле зрения
}

# ═══════════════════════════════════════════════════════════════
# DATA MODEL (Game info)
# ═══════════════════════════════════════════════════════════════
DATAMODEL_OFFSETS = {
    "PlaceId": 0x198,           # Place ID - 408
    "GameId": 0x190,            # Game ID - 400
    "Workspace": 0x178,         # Workspace pointer - 376
    "ScriptContext": 0x3F0,     # ScriptContext - 1008
}

# ═══════════════════════════════════════════════════════════════
# WORKSPACE
# ═══════════════════════════════════════════════════════════════
WORKSPACE_OFFSETS = {
    "World": 0x400,             # World pointer - 1024
    "Gravity": 0x9B0,           # Gravity setting - 2480
    "CurrentCamera": 0x488,     # CurrentCamera - 1160
}

# ═══════════════════════════════════════════════════════════════
# RENDERVIEW
# ═══════════════════════════════════════════════════════════════
RENDERVIEW_OFFSETS = {
    "LightingValid": 0x148,     # Lighting valid flag - 328
    "SkyValid": 0x28D,          # Sky valid flag - 653
    "VisualEngine": 0x10,       # VisualEngine pointer - 16
    "DeviceD3D11": 0x8,         # D3D11 Device - 8
}

# ═══════════════════════════════════════════════════════════════
# INSTANCES (General)
# ═══════════════════════════════════════════════════════════════
INSTANCE_OFFSETS = {
    "Name": 0xB0,               # Имя объекта - 176
    "Parent": 0x70,             # Родительский объект - 112
    "Children": 0x78,           # Дети (начало списка)
    "ClassName": 0x8,           # Имя класса
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
        "BasePart": BASEPART_OFFSETS,
        "Player": PLAYER_OFFSETS,
        "Camera": CAMERA_OFFSETS,
        "DataModel": DATAMODEL_OFFSETS,
        "Workspace": WORKSPACE_OFFSETS,
        "RenderView": RENDERVIEW_OFFSETS,
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
    print(f"Version: version-26c90be22e0d4758")
    print(f"Dumped: 21:56 09/04/2026")
    print("=" * 60)
    print_offsets()
