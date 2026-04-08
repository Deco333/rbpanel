"""
Quick Start — Примеры использования всех модулей

Этот файл содержит готовые примеры для каждого нового модуля.
Скопируйте нужный пример в свой проект.
"""

# ═══════════════════════════════════════════════════════════════
# 0. БАЗОВАЯ НАСТРОЙКА
# ═══════════════════════════════════════════════════════════════

from robloxmemoryapi import RobloxGameClient
from robloxmemoryapi_addons import (
    patch_all,
    get_visual_engine,
    get_task_scheduler,
    get_w2s_helper,
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

# Подключение
client = RobloxGameClient()
if client.failed:
    print("Roblox не найден или не Windows")
    exit(1)

# Применяем патч — добавляет новые свойства к RBXInstance
modules = patch_all(client)

# Получаем DataModel
dm = client.DataModel

# ═══════════════════════════════════════════════════════════════
# 1. TASK SCHEDULER — FPS, MaxFPS, Jobs
# ═══════════════════════════════════════════════════════════════

ts = get_task_scheduler(client.memory_module)

print(f"MaxFPS: {ts.max_fps}")
ts.max_fps = 999           # снять лимит FPS
print(f"Jobs: {[j['name'] for j in ts.get_jobs()]}")

heartbeat = ts.find_job("Heartbeat")
if heartbeat:
    print(f"Heartbeat job address: 0x{heartbeat['address']:X}")


# ═══════════════════════════════════════════════════════════════
# 2. VISUAL ENGINE + W2S — ViewMatrix, World-to-Screen
# ═══════════════════════════════════════════════════════════════

ve = get_visual_engine(client.memory_module)

print(f"Viewport: {ve.width}x{ve.height}")
print(f"Lighting Valid: {ve.lighting_valid}")
print(f"Sky Valid: {ve.sky_valid}")

# World-to-Screen
from robloxmemoryapi.utils.rbx.datastructures import Vector3

w2s = get_w2s_helper(client.memory_module)

# Проверяем, видна ли точка на экране
world_pos = Vector3(100, 50, 200)
result = w2s.world_to_screen(world_pos)

if result.on_screen:
    print(f"Screen pos: ({result.x:.0f}, {result.y:.0f})")
    print(f"Depth: {result.depth:.2f}")

# Batch W2S
positions = [Vector3(i * 10, 0, 0) for i in range(10)]
results = w2s.world_to_screen_many(positions)
visible_count = sum(1 for r in results if r.on_screen)
print(f"Visible: {visible_count}/{len(positions)}")

# Размер объекта в пикселях для ESP box
box_height = w2s.world_distance_to_screen_size(world_pos, 5.0)
print(f"Box height for 5-stud object: {box_height:.0f}px")


# ═══════════════════════════════════════════════════════════════
# 3. RUN SERVICE — FPS
# ═══════════════════════════════════════════════════════════════

dm_addr = get_data_model_address(client.memory_module)
rs = get_run_service(client.memory_module, dm_addr)

print(f"Current FPS: {rs.fps:.1f}")
print(f"Is running: {rs.is_running}")

# Измерить средний FPS за 2 секунды
avg_fps = rs.measure_fps(samples=20, interval=0.1)
print(f"Average FPS: {avg_fps:.1f}")


# ═══════════════════════════════════════════════════════════════
# 4. SCRIPT CONTEXT — RequireBypass
# ═══════════════════════════════════════════════════════════════

sc = get_script_context(client.memory_module, dm_addr)
print(f"ScriptContext address: 0x{sc.address:X}")
print(f"RequireBypass: {sc.require_bypass}")


# ═══════════════════════════════════════════════════════════════
# 5. TERRAIN — Water, Grass, MaterialColors
# ═══════════════════════════════════════════════════════════════

terrain_instance = dm.Workspace.FindFirstChild("Terrain")
if terrain_instance:
    terrain = wrap_terrain(terrain_instance)

    # Вода
    print(f"Water Color: {terrain.water_color}")
    print(f"Water Transparency: {terrain.water_transparency}")
    terrain.water_transparency = 0.5
    terrain.water_wave_size = 2.0

    # Трава
    terrain.grass_length = 0.5

    # Цвета материалов
    mc = terrain.get_material_colors()
    print(f"Grass color: {mc.grass}")
    mc.snow = (1, 1, 1)          # белый снег
    mc.asphalt = (0.2, 0.2, 0.2) # тёмный асфальт

    # Все материалы сразу
    all_colors = mc.get_all()
    for name, color in all_colors.items():
        print(f"  {name}: {color}")

    # Установить один цвет для ВСЕХ материалов
    # mc.set_all(Color3(0.5, 0.5, 0.5))


# ═══════════════════════════════════════════════════════════════
# 6. SKY — Skybox, Sun, Moon
# ═══════════════════════════════════════════════════════════════

sky_instance = dm.Lighting.FindFirstChildOfClass("Sky")
if sky_instance:
    sky = wrap_sky(sky_instance)

    print(f"Stars: {sky.star_count}")
    sky.star_count = 5000
    sky.sun_angular_size = 30
    sky.moon_angular_size = 20

    # Все грани скайбокса
    skybox = sky.get_all_skybox()
    print(f"Front: {skybox['Front']}")

    # Установить одну текстуру на все грани
    # sky.set_skybox("rbxassetid://123456789")


# ═══════════════════════════════════════════════════════════════
# 7. ATMOSPHERE — Density, Haze, Glare
# ═══════════════════════════════════════════════════════════════

atm_instance = dm.Lighting.FindFirstChildOfClass("Atmosphere")
if atm_instance:
    atm = wrap_atmosphere(atm_instance)
    print(f"Density: {atm.density}")
    atm.density = 0.4
    atm.haze = 5
    atm.glare = 2
    atm.color = (0.8, 0.9, 1.0)


# ═══════════════════════════════════════════════════════════════
# 8. POST-PROCESSING — Bloom, DoF, SunRays
# ═══════════════════════════════════════════════════════════════

bloom_instance = dm.Lighting.FindFirstChildOfClass("BloomEffect")
if bloom_instance:
    bloom = wrap_bloom(bloom_instance)
    bloom.intensity = 0.8
    bloom.size = 30
    bloom.threshold = 0.9
    bloom.enabled = True

dof_instance = dm.Lighting.FindFirstChildOfClass("DepthOfFieldEffect")
if dof_instance:
    dof = wrap_dof(dof_instance)
    dof.focus_distance = 50
    dof.far_intensity = 0.3
    dof.near_intensity = 0.1

sunrays_instance = dm.Lighting.FindFirstChildOfClass("SunRaysEffect")
if sunrays_instance:
    sr = wrap_sunrays(sunrays_instance)
    sr.intensity = 0.5
    sr.spread = 1.0


# ═══════════════════════════════════════════════════════════════
# 9. DRAG DETECTOR
# ═══════════════════════════════════════════════════════════════

dd_instance = dm.Workspace.FindFirstChildOfClass("DragDetector")
if dd_instance:
    dd = wrap_drag_detector(dd_instance)
    print(f"Max Force: {dd.max_force}")
    dd.max_force = Vector3(100000, 100000, 100000)
    dd.responsiveness = 15
    dd.max_drag_translation = (50, 50, 50)


# ═══════════════════════════════════════════════════════════════
# 10. PLAYER MOUSE
# ═══════════════════════════════════════════════════════════════

player = dm.Players.LocalPlayer
if player:
    mouse = wrap_player_mouse(player)
    if mouse.is_valid:
        print(f"Current cursor: {mouse.icon}")
        # mouse.icon = "rbxassetid://12345"


# ═══════════════════════════════════════════════════════════════
# 11. НОВЫЕ СВОЙСТВА RBXInstance (после patch_all)
# ═══════════════════════════════════════════════════════════════

# BasePart
part = dm.Workspace.FindFirstChildOfClass("Part")
if part:
    print(f"CastShadow: {part.CastShadow}")
    print(f"Material: {part.Material}")
    print(f"Shape: {part.Shape}")
    part.CastShadow = False
    part.Material = 256  # ForceField

# Model
model = dm.Workspace.FindFirstChildOfClass("Model")
if model:
    print(f"ModelScale: {model.ModelScale}")
    model.ModelScale = 2.0

# SpecialMesh
mesh = dm.Workspace.FindFirstChildOfClass("SpecialMesh")
if mesh:
    print(f"MeshScale: {mesh.MeshScale}")
    print(f"MeshId: {mesh.MeshId}")
    mesh.MeshScale = Vector3(2, 2, 2)

# Decal
decal = dm.Workspace.FindFirstChildOfClass("Decal")
if decal:
    print(f"Texture: {decal.Texture}")

# UnionOperation
union = dm.Workspace.FindFirstChildOfClass("UnionOperation")
if union:
    print(f"AssetId: {union.AssetId}")

# ProximityPrompt
prompt = dm.Workspace.FindFirstChildOfClass("ProximityPrompt")
if prompt:
    print(f"KeyCode: {prompt.KeyCode}")
    print(f"GamepadKeyCode: {prompt.GamepadKeyCode}")

# Lighting (новые)
print(f"LightColor: {dm.Lighting.LightColor}")
print(f"GradientTop: {dm.Lighting.GradientTop}")
print(f"LightDirection: {dm.Lighting.LightDirection}")

# SurfaceAppearance (новые)
sa = dm.Workspace.FindFirstChildOfClass("SurfaceAppearance")
if sa:
    print(f"EmissiveTint: {sa.EmissiveTint}")
    print(f"NormalMap: {sa.NormalMap}")
    print(f"MetalnessMap: {sa.MetalnessMap}")
    sa.EmissiveTint = (1, 0, 0)  # красное свечение

# Post-processing Enabled
bloom = dm.Lighting.FindFirstChildOfClass("BloomEffect")
if bloom:
    print(f"PostEnabled: {bloom.PostEnabled}")
    bloom.PostEnabled = False  # отключить


# ═══════════════════════════════════════════════════════════════
# 12. ПОЛНЫЙ W2S ESP ПРИМЕР
# ═══════════════════════════════════════════════════════════════

def draw_esp_box(w2s_helper, instance):
    """Рисует ESP box вокруг BasePart."""
    if not hasattr(instance, "Position") or not hasattr(instance, "Size"):
        return

    pos = instance.Position
    size = instance.Size
    if not isinstance(pos, Vector3) or not isinstance(size, Vector3):
        return

    # Верхняя и нижняя точки bounding box
    top = Vector3(pos.X, pos.Y + size.Y, pos.Z)
    bottom = pos

    top_screen = w2s_helper.world_to_screen(top)
    bottom_screen = w2s_helper.world_to_screen(bottom)

    if top_screen.on_screen and bottom_screen.on_screen:
        box_height = abs(top_screen.y - bottom_screen.y)
        box_width = box_height * 0.6  # примерное соотношение

        center_x = (top_screen.x + bottom_screen.x) / 2
        left = center_x - box_width / 2

        # Здесь можно рисовать (например, через overlay)
        print(
            f"  {instance.Name}: "
            f"box=({left:.0f}, {top_screen.y:.0f}, {box_width:.0f}, {box_height:.0f}) "
            f"depth={top_screen.depth:.1f}"
        )


# Использование
w2s = get_w2s_helper(client.memory_module)
for descendant in dm.Workspace.GetDescendants():
    if descendant.ClassName in ("Part", "MeshPart"):
        draw_esp_box(w2s, descendant)

client.close()
