╔══════════════════════════════════════════════════════════════════╗
║        RobloxMemoryAPI Addons — Инструкция по установке       ║
║                      Версия 1.0.0                             ║
╚══════════════════════════════════════════════════════════════════╝

ОГЛАВЛЕНИЕ
─────────────────────────────────────────────────────────────────
 1. Описание
 2. Системные требования
 3. Установка
 4. Быстрый старт
 5. Список модулей
 6. Новые свойства RBXInstance
 7. API Reference по модулям
 8. Примеры использования
 9. Архитектура и взаимодействие
10. Ограничения и замечания
11. Структура файлов


═══════════════════════════════════════════════════════════════════
 1. ОПИСАНИЕ
═══════════════════════════════════════════════════════════════════

RobloxMemoryAPI Addons — это набор из 14 модулей (3755 строк кода),
расширяющих библиотеку RobloxMemoryAPI новыми возможностями.

Что добавлено:
  • TaskScheduler — управление задачами Roblox, MaxFPS
  • VisualEngine — ViewMatrix, RenderView, размеры вьюпорта
  • W2SHelper — World-to-Screen для ESP / aimbot
  • RunService — HeartbeatFPS, определение загрузки игры
  • Terrain — вода, трава, 22 материала террейна
  • MaterialColors — управление цветами всех материалов
  • Sky — Skybox (6 граней), Sun, Moon, StarCount
  • Atmosphere — Density, Haze, Glare, Decay
  • BloomEffect — Intensity, Size, Threshold
  • DepthOfFieldEffect — FocusDistance, Near/FarIntensity
  • SunRaysEffect — Intensity, Spread
  • DragDetector — Force, Torque, Responsiveness
  • ScriptContext — RequireBypass
  • PlayerMouse — Icon, Workspace reference
  • 22 новых свойства для RBXInstance (CastShadow, Material,
    Shape, LightColor, GradientTop, EmissiveTint и другие)


═══════════════════════════════════════════════════════════════════
 2. СИСТЕМНЫЕ ТРЕБОВАНИЯ
═══════════════════════════════════════════════════════════════════

  • Python >= 3.9
  • Windows (для работы с процессом Roblox)
  • Установленный RobloxMemoryAPI:
        pip install robloxmemoryapi

    Или из исходников:
        pip install git+https://github.com/notpoiu/RobloxMemoryAPI.git

  • Запущенный процесс RobloxPlayerBeta.exe


═══════════════════════════════════════════════════════════════════
 3. УСТАНОВКА
═══════════════════════════════════════════════════════════════════

Способ A — Скопировать в проект:

  1. Распакуйте robloxmemoryapi_addons.zip
  2. Скопируйте папку robloxmemoryapi_addons в корень вашего проекта:

     ваш_проект/
     ├── main.py
     ├── robloxmemoryapi_addons/     ← сюда
     │   ├── __init__.py
     │   ├── task_scheduler.py
     │   ├── visual_engine.py
     │   ├── ...
     └── ...

  3. Используйте в коде:
     from robloxmemoryapi_addons import patch_all


Способ B — Установить как пакет (если есть setup.py):

  1. Распакуйте архив
  2. Выполните:
     cd robloxmemoryapi_addons
     pip install .

  3. Используйте:
     from robloxmemoryapi_addons import patch_all


═══════════════════════════════════════════════════════════════════
 4. БЫСТРЫЙ СТАРТ
═══════════════════════════════════════════════════════════════════

from robloxmemoryapi import RobloxGameClient
from robloxmemoryapi_addons import patch_all, get_w2s_helper, get_task_scheduler

# 1. Подключение к Roblox
client = RobloxGameClient(allow_write=True)
if client.failed:
    print("Roblox не найден")
    exit(1)

# 2. Применить патч — добавляет 22 новых свойства к RBXInstance
modules = patch_all(client)

# 3. Получить DataModel
dm = client.DataModel

