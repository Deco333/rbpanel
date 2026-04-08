"""
Roblox Panel v4.1 — Advanced Overlay Module
Интегрирует GameOverlay с предсказанием движения и авто-оффсетами.

Features:
- Прозрачный Win32 оверлей поверх Roblox (ESP, коробки, линии)
- Предсказание позиции на 0.5 сек вперед с гравитацией
- Автообновление оффсетов с https://imtheo.lol/Offsets
- Исправленный World-to-Screen через VisualEngine addon
- Оптимизированный рендеринг при 240 FPS
"""

import threading
import time
import math
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Импорты из robloxmemoryapi_addons
try:
    from robloxmemoryapi_addons import GameOverlay, VisualEngine, OffsetUpdater
    from robloxmemoryapi_addons.visual_engine import W2SHelper
    HAS_ADDONS = True
except ImportError as e:
    HAS_ADDONS = False
    print(f"[Overlay] Warning: addons not available: {e}")

log = logging.getLogger("overlay_module")

# Константы физики Roblox
ROBLOX_GRAVITY = 196.2  # Студы/сек² (примерно 1.5 * 50 * масштаб)
PREDICTION_TIME = 0.5   # Секунды вперед для предсказания


class Vector3:
    """Простая векторная математика."""
    __slots__ = ('x', 'y', 'z')
    
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z


class PredictionEngine:
    """Расчет будущей позиции с учетом гравитации."""
    
    @staticmethod
    def predict_position(pos: Vector3, vel: Vector3, dt: float = PREDICTION_TIME) -> Vector3:
        """
        Формула: P_new = P_old + V * t + 0.5 * g * t²
        
        Args:
            pos: Текущая позиция (Vector3)
            vel: Текущая скорость (Vector3)
            dt: Время предсказания в секундах
        
        Returns:
            Predicted position (Vector3)
        """
        # Гравитация направлена вниз по оси Y
        gravity_y = -ROBLOX_GRAVITY
        
        pred_x = pos.x + vel.x * dt
        pred_y = pos.y + vel.y * dt + 0.5 * gravity_y * (dt ** 2)
        pred_z = pos.z + vel.z * dt
        
        return Vector3(pred_x, pred_y, pred_z)
    
    @staticmethod
    def predict_with_jump(pos: Vector3, vel: Vector3, is_jumping: bool, dt: float = PREDICTION_TIME) -> Vector3:
        """Предсказание с учетом возможного прыжка."""
        if is_jumping:
            # Добавляем вертикальную скорость прыжка (~50 студ/сек вверх)
            vel = Vector3(vel.x, vel.y + 50.0, vel.z)
        return PredictionEngine.predict_position(pos, vel, dt)


