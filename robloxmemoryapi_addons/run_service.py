"""
RunService Module — Сервис выполнения Roblox

Позволяет:
  - Читать реальный FPS (HeartbeatFPS)
  - Доступ к HeartbeatTask
"""

import time


# ──────────────────────────────────────────────────────────────
# Offsets
# ──────────────────────────────────────────────────────────────

RUN_SERVICE_OFFSETS = {
    "HeartbeatTask": 0xf0,
    "HeartbeatFPS": 0xb8,
}


class RunServiceWrapper:
    """
    Обёртка над RunService Roblox.

    Предоставляет доступ к FPS и информации о heartbeat.

    Usage:
        rs = RunServiceWrapper(memory_module, data_model_address)
        print(rs.fps)              # текущий FPS
        print(rs.heartbeat_task)   # адрес heartbeat task
    """

    def __init__(self, memory_module, data_model_address: int):
        """
        Args:
            memory_module: EvasiveProcess
            data_model_address: адрес DataModel
        """
        self.mem = memory_module
        self._dm_addr = data_model_address
        self._offsets = RUN_SERVICE_OFFSETS

    @property
    def address(self) -> int:
        return self._dm_addr

    # ── FPS ─────────────────────────────────────────────────

    @property
    def fps(self) -> float:
        """
        Текущий FPS (HeartbeatFPS).

        Returns:
            float: текущий FPS, или 0.0 если недоступен
        """
        try:
            addr = self._dm_addr + self._offsets["HeartbeatFPS"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    # ── HeartbeatTask ───────────────────────────────────────

    @property
    def heartbeat_task(self) -> int:
        """Адрес HeartbeatTask."""
        try:
            addr = self._dm_addr + self._offsets["HeartbeatTask"]
            return self.mem.get_pointer(addr)
        except Exception:
            return 0

    @property
    def is_running(self) -> bool:
        """
        Проверяет, запущен ли RunService (игра загружена).

        Определяется по наличию heartbeat task.
        """
        return self.heartbeat_task != 0

    # ── Вспомогательные методы ──────────────────────────────

    def wait_for_game_load(self, timeout: float = 30.0, interval: float = 0.5) -> bool:
        """
        Ждёт загрузки игры (появления heartbeat task).

        Args:
            timeout: максимальное время ожидания в секундах
            interval: интервал проверки

        Returns:
            bool: загружена ли игра
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_running:
                return True
            time.sleep(interval)
        return False

    def measure_fps(self, samples: int = 10, interval: float = 0.1) -> float:
        """
        Измеряет средний FPS за несколько выборок.

        Args:
            samples: количество выборок
            interval: интервал между выборками

        Returns:
            float: средний FPS
        """
        values = []
        for _ in range(samples):
            f = self.fps
            if f > 0:
                values.append(f)
            time.sleep(interval)
        return sum(values) / len(values) if values else 0.0

    def __repr__(self):
        return f"RunService(fps={self.fps:.1f}, running={self.is_running})"