# 4. TaskScheduler — снять лимит FPS
ts = get_task_scheduler(client.memory_module)
ts.max_fps = 999
print(f"MaxFPS: {ts.max_fps}")

# 5. World-to-Screen — проверка видимости точки
from robloxmemoryapi.utils.rbx.datastructures import Vector3

w2s = get_w2s_helper(client.memory_module)
result = w2s.world_to_screen(Vector3(100, 50, 200))
print(f"На экране: {result.on_screen}, X={result.x:.0f}, Y={result.y:.0f}")

# 6. Новые свойства RBXInstance
part = dm.Workspace.FindFirstChildOfClass("Part")
if part:
    print(f"CastShadow: {part.CastShadow}")
    print(f"Material: {part.Material}")
    part.CastShadow = False
    part.Material = 256  # ForceField

# 7. Terrain — управление водой
terrain = dm.Workspace.FindFirstChild("Terrain")
if terrain:
    from robloxmemoryapi_addons import wrap_terrain
    t = wrap_terrain(terrain)
    t.water_transparency = 0.5
    t.water_wave_size = 2.0

# 8. Lighting — новые свойства
print(f"LightColor: {dm.Lighting.LightColor}")
print(f"GradientTop: {dm.Lighting.GradientTop}")
dm.Lighting.LightColor = (1.0, 0.95, 0.9)

client.close()


═══════════════════════════════════════════════════════════════════
 5. СПИСОК МОДУЛЕЙ
═══════════════════════════════════════════════════════════════════

Файл                  | Класс/Функция              | Описание
─────────────────────────────────────────────────────────────────────────
task_scheduler.py     | TaskScheduler               | Диспетчер задач Roblox
                      |   .max_fps (float, r/w)     | Лимит FPS
                      |   .address (int)            | Адрес в памяти
                      |   .get_jobs()               | Список всех jobs
                      |   .find_job(name)           | Поиск job по имени
                      |   .refresh()                | Переобновить адрес
─────────────────────────────────────────────────────────────────────────
visual_engine.py      | VisualEngine                | Движок рендеринга
                      |   .dimensions (tuple, r/w)  | (ширина, высота)
                      |   .width / .height          | Чтение размеров
                      |   .view_matrix (list)       | 4x4 matrix (row-major)
                      |   .view_matrix_raw (list)   | 16 float (column-major)
                      |   .render_view              | RenderView объект
                      |   .lighting_valid (bool)    | Валидность лайтинга
                      |   .sky_valid (bool)         | Валидность скайбокса
                      |   .refresh()                | Переобновить адрес
                      |                              |
                      | RenderView                  | Вьюпорт рендера
                      |   .lighting_valid           | Валидность лайтинга
                      |   .sky_valid                | Валидность скайбокса
                      |   .device_d3d11_address     | D3D11 Device
                      |                              |
                      | W2SHelper                   | World-to-Screen
                      |   .world_to_screen(pos)     | 3D → 2D на экране
                      |   .world_to_screen_many()   | Batch W2S
                      |   .is_visible(pos)          | Быстрая проверка
                      |   .world_distance_to_       | Размер в пикселях
                      |     screen_size(pos, size)  | для ESP box
                      |                              |
                      | W2SResult                   | Результат W2S
                      |   .x, .y (float)            | Экранные координаты
                      |   .on_screen (bool)         | Видимость
                      |   .depth (float)            | Глубина (clip w)
                      |   .to_tuple()               | (x, y, on_screen)
─────────────────────────────────────────────────────────────────────────
run_service.py        | RunServiceWrapper           | Сервис выполнения
                      |   .fps (float)              | Текущий HeartbeatFPS
                      |   .heartbeat_task (int)     | Адрес heartbeat
                      |   .is_running (bool)        | Игра загружена?
                      |   .wait_for_game_load()     | Ожидание загрузки
                      |   .measure_fps()            | Средний FPS за N выборок