class AdvancedOverlay:
    """
    Продвинутый ESP оверлей с предсказанием.
    
    Интегрируется с server.py через PanelState.
    """
    
    def __init__(self, panel_state):
        self.state = panel_state
        self.overlay = None
        self.running = False
        self.thread = None
        self.last_update = 0
        self.update_interval = 1.0 / 240.0  # 240 FPS target
        
        # Кэш сущностей
        self.entities_cache: List[Dict[str, Any]] = []
        self.local_player_pos = Vector3()
        
        # Настройки визуализации
        self.config = {
            "show_boxes": True,
            "show_lines": True,
            "show_prediction": True,
            "show_health": True,
            "show_distance": True,
            "box_color_enemy": (255, 0, 0),      # Красный
            "box_color_friend": (0, 255, 0),     # Зеленый
            "pred_color": (0, 255, 255),         # Циан
            "line_color": (255, 255, 255),       # Белый
        }
        
        # Offset updater
        self.offset_updater = None
        if HAS_ADDONS:
            try:
                self.offset_updater = OffsetUpdater()
                log.info("[Overlay] OffsetUpdater initialized")
            except Exception as e:
                log.warning(f"[Overlay] OffsetUpdater failed: {e}")
    
    def start(self):
        """Запуск оверлея в отдельном потоке."""
        if not HAS_ADDONS:
            log.error("[Overlay] Cannot start: addons not available")
            return False
        
        if self.running:
            log.warning("[Overlay] Already running")
            return False
        
        # Создаем оверлей
        try:
            self.overlay = GameOverlay(target_fps=240)
            self.overlay.create()
            self.overlay.start()
            
            self.running = True
            self.thread = threading.Thread(target=self._render_loop, daemon=True, name="OverlayThread")
            self.thread.start()
            
            log.info("[Overlay] Started successfully at 240 FPS")
            return True
        except Exception as e:
            log.error(f"[Overlay] Failed to start: {e}")
            return False
    
    def stop(self):
        """Остановка оверлея."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.overlay:
            try:
                self.overlay.stop()
                self.overlay.destroy()
            except:
                pass
        log.info("[Overlay] Stopped")
    
    def update_offsets(self) -> bool:
        """Проверка и применение обновлений оффсетов."""
        if not self.offset_updater:
            return False
        
        try:
            info = self.offset_updater.compare_versions()
            if info.get("is_update_available", False):
                log.info("[Overlay] New offsets available, updating...")
                self.offset_updater.backup_files()
                report = self.offset_updater.apply_updates(dry_run=False)
                log.info(f"[Overlay] Updated {report['total_changes']} values")
                
                # Пересоздаем VisualEngine с новыми оффсетами
                if self.state.client:
                    self.state.visual_engine = VisualEngine(self.state.mem)
                    self.state.w2s = W2SHelper(self.state.visual_engine)
                return True
        except Exception as e:
            log.error(f"[Overlay] Offset update failed: {e}")
        return False
    
    def _render_loop(self):
        """Основной цикл рендеринга."""
        while self.running:
            start_time = time.time()
            
            try:
                # 1. Обновление данных из памяти
                self._update_game_data()
                
                # 2. Подготовка команд отрисовки
                draw_commands = self._prepare_draw_commands()
                
                # 3. Отправка в оверлей
                if self.overlay and draw_commands:
                    self.overlay.update(draw_commands)
                
            except Exception as e:
                log.error(f"[Overlay] Render error: {e}")
            
            # Контроль FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, self.update_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _update_game_data(self):
        """Чтение данных из памяти через memory_api."""
        if not self.state.client or not self.state.w2s:
            self.entities_cache = []
            return
        
        try:
            # Локальный игрок
            local_char = self.state.client.get_local_character()
            if not local_char:
                self.entities_cache = []
                return
            
            # Позиция локального игрока
            root_part = local_char.find_first_child("HumanoidRootPart")
            if not root_part:
                return
            
            hrp_addr = root_part.address
            self.local_player_pos = Vector3(
                self.state.mem.read_float(hrp_addr + 0x10),  # X
                self.state.mem.read_float(hrp_addr + 0x14),  # Y
                self.state.mem.read_float(hrp_addr + 0x18)   # Z
            )
            
            # Получаем список игроков
            players = self.state.client.get_players()
            new_cache = []
            
            for player in players:
                try:
                    name = player.Name
                    char = player.Character
                    if not char or char.address == local_char.address:
                        continue  # Пропускаем себя
                    
                    # Позиция и скорость
                    char_root = char.find_first_child("HumanoidRootPart")
                    if not char_root:
                        continue
                    
                    root_addr = char_root.address
                    
                    # Читаем позицию
                    pos = Vector3(
                        self.state.mem.read_float(root_addr + 0x10),
                        self.state.mem.read_float(root_addr + 0x14),
                        self.state.mem.read_float(root_addr + 0x18)
                    )
                    
                    # Читаем скорость (если доступна)
                    # Обычно смещение velocity = 0x20 от root part или через Humanoid
                    vel = Vector3(0, 0, 0)
                    try:
                        humanoid = char.find_first_child("Humanoid")
                        if humanoid:
                            # Скорость часто хранится в Humanoid
                            # Смещения могут меняться, это примерное
                            vel_offset = 0x1C0  # Примерное смещение Velocity
                            vel = Vector3(
                                self.state.mem.read_float(humanoid.address + vel_offset),
                                self.state.mem.read_float(humanoid.address + vel_offset + 4),
                                self.state.mem.read_float(humanoid.address + vel_offset + 8)
                            )
                    except:
                        pass
                    
                    # Расчет предсказания
                    pred_pos = PredictionEngine.predict_position(pos, vel, PREDICTION_TIME)
                    
                    # Здоровье
                    health = 100
                    max_health = 100
                    try:
                        humanoid = char.find_first_child("Humanoid")
                        if humanoid:
                            health = self.state.mem.read_float(humanoid.address + 0x1C0)
                            max_health = self.state.mem.read_float(humanoid.address + 0x1C4)
                    except:
                        pass
                    
                    # Дистанция
                    dist = math.sqrt(
                        (pos.x - self.local_player_pos.x) ** 2 +
                        (pos.y - self.local_player_pos.y) ** 2 +
                        (pos.z - self.local_player_pos.z) ** 2
                    )
                    
                    new_cache.append({
                        'name': name,
                        'position': pos,
                        'velocity': vel,
                        'pred_pos': pred_pos,
                        'health': health,
                        'max_health': max_health,
                        'distance': dist,
                        'is_enemy': True,  # TODO: проверка команды
                    })
                    
                except Exception as e:
                    continue
            
            self.entities_cache = new_cache
            
        except Exception as e:
            log.error(f"[Overlay] Data update error: {e}")
    
    def _prepare_draw_commands(self) -> List[Dict[str, Any]]:
        """Подготовка команд отрисовки для GameOverlay."""
        commands = []
        
        if not self.state.w2s:
            return commands
        
        center_x, center_y = 960, 540  # Default 1080p, будет обновлено
        
        # Получаем размеры экрана из VisualEngine
        if self.state.visual_engine:
            try:
                dims = self.state.visual_engine.dimensions
                if dims[0] > 0 and dims[1] > 0:
                    center_x = dims[0] / 2
                    center_y = dims[1] / 2
            except:
                pass
        
        for entity in self.entities_cache:
            try:
                # Позиция для отрисовки (предсказанная или реальная)
                target_pos = entity['pred_pos'] if self.config['show_prediction'] else entity['position']
                
                # World to Screen
                screen_pos = self.state.w2s.world_to_screen(tuple(target_pos))
                if not screen_pos or not screen_pos.on_screen:
                    continue
                
                sx, sy = screen_pos.x, screen_pos.y
                dist = entity['distance']
                
                # Размер коробки зависит от дистанции
                box_size = max(10, 3000 / (dist + 1))
                box_height = box_size * 1.8
                
                # Цвет
                color = self.config['box_color_enemy'] if entity['is_enemy'] else self.config['box_color_friend']
                
                # 1. Коробка
                if self.config['show_boxes']:
                    # Top-left и bottom-right для прямоугольника
                    x1 = sx - box_size / 2
                    y1 = sy - box_height / 2
                    x2 = sx + box_size / 2
                    y2 = sy + box_height / 2
                    
                    commands.append({
                        "type": "rect",
                        "x1": int(x1), "y1": int(y1),
                        "x2": int(x2), "y2": int(y2),
                        "color": color,
                        "filled": False,
                        "thickness": 2
                    })
                
                # 2. Линия от центра
                if self.config['show_lines']:
                    commands.append({
                        "type": "line",
                        "x1": int(center_x), "y1": int(center_y),
                        "x2": int(sx), "y2": int(sy),
                        "color": self.config['line_color'],
                        "thickness": 1
                    })
                
                # 3. Маркер предсказания
                if self.config['show_prediction']:
                    pred_screen = self.state.w2s.world_to_screen(tuple(entity['pred_pos']))
                    if pred_screen and pred_screen.on_screen:
                        px, py = pred_screen.x, pred_screen.y
                        commands.append({
                            "type": "circle",
                            "x": int(px), "y": int(py),
                            "r": 4,
                            "color": self.config['pred_color'],
                            "filled": True
                        })
                        # Линия от реальной позиции к предсказанной
                        commands.append({
                            "type": "line",
                            "x1": int(sx), "y1": int(sy),
                            "x2": int(px), "y2": int(py),
                            "color": self.config['pred_color'],
                            "thickness": 1,
                            "dash": True
                        })
                
                # 4. Текст (имя, здоровье, дистанция)
                if self.config['show_health'] or self.config['show_distance']:
                    text_parts = []
                    if self.config['show_health']:
                        text_parts.append(f"{int(entity['health'])}/{int(entity['max_health'])}")
                    if self.config['show_distance']:
                        text_parts.append(f"{int(dist)}m")
                    
                    info_text = f"{entity['name']} [{', '.join(text_parts)}]"
                    commands.append({
                        "type": "text",
                        "x": int(sx - 50),
                        "y": int(y1 - 5),
                        "text": info_text,
                        "color": (255, 255, 255),
                        "font_size": 12
                    })
                
            except Exception as e:
                continue
        
        return commands


# Singleton instance
_overlay_instance: Optional[AdvancedOverlay] = None


def get_overlay(panel_state) -> AdvancedOverlay:
    """Получить или создать экземпляр оверлея."""
    global _overlay_instance
    if _overlay_instance is None:
        _overlay_instance = AdvancedOverlay(panel_state)
    return _overlay_instance


def start_overlay(panel_state) -> bool:
    """Удобная функция для запуска оверлея из server.py."""
    overlay = get_overlay(panel_state)
    return overlay.start()


def stop_overlay():
    """Остановка оверлея."""
    global _overlay_instance
    if _overlay_instance:
        _overlay_instance.stop()
        _overlay_instance = None
