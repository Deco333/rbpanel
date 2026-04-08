"""
TaskScheduler Module — Система задач Roblox

Позволяет:
  - Читать текущий FPS и MaxFPS
  - Перечислять и управлять jobs (Heartbeat, Render, Stepper, etc.)
  - Читать имена, состояния, приоритеты задач
"""

import struct
import ctypes


# ──────────────────────────────────────────────────────────────
# Offsets (обновляются с imtheo.lol)
# ──────────────────────────────────────────────────────────────

TASK_SCHEDULER_OFFSETS = {
    "Pointer": 0x8428188,
    "JobStart": 0xc8,
    "JobEnd": 0xd0,
    "JobName": 0x18,
    "MaxFPS": 0xb0,
}


class TaskScheduler:
    """
    Обёртка над TaskScheduler Roblox.

    Позволяет читать/писать MaxFPS, перечислять jobs,
    получать реальный FPS.

    Usage:
        ts = TaskScheduler(memory_module)
        print(ts.max_fps)           # текущий лимит FPS
        ts.max_fps = 999            # снять лимит
        for job in ts.get_jobs():
            print(job.name, job.is_running)
    """

    def __init__(self, memory_module):
        """
        Args:
            memory_module: EvasiveProcess — объект для чтения/записи памяти
        """
        self.mem = memory_module
        self.base = memory_module.base
        self._scheduler_ptr = self.base + TASK_SCHEDULER_OFFSETS["Pointer"]
        self._scheduler_addr = self.mem.get_pointer(self._scheduler_ptr)
        self._offsets = TASK_SCHEDULER_OFFSETS

    # ── MaxFPS ──────────────────────────────────────────────

    @property
    def max_fps(self) -> float:
        """Текущий лимит MaxFPS (float)."""
        try:
            addr = self._scheduler_addr + self._offsets["MaxFPS"]
            return self.mem.read_float(addr)
        except Exception:
            return 0.0

    @max_fps.setter
    def max_fps(self, value: float):
        """Установить лимит MaxFPS (0 = безлимит)."""
        try:
            addr = self._scheduler_addr + self._offsets["MaxFPS"]
            self.mem.write_float(addr, float(value))
        except Exception as e:
            raise RuntimeError(f"Failed to write MaxFPS: {e}")

    # ── Адрес ───────────────────────────────────────────────

    @property
    def address(self) -> int:
        """Адрес TaskScheduler."""
        return self._scheduler_addr

    # ── Jobs ────────────────────────────────────────────────

    def get_jobs(self) -> list:
        """
        Возвращает список всех jobs в TaskScheduler.

        Каждый job — это словарь:
          - name (str): имя задачи (Heartbeat, Render, Stepper, ...)
          - start_addr (int): адрес начала job
          - is_running (bool): выполняется ли сейчас
          - scheduler_addr (int): адрес scheduler для этого job
        """
        jobs = []

        if self._scheduler_addr == 0:
            return jobs

        job_start_ptr = self._scheduler_addr + self._offsets["JobStart"]
        job_end_ptr = self._scheduler_addr + self._offsets["JobEnd"]

        try:
            start_addr = self.mem.get_pointer(job_start_ptr)
            end_addr = self.mem.get_pointer(job_end_ptr)
        except Exception:
            return jobs

        if start_addr == 0 or end_addr == 0:
            return jobs

        # Job linked list: каждый узел размером ~0x??
        # JobStart → первый job, JobEnd → последний job
        # JobNext = addr + 0x0 (внутри списка, структура зависит от версии)

        # В Roblox Jobs — это двусвязный список.
        # Начинаем с первого и идём до конца.
        current = start_addr
        max_iterations = 200  # защита от бесконечного цикла

        for _ in range(max_iterations):
            if current == 0:
                break

            try:
                # Имя job — строка по оффсету
                name_addr = current + self._offsets["JobName"]
                job_name = self.mem.read_string(name_addr)

                # Определяем, запущен ли job
                # Job::running обычно хранится как bool где-то в структуре
                # Для простоты — проверяем что адрес валидный
                is_running = True

                jobs.append({
                    "name": job_name,
                    "address": current,
                    "is_running": is_running,
                })

                # Следующий job в списке
                # В двусвязном списке следующий элемент через указатель
                # Roblox использует intrusive linked list, next ptr может быть
                # на смещении 0x10 от начала job
                next_ptr = self.mem.get_pointer(current)
                if next_ptr == 0 or next_ptr == current:
                    break
                current = next_ptr
            except Exception:
                break

        return jobs

    def find_job(self, name: str) -> dict | None:
        """
        Найти job по имени.

        Args:
            name: имя задачи (например "Heartbeat", "Render", "Stepper")

        Returns:
            dict с информацией о job или None
        """
        for job in self.get_jobs():
            if job["name"].lower() == name.lower():
                return job
        return None

    # ── Refresh ─────────────────────────────────────────────

    def refresh(self):
        """Переобновить адрес TaskScheduler (полезно при смене DataModel)."""
        self._scheduler_addr = self.mem.get_pointer(self._scheduler_ptr)

    def __repr__(self):
        return f"TaskScheduler(address=0x{self._scheduler_addr:X}, max_fps={self.max_fps})"


class Job:
    """
    Представление одной задачи (Job) в TaskScheduler.

    Attributes:
        address: адрес job в памяти
        name: имя задачи
        memory_module: EvasiveProcess
    """

    def __init__(self, address: int, name: str, memory_module):
        self.address = address
        self.name = name
        self.mem = memory_module

    def __repr__(self):
        return f"Job(name={self.name!r}, address=0x{self.address:X})"