─────────────────────────────────────────────────────────────────────────
terrain.py            | TerrainWrapper              | Террейн
                      |   .water_color (Color3,r/w) | Цвет воды
                      |   .water_reflectance (f,r/w)| Отражение воды
                      |   .water_transparency (f)   | Прозрачность воды
                      |   .water_wave_size (f)      | Размер волны
                      |   .water_wave_speed (f)     | Скорость волны
                      |   .grass_length (f)         | Длина травы
                      |   .get_material_colors()    | MaterialColors объект
                      |                              |
                      | MaterialColors              | 22 материала
                      |   .grass, .snow, .asphalt   | Индивидуальные (r/w)
                      |   .get(name)                | Получить по имени
                      |   .set(name, value)         | Установить по имени
                      |   .get_all()                | Все цвета (dict)
                      |   .set_all(value)           | Один цвет для всех
                      |   [name]                    | Доступ по индексу
                      |                              |
                      | WorldWrapper                | Физический мир
                      |   .primitive_count (int)    | Кол-во примитивов
─────────────────────────────────────────────────────────────────────────
sky.py                | SkyWrapper                  | Скайбокс
                      |   .skybox_back/front/...    | 6 граней (str, r/w)
                      |   .set_skybox(asset_id)     | Текстура на все грани
                      |   .get_all_skybox()         | Все 6 текстур (dict)
                      |   .sun_angular_size (f,r/w) | Угловой размер солнца
                      |   .sun_texture_id (str,r/w) | Текстура солнца
                      |   .moon_angular_size (f)    | Угловой размер луны
                      |   .moon_texture_id (str)    | Текстура луны
                      |   .star_count (int, r/w)    | Количество звёзд
                      |   .skybox_orientation (f)   | Ориентация скайбокса
─────────────────────────────────────────────────────────────────────────
atmosphere.py         | AtmosphereWrapper           | Атмосфера
                      |   .density (float, r/w)     | Плотность
                      |   .offset (float, r/w)      | Смещение
                      |   .color (Color3, r/w)      | Цвет
                      |   .decay (float, r/w)       | Затухание
                      |   .glare (float, r/w)       | Блик
                      |   .haze (float, r/w)        | Дымка
─────────────────────────────────────────────────────────────────────────
post_processing.py    | BloomEffectWrapper          | Bloom
                      |   .intensity (f, r/w)       | Интенсивность
                      |   .size (f, r/w)            | Размер
                      |   .threshold (f, r/w)       | Порог
                      |   .enabled (bool, r/w)      | Вкл/выкл
                      |                              |
                      | DepthOfFieldEffectWrapper   | Глубина резкости
                      |   .focus_distance (f, r/w)  | Дистанция фокуса
                      |   .far_intensity (f, r/w)   | Размытие далеко
                      |   .near_intensity (f, r/w)  | Размытие близко
                      |   .in_focus_radius (f, r/w) | Радиус фокуса
                      |   .enabled (bool, r/w)      | Вкл/выкл
                      |                              |
                      | SunRaysEffectWrapper        | Лучи солнца
                      |   .intensity (f, r/w)       | Интенсивность
                      |   .spread (f, r/w)          | Разброс
                      |   .enabled (bool, r/w)      | Вкл/выкл
─────────────────────────────────────────────────────────────────────────
drag_detector.py      | DragDetectorWrapper         | Детектор перетаскивания
                      |   .reference_instance       | Привязанный объект
                      |   .max_activation_dist (f)  | Дистанция активации
                      |   .max_drag_angle (V3,r/w)  | Макс. угол
                      |   .min_drag_angle (V3,r/w)  | Мин. угол
                      |   .max_drag_translation(V3) | Макс. перемещение
                      |   .min_drag_translation(V3) | Мин. перемещение
                      |   .max_force (V3, r/w)      | Макс. сила
                      |   .max_torque (V3, r/w)     | Макс. момент
                      |   .responsiveness (f, r/w)  | Отзывчивость
                      |   .cursor_icon (str, r/w)   | Курсор
                      |   .activated_cursor_icon    | Курсор при активации
─────────────────────────────────────────────────────────────────────────
script_context.py     | ScriptContextWrapper        | Контекст скриптов
                      |   .address (int)            | Адрес ScriptContext
                      |   .require_bypass (bool,r/w)| RequireBypass флаг
─────────────────────────────────────────────────────────────────────────
player_mouse.py       | PlayerMouseWrapper          | Мышь игрока
                      |   .is_valid (bool)          | Character загружен?
                      |   .icon (str, r/w)          | Иконка курсора
                      |   .workspace (RBXInstance)  | Workspace ссылка
─────────────────────────────────────────────────────────────────────────
enhanced_instance.py  | (monkey-patch RBXInstance)  | Новые свойства
─────────────────────────────────────────────────────────────────────────
patch.py              | patch_all()                 | Применить все патчи
                      | get_visual_engine()         | Быстрое создание VE
                      | get_task_scheduler()        | Быстрое создание TS
                      | get_w2s_helper()            | Быстрое создание W2S
                      | get_run_service()           | Быстрое создание RS
                      | get_script_context()        | Быстрое создание SC
                      | get_data_model_address()    | Адрес DataModel
                      | wrap_terrain()              | Обёртка Terrain
                      | wrap_sky()                  | Обёртка Sky
                      | wrap_atmosphere()           | Обёртка Atmosphere
                      | wrap_bloom()                | Обёртка Bloom
                      | wrap_dof()                  | Обёртка DepthOfField
                      | wrap_sunrays()              | Обёртка SunRays
                      | wrap_drag_detector()        | Обёртка DragDetector
                      | wrap_player_mouse()         | Обёртка PlayerMouse
─────────────────────────────────────────────────────────────────────────


═══════════════════════════════════════════════════════════════════
 6. НОВЫЕ СВОЙСТВА RBXInstance
═══════════════════════════════════════════════════════════════════

После вызова patch_all(client) к RBXInstance добавляются
следующие свойства. Класс проверяется автоматически —
свойство вернёт None если ClassName не совпадает.

┌───────────────────────────────────────────────────────────────┐
│ BASEPART                                                      │
├────────────────────────┬──────────┬───────────────────────────┤
│ Свойство               │ Тип      │ Доступ                    │
├────────────────────────┼──────────┼───────────────────────────┤
│ CastShadow             │ bool     │ Чтение / Запись           │
│ Shape                  │ int      │ Только чтение             │
│ Material               │ int      │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ MODEL                                                         │
├────────────────────────┬──────────┬───────────────────────────┤
│ ModelScale             │ float    │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ SPECIALMESH                                                   │
├────────────────────────┬──────────┬───────────────────────────┤
│ MeshScale              │ Vector3  │ Чтение / Запись           │
│ MeshId                 │ str      │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ DECAL / TEXTURE                                               │
├────────────────────────┬──────────┬───────────────────────────┤
│ Texture                │ str      │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ UNIONOPERATION                                               │
├────────────────────────┬──────────┬───────────────────────────┤
│ AssetId                │ str      │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ PROXIMITYPROMPT                                               │
├────────────────────────┬──────────┬───────────────────────────┤
│ KeyCode                │ int      │ Только чтение             │
│ GamepadKeyCode         │ int      │ Только чтение             │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ LIGHTING                                                      │
├────────────────────────┬──────────┬───────────────────────────┤
│ LightColor             │ Color3   │ Чтение / Запись           │
│ GradientTop            │ Color3   │ Чтение / Запись           │
│ GradientBottom         │ Color3   │ Чтение / Запись           │
│ LightDirection         │ Vector3  │ Только чтение             │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ SURFACEAPPEARANCE                                             │
├────────────────────────┬──────────┬───────────────────────────┤
│ ColorMap               │ str      │ Только чтение             │
│ EmissiveMaskContent    │ str      │ Только чтение             │
│ EmissiveTint           │ Color3   │ Чтение / Запись           │
│ MetalnessMap           │ str      │ Только чтение             │
│ NormalMap              │ str      │ Только чтение             │
│ RoughnessMap           │ str      │ Только чтение             │
└────────────────────────┴──────────┴───────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ POST-PROCESSING EFFECTS                                       │
│ (Bloom, DepthOfField, SunRays, ColorCorrection, etc)          │
├────────────────────────┬──────────┬───────────────────────────┤
│ PostEnabled            │ bool     │ Чтение / Запись           │
└────────────────────────┴──────────┴───────────────────────────┘


═══════════════════════════════════════════════════════════════════
 7. API REFERENCE ПО МОДУЛЯМ
═══════════════════════════════════════════════════════════════════

── TaskScheduler ──────────────────────────────────────────────

  from robloxmemoryapi_addons.task_scheduler import TaskScheduler

  ts = TaskScheduler(memory_module)
  ts.max_fps          → float   # текущий лимит
  ts.max_fps = 999    → None    # установить лимит (0 = безлимит)
  ts.address          → int     # адрес TaskScheduler
  ts.get_jobs()       → list[dict]  # [{"name": "Heartbeat", ...}, ...]
  ts.find_job("Render") → dict|None
  ts.refresh()        → None    # переобновить адрес

── VisualEngine ───────────────────────────────────────────────

  from robloxmemoryapi_addons.visual_engine import (
      VisualEngine, RenderView, W2SHelper, W2SResult
  )

  ve = VisualEngine(memory_module)
  ve.dimensions        → (float, float)    # (1920, 1080)
  ve.width             → float
  ve.height            → float
  ve.dimensions = (1280, 720)               # установить
  ve.view_matrix       → list[list[float]]  # 4x4 row-major
  ve.view_matrix_raw   → list[float]        # 16 float column-major
  ve.render_view       → RenderView
  ve.lighting_valid    → bool
  ve.sky_valid         → bool
  ve.refresh()

── W2SHelper (World-to-Screen) ────────────────────────────────

  w2s = W2SHelper(visual_engine)

  # Одиночная проекция
  result = w2s.world_to_screen(Vector3(100, 50, 200))
  result.x             → float    # экранный X
  result.y             → float    # экранный Y
  result.on_screen     → bool     # видимость
  result.depth         → float    # глубина (clip w)
  result.to_tuple()    → (x, y, bool)

  # Batch
  results = w2s.world_to_screen_many([v1, v2, v3])
  w2s.is_visible(pos)  → bool     # быстрая проверка

  # ESP box sizing
  px = w2s.world_distance_to_screen_size(pos, 5.0)  # пиксели

── RunService ─────────────────────────────────────────────────

  from robloxmemoryapi_addons.run_service import RunServiceWrapper

  rs = RunServiceWrapper(memory_module, data_model_address)
  rs.fps               → float    # текущий FPS
  rs.heartbeat_task    → int      # адрес heartbeat
  rs.is_running        → bool     # игра загружена?
  rs.wait_for_game_load(timeout=30)  → bool
  rs.measure_fps(samples=20, interval=0.1) → float

── Terrain ────────────────────────────────────────────────────

  from robloxmemoryapi_addons.terrain import TerrainWrapper
  from robloxmemoryapi_addons import wrap_terrain

  # Обёртка для RBXInstance с ClassName "Terrain"
  terrain = wrap_terrain(terrain_instance)
  # или:
  terrain = TerrainWrapper(terrain_instance)

  terrain.water_color           → Color3
  terrain.water_color = Color3(0, 0.3, 1)
  terrain.water_reflectance     → float
  terrain.water_transparency    → float
  terrain.water_wave_size       → float
  terrain.water_wave_speed      → float
  terrain.grass_length          → float

  mc = terrain.get_material_colors()
  mc.grass           → Color3
  mc.snow = (1,1,1)             # tuple работает
  mc.asphalt = Color3(0.2, 0.2, 0.2)
  mc.get("Grass")               → Color3
  mc.set("Snow", (1, 1, 1))
  mc.get_all()                  → dict[str, Color3]
  mc.set_all(Color3(0.5, 0.5, 0.5))  # все материалы сразу

── MaterialColors (доступные материалы) ──────────────────────

  asphalt, basalt, brick, cobblestone, concrete, cracked_lava,
  glacier, grass, ground, ice, leafy_grass, limestone, mud,
  pavement, rock, salt, sand, sandstone, slate, snow, wood_planks

── Sky ────────────────────────────────────────────────────────

  from robloxmemoryapi_addons.sky import SkyWrapper
  from robloxmemoryapi_addons import wrap_sky

  sky = wrap_sky(sky_instance)
  sky.skybox_back/front/down/left/right/up  → str (Asset ID)
  sky.set_skybox("rbxassetid://123456")    # все грани
  sky.get_all_skybox()                     → dict
  sky.sun_angular_size                     → float
  sky.moon_angular_size                    → float
  sky.sun_texture_id / .moon_texture_id    → str
  sky.star_count                           → int
  sky.skybox_orientation                   → float

── Atmosphere ─────────────────────────────────────────────────

  from robloxmemoryapi_addons import wrap_atmosphere

  atm = wrap_atmosphere(atm_instance)
  atm.density       → float   # плотность
  atm.offset        → float
  atm.color         → Color3
  atm.decay         → float
  atm.glare         → float
  atm.haze          → float

── Post-Processing ────────────────────────────────────────────

  from robloxmemoryapi_addons import wrap_bloom, wrap_dof, wrap_sunrays

  bloom = wrap_bloom(bloom_instance)
  bloom.intensity   → float   r/w
  bloom.size        → float   r/w
  bloom.threshold   → float   r/w
  bloom.enabled     → bool    r/w

  dof = wrap_dof(dof_instance)
  dof.focus_distance      → float  r/w
  dof.far_intensity       → float  r/w
  dof.near_intensity      → float  r/w
  dof.in_focus_radius     → float  r/w
  dof.enabled             → bool   r/w

  sr = wrap_sunrays(sr_instance)
  sr.intensity    → float   r/w
  sr.spread       → float   r/w
  sr.enabled      → bool    r/w

── DragDetector ───────────────────────────────────────────────

  from robloxmemoryapi_addons import wrap_drag_detector

  dd = wrap_drag_detector(dd_instance)
  dd.reference_instance       → RBXInstance|None
  dd.max_activation_distance  → float  r/w
  dd.max_drag_angle           → Vector3 r/w
  dd.min_drag_angle           → Vector3 r/w
  dd.max_drag_translation     → Vector3 r/w
  dd.min_drag_translation     → Vector3 r/w
  dd.max_force                → Vector3 r/w
  dd.max_torque               → Vector3 r/w
  dd.responsiveness           → float   r/w
  dd.cursor_icon              → str     r/w
  dd.activated_cursor_icon    → str     r/w

── ScriptContext ──────────────────────────────────────────────

  from robloxmemoryapi_addons.script_context import ScriptContextWrapper
  from robloxmemoryapi_addons import get_script_context

  sc = get_script_context(memory_module, dm_address)
  sc.address         → int
  sc.require_bypass  → bool   r/w

── PlayerMouse ────────────────────────────────────────────────

  from robloxmemoryapi_addons import wrap_player_mouse

  mouse = wrap_player_mouse(player_instance)
  mouse.is_valid     → bool
  mouse.icon         → str    r/w   # rbxassetid://...
  mouse.workspace    → RBXInstance|None


═══════════════════════════════════════════════════════════════════
 8. ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
═══════════════════════════════════════════════════════════════════

── Пример 1: ESP (World-to-Screen для всех Parts) ────────────

    from robloxmemoryapi import RobloxGameClient
    from robloxmemoryapi_addons import patch_all, get_w2s_helper
    from robloxmemoryapi.utils.rbx.datastructures import Vector3

    client = RobloxGameClient()
    patch_all(client)
    dm = client.DataModel
    w2s = get_w2s_helper(client.memory_module)

    for desc in dm.Workspace.GetDescendants():
        if desc.ClassName in ("Part", "MeshPart"):
            pos = desc.Position
            if isinstance(pos, Vector3):
                screen = w2s.world_to_screen(pos)
                if screen.on_screen:
                    print(f"{desc.Name}: ({screen.x:.0f}, {screen.y:.0f})")

── Пример 2: Снять лимит FPS + читать реальный FPS ─────────

    from robloxmemoryapi_addons import get_task_scheduler, get_run_service

    ts = get_task_scheduler(client.memory_module)
    ts.max_fps = 0     # 0 = безлимит

    dm_addr = get_data_model_address(client.memory_module)
    rs = get_run_service(client.memory_module, dm_addr)
    print(f"FPS: {rs.fps:.1f}")

── Пример 3: Полный контроль над водой ───────────────────────

    terrain = dm.Workspace.FindFirstChild("Terrain")
    if terrain:
        from robloxmemoryapi_addons import wrap_terrain
        t = wrap_terrain(terrain)
        t.water_color = (0, 0.4, 0.8)     # синяя вода
        t.water_transparency = 0.4
        t.water_reflectance = 0.1
        t.water_wave_size = 1.5
        t.water_wave_speed = 10

── Пример 4: Изменить все цвета материалов ───────────────────

    from robloxmemoryapi_addons import wrap_terrain
    terrain = dm.Workspace.FindFirstChild("Terrain")
    if terrain:
        t = wrap_terrain(terrain)
        mc = t.get_material_colors()
        # Всё в серое
        mc.set_all((0.4, 0.4, 0.4))
        # Только трава в зелёное
        mc.grass = (0.2, 0.8, 0.2)

── Пример 5: Управление пост-процессом ──────────────────────

    # Bloom
    bloom = dm.Lighting.FindFirstChildOfClass("BloomEffect")
    if bloom:
        from robloxmemoryapi_addons import wrap_bloom
        b = wrap_bloom(bloom)
        b.intensity = 1.0
        b.size = 50
        b.threshold = 0.8

    # Atmosphere
    atm = dm.Lighting.FindFirstChildOfClass("Atmosphere")
    if atm:
        from robloxmemoryapi_addons import wrap_atmosphere
        a = wrap_atmosphere(atm)
        a.density = 0.3
        a.haze = 2
        a.glare = 1

── Пример 6: Monkey-patch свойства ──────────────────────────

    patch_all(client)  # обязательно!

    # BasePart
    part.CastShadow = False
    part.Material = 256  # Enum.Material.ForceField

    # Lighting
    dm.Lighting.LightColor = (1.0, 0.9, 0.8)
    dm.Lighting.GradientTop = (0.5, 0.7, 1.0)

    # SurfaceAppearance
    sa = dm.Workspace.FindFirstChildOfClass("SurfaceAppearance")
    sa.EmissiveTint = (1, 0, 0)  # красное свечение

    # Post-processing (универсальное)
    bloom.PostEnabled = False  # отключить


═══════════════════════════════════════════════════════════════════
 9. АРХИТЕКТУРА И ВЗАИМОДЕЙСТВИЕ
═══════════════════════════════════════════════════════════════════

  robloxmemoryapi_addons/
  │
  ├── __init__.py          ← Точка входа, patch_all()
  │
  ├── enhanced_instance.py ← Monkey-patch для RBXInstance
  │     └── patch_rbx_instance() — добавляет 22 property
  │
  ├── patch.py             ← Интеграция и хелперы
  │     ├── patch_all()    — вызывает patch_rbx_instance()
  │     ├── get_*()        — фабрики для модулей
  │     └── wrap_*()       — фабрики для wrapper-классов
  │
  ├── task_scheduler.py    ← TaskScheduler (независимый)
  │
  ├── visual_engine.py     ← VisualEngine + W2S (независимый)
  │
  ├── run_service.py       ← RunService (нужен dm address)
  │
  ├── script_context.py    ← ScriptContext (нужен dm address)
  │
  ├── terrain.py           ← Terrain + MaterialColors (нужен instance)
  ├── sky.py               ← Sky (нужен instance)
  ├── atmosphere.py        ← Atmosphere (нужен instance)
  ├── post_processing.py   ← Bloom/DoF/SunRays (нужен instance)
  ├── drag_detector.py     ← DragDetector (нужен instance)
  └── player_mouse.py      ← PlayerMouse (нужен player instance)

Зависимости:
  • enhanced_instance.py ← импортирует RBXInstance и datastructures
  • terrain.py            ← импортирует datastructures (Color3, Vector3)
  • drag_detector.py      ← импортирует RBXInstance, datastructures
  • patch.py              ← импортирует ВСЕ модули
  • Остальные модули      ← независимы (только ctypes/struct)


═══════════════════════════════════════════════════════════════════
 10. ОГРАНИЧЕНИЯ И ЗАМЕЧАНИЯ
═══════════════════════════════════════════════════════════════════

  1. Оффсеты могут устареть при обновлении Roblox.
     Все оффсеты взяты с imtheo.lol/Offsets/Offsets.txt
     и хардкожены в коде. При обновлении Roblox их нужно
     обновить вручную или дождаться обновления на imtheo.lol.

  2. enhanced_instance.py патчит класс RBXInstance через
     monkey-patching (добавляет property). Это безопасно
     только если патч вызывается один раз.
     patch_all() автоматически проверяет это.

  3. Wrapper-классы (TerrainWrapper, SkyWrapper и т.д.)
     принимают RBXInstance и работают через его memory_module.
     ClassName НЕ проверяется внутри — передавайте правильный
     инстанс.

  4. W2SHelper использует ViewMatrix из VisualEngine.
     Матрица хранится column-major и конвертируется
     в row-major для удобства. Это может влиять на точность.

  5. Для записи (setter) необходимо создавать клиент
     с allow_write=True:
       client = RobloxGameClient(allow_write=True)

  6. MaterialColors использует оффсеты MaterialColors::
     от адреса Terrain + MaterialColors offset.
     Формат хранения: 3 × int (RGB, 0-255).

  7. Модуль работает ТОЛЬКО на Windows.

  8. TaskScheduler.get_jobs() читает job linked list.
     Структура списка может отличаться между версиями Roblox.
     Используйте find_job() для поиска по имени.


═══════════════════════════════════════════════════════════════════
 11. СТРУКТУРА ФАЙЛОВ
═══════════════════════════════════════════════════════════════════

  robloxmemoryapi_addons/
  ├── __init__.py              84 строки   Точка входа
  ├── task_scheduler.py        192 строки  TaskScheduler
  ├── visual_engine.py         435 строк   VisualEngine + W2S
  ├── run_service.py           124 строки  RunService
  ├── terrain.py               539 строк  Terrain + MaterialColors
  ├── sky.py                   297 строк  Sky
  ├── atmosphere.py            166 строк  Atmosphere
  ├── post_processing.py       285 строк  Bloom/DoF/SunRays
  ├── drag_detector.py         351 строк  DragDetector
  ├── script_context.py         77 строк  ScriptContext
  ├── player_mouse.py          114 строк  PlayerMouse
  ├── enhanced_instance.py     547 строк  Патч RBXInstance
  ├── patch.py                 206 строк  Интеграция
  ├── examples.py              338 строк  Примеры
  └── README.txt               этот файл

  ИТОГО: 14 файлов, 3755 строк кода (без README и примеров)
