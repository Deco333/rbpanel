"""
Roblox Memory API - Mini GUI Cheat Panel
Использует библиотеку RobloxMemoryAPI для работы с памятью Roblox
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

try:
    from robloxmemoryapi import RobloxGameClient
    from robloxmemoryapi.utils.rbx.datastructures import Vector3
except ImportError:
    print("Ошибка: убедитесь, что RobloxMemoryAPI установлен.")
    print("Установите: pip install -e ./RobloxMemoryAPI")
    exit(1)


class RobloxCheatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Roblox Memory API - Cheat Panel")
        self.root.geometry("500x650")
        self.root.resizable(False, False)

        # Переменные
        self.client = None
        self.game = None
        self.local_player = None
        self.character = None
        self.humanoid = None
        self.root_part = None
        
        # Флаги состояний
        self.fly_enabled = False
        self.noclip_enabled = False
        self.platform_fly_enabled = False
        self.lock_in_enabled = False
        
        # Потоки
        self.fly_thread = None
        self.noclip_thread = None
        self.platform_thread = None
        self.lock_in_thread = None
        self.running = True

        # Создание интерфейса
        self.create_widgets()
        
        # Обработчик закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """Создание всех виджетов GUI"""
        
        # Заголовок
        title_label = tk.Label(self.root, text="Roblox Cheat Panel", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Кнопка подключения
        self.connect_btn = tk.Button(self.root, text="Подключиться к Roblox", command=self.connect_to_roblox, 
                                      bg="#4CAF50", fg="white", font=("Arial", 11))
        self.connect_btn.pack(pady=5)

        self.status_label = tk.Label(self.root, text="Статус: Не подключено", fg="red")
        self.status_label.pack(pady=2)

        # Разделитель
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=10)

        # === Блок основных функций ===
        main_frame = tk.LabelFrame(self.root, text="Основные функции", padx=10, pady=10)
        main_frame.pack(fill='x', padx=10, pady=5)

        # Speed Changer
        speed_frame = tk.Frame(main_frame)
        speed_frame.pack(fill='x', pady=3)
        tk.Label(speed_frame, text="Speed:").pack(side='left')
        self.speed_var = tk.StringVar(value="16")
        self.speed_entry = tk.Entry(speed_frame, textvariable=self.speed_var, width=10)
        self.speed_entry.pack(side='left', padx=5)
        tk.Button(speed_frame, text="Применить", command=self.set_speed, width=8).pack(side='left')

        # JumpPower
        jump_frame = tk.Frame(main_frame)
        jump_frame.pack(fill='x', pady=3)
        tk.Label(jump_frame, text="JumpPower:").pack(side='left')
        self.jump_var = tk.StringVar(value="50")
        self.jump_entry = tk.Entry(jump_frame, textvariable=self.jump_var, width=10)
        self.jump_entry.pack(side='left', padx=5)
        tk.Button(jump_frame, text="Применить", command=self.set_jumppower, width=8).pack(side='left')

        # Teleport to Cursor
        teleport_btn = tk.Button(main_frame, text="Teleport to Cursor", command=self.teleport_to_cursor,
                                  bg="#2196F3", fg="white")
        teleport_btn.pack(fill='x', pady=3)

        # Lock In
        self.lock_in_var = tk.BooleanVar()
        self.lock_in_cb = tk.Checkbutton(main_frame, text="Lock In (Блокировка)", 
                                          variable=self.lock_in_var, command=self.toggle_lock_in)
        self.lock_in_cb.pack(fill='x', pady=3)

        # Разделитель
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=10)

        # === Блок движения ===
        move_frame = tk.LabelFrame(self.root, text="Движение", padx=10, pady=10)
        move_frame.pack(fill='x', padx=10, pady=5)

        # Fly
        self.fly_var = tk.BooleanVar()
        self.fly_cb = tk.Checkbutton(move_frame, text="Fly (Полёт)", 
                                      variable=self.fly_var, command=self.toggle_fly)
        self.fly_cb.pack(fill='x', pady=3)

        # Noclip
        self.noclip_var = tk.BooleanVar()
        self.noclip_cb = tk.Checkbutton(move_frame, text="Noclip (Сквозь стены)", 
                                         variable=self.noclip_var, command=self.toggle_noclip)
        self.noclip_cb.pack(fill='x', pady=3)

        # Platform Fly
        self.platform_var = tk.BooleanVar()
        self.platform_cb = tk.Checkbutton(move_frame, text="Platform Fly", 
                                           variable=self.platform_var, command=self.toggle_platform_fly)
        self.platform_cb.pack(fill='x', pady=3)

        # Разделитель
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=10)

        # === Блок Hitbox ===
        hitbox_frame = tk.LabelFrame(self.root, text="Hitbox Настройки", padx=10, pady=10)
        hitbox_frame.pack(fill='x', padx=10, pady=5)

        # Выбор типа hitbox
        hitbox_type_frame = tk.Frame(hitbox_frame)
        hitbox_type_frame.pack(fill='x', pady=3)
        tk.Label(hitbox_type_frame, text="Тип:").pack(side='left')
        self.hitbox_type = tk.StringVar(value="Player")
        ttk.Radiobutton(hitbox_type_frame, text="Player", variable=self.hitbox_type, 
                        value="Player").pack(side='left', padx=5)
        ttk.Radiobutton(hitbox_type_frame, text="NPC", variable=self.hitbox_type, 
                        value="NPC").pack(side='left', padx=5)

        # Выбор части тела (Scrollable)
        body_part_frame = tk.Frame(hitbox_frame)
        body_part_frame.pack(fill='x', pady=5)
        tk.Label(body_part_frame, text="Часть тела:").pack(side='left')
        
        # Создаём Canvas со скроллбаром для выбора частей тела
        self.body_parts_container = tk.Frame(body_part_frame)
        self.body_parts_container.pack(side='left', fill='x', expand=True, padx=5)
        
        canvas_width = 200
        canvas_height = 60
        
        self.body_canvas = tk.Canvas(self.body_parts_container, width=canvas_width, height=canvas_height,
                                      highlightthickness=0)
        self.body_scrollbar = ttk.Scrollbar(self.body_parts_container, orient="vertical", 
                                             command=self.body_canvas.yview)
        self.body_inner_frame = tk.Frame(self.body_canvas)
        
        self.body_inner_frame.bind(
            "<Configure>",
            lambda e: self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all"))
        )
        
        self.canvas_window = self.body_canvas.create_window((0, 0), window=self.body_inner_frame, anchor="nw")
        self.body_canvas.configure(yscrollcommand=self.body_scrollbar.set)
        
        self.body_canvas.pack(side='left', fill='x', expand=True)
        self.body_scrollbar.pack(side='right', fill='y')
        
        # Части тела для выбора
        self.body_parts = [
            "Head", "UpperTorso", "LowerTorso", "HumanoidRootPart",
            "LeftArm", "RightArm", "LeftLeg", "RightLeg",
            "LeftHand", "RightHand", "LeftFoot", "RightFoot"
        ]
        
        self.body_part_var = tk.StringVar(value="HumanoidRootPart")
        for part in self.body_parts:
            rb = tk.Radiobutton(self.body_inner_frame, text=part, variable=self.body_part_var,
                               value=part, indicatoron=False, width=15, anchor='w')
            rb.pack(fill='x', pady=1)
        
        # Размер хитбокса
        size_frame = tk.Frame(hitbox_frame)
        size_frame.pack(fill='x', pady=3)
        tk.Label(size_frame, text="Размер:").pack(side='left')
        self.hitbox_size_var = tk.StringVar(value="1.0")
        self.hitbox_size_entry = tk.Entry(size_frame, textvariable=self.hitbox_size_var, width=10)
        self.hitbox_size_entry.pack(side='left', padx=5)
        tk.Button(size_frame, text="Применить", command=self.apply_hitbox, width=8).pack(side='left')

        # Разделитель
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=10)

        # === Информационная панель ===
        info_frame = tk.LabelFrame(self.root, text="Информация", padx=10, pady=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        self.info_text = tk.Text(info_frame, height=6, wrap='word', font=("Consolas", 9))
        self.info_text.pack(fill='x', pady=3)
        
        # Кнопка обновления информации
        refresh_btn = tk.Button(info_frame, text="Обновить информацию", command=self.refresh_info)
        refresh_btn.pack(fill='x')

    def connect_to_roblox(self):
        """Подключение к процессу Roblox"""
        try:
            self.client = RobloxGameClient(allow_write=True)
            
            if self.client.failed:
                self.status_label.config(text="Статус: Ошибка подключения", fg="red")
                messagebox.showerror("Ошибка", "Не удалось подключиться к Roblox.\nУбедитесь, что игра запущена.")
                return
            
            self.game = self.client.DataModel
            
            # Проверка, не в главном меню ли
            if self.game.is_lua_app():
                self.status_label.config(text="Статус: Главное меню", fg="orange")
                messagebox.showwarning("Внимание", "Вы находитесь в главном меню Roblox.\nЗапустите игру для использования функций.")
                return
            
            self.local_player = self.game.Players.LocalPlayer
            self.character = self.local_player.Character
            self.humanoid = self.character.Humanoid
            self.root_part = self.character.PrimaryPart
            
            self.status_label.config(text="Статус: Подключено", fg="green")
            self.refresh_info()
            
            messagebox.showinfo("Успех", "Успешно подключено к Roblox!")
            
        except Exception as e:
            self.status_label.config(text="Статус: Ошибка", fg="red")
            messagebox.showerror("Ошибка", f"Ошибка подключения:\n{str(e)}")

    def refresh_info(self):
        """Обновление информации об игре"""
        if not self.game or self.game.is_lua_app():
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, "Нет активной игры")
            return
        
        try:
            info = f"""PlaceID: {self.game.PlaceId}
Игрок: {self.local_player.Name}
Здоровье: {self.character.Humanoid.Health}/{self.character.Humanoid.MaxHealth}
Позиция: {self.root_part.Position if self.root_part else 'N/A'}"""
            
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, info)
        except Exception as e:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"Ошибка получения информации:\n{str(e)}")

    def set_speed(self):
        """Изменение скорости игрока"""
        if not self.humanoid:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            return
        
        try:
            speed = float(self.speed_var.get())
            self.humanoid.WalkSpeed = speed
            messagebox.showinfo("Успех", f"Скорость установлена на {speed}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить скорость:\n{str(e)}")

    def set_jumppower(self):
        """Изменение силы прыжка"""
        if not self.humanoid:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            return
        
        try:
            jumppower = float(self.jump_var.get())
            self.humanoid.JumpPower = jumppower
            messagebox.showinfo("Успех", f"JumpPower установлен на {jumppower}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить JumpPower:\n{str(e)}")

    def get_cursor_position_3d(self):
        """Получение позиции курсора в 3D пространстве"""
        if not self.game:
            return None
        
        try:
            camera = self.game.Workspace.CurrentCamera
            mouse_service = self.game.UserInputService
            
            # Получаем позицию мыши на экране
            # Используем Mouse.Hit для получения позиции в мире
            mouse = self.local_player.Mouse
            if mouse and mouse.Hit:
                return mouse.Hit.Position
            
            return None
        except:
            return None

    def teleport_to_cursor(self):
        """Телепортация к позиции курсора"""
        if not self.root_part:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            return
        
        try:
            cursor_pos = self.get_cursor_position_3d()
            
            if cursor_pos:
                # Телепортируем немного выше позиции курсора
                new_pos = Vector3(cursor_pos.X, cursor_pos.Y + 2, cursor_pos.Z)
                self.root_part.Position = new_pos
                messagebox.showinfo("Успех", "Телепортация выполнена!")
            else:
                messagebox.showwarning("Внимание", "Не удалось получить позицию курсора")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось телепортироваться:\n{str(e)}")

    def toggle_lock_in(self):
        """Включение/выключение Lock In"""
        if not self.character:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            self.lock_in_var.set(False)
            return
        
        if self.lock_in_enabled:
            self.lock_in_enabled = False
            if self.lock_in_thread:
                self.running = False
                self.lock_in_thread = None
        else:
            self.lock_in_enabled = True
            self.running = True
            self.lock_in_thread = threading.Thread(target=self.lock_in_loop, daemon=True)
            self.lock_in_thread.start()

    def lock_in_loop(self):
        """Цикл Lock In - блокировка позиции игрока"""
        if not self.root_part:
            return
        
        original_pos = self.root_part.Position
        
        while self.running and self.lock_in_enabled:
            try:
                if self.root_part:
                    # Возвращаем позицию на место
                    self.root_part.Position = original_pos
                time.sleep(0.05)
            except:
                break

    def toggle_fly(self):
        """Включение/выключение Fly"""
        if not self.character:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            self.fly_var.set(False)
            return
        
        if self.fly_enabled:
            self.fly_enabled = False
            if self.fly_thread:
                self.running = False
                self.fly_thread = None
            # Восстанавливаем гравитацию
            if self.humanoid:
                try:
                    self.humanoid.JumpPower = 50
                except:
                    pass
        else:
            self.fly_enabled = True
            self.running = True
            self.fly_thread = threading.Thread(target=self.fly_loop, daemon=True)
            self.fly_thread.start()
            # Отключаем гравитацию
            if self.humanoid:
                try:
                    self.humanoid.JumpPower = 0
                except:
                    pass

    def fly_loop(self):
        """Цикл Fly - режим полёта"""
        if not self.root_part:
            return
        
        while self.running and self.fly_enabled:
            try:
                # Здесь можно добавить управление полётом
                # Для базовой реализации просто отключаем гравитацию
                time.sleep(0.1)
            except:
                break

    def toggle_noclip(self):
        """Включение/выключение Noclip"""
        if not self.character:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            self.noclip_var.set(False)
            return
        
        if self.noclip_enabled:
            self.noclip_enabled = False
            if self.noclip_thread:
                self.running = False
                self.noclip_thread = None
            # Восстанавливаем CanCollide
            self.set_all_parts_collide(True)
        else:
            self.noclip_enabled = True
            self.running = True
            self.noclip_thread = threading.Thread(target=self.noclip_loop, daemon=True)
            self.noclip_thread.start()
            # Отключаем столкновения
            self.set_all_parts_collide(False)

    def noclip_loop(self):
        """Цикл Noclip - отключение столкновений"""
        while self.running and self.noclip_enabled:
            try:
                self.set_all_parts_collide(False)
                time.sleep(0.1)
            except:
                break

    def set_all_parts_collide(self, collide: bool):
        """Установка CanCollide для всех частей персонажа"""
        if not self.character:
            return
        
        try:
            children = self.character.GetChildren()
            for child in children:
                class_name = child.ClassName.lower()
                if 'part' in class_name or 'mesh' in class_name:
                    try:
                        child.CanCollide = collide
                    except:
                        pass
        except:
            pass

    def toggle_platform_fly(self):
        """Включение/выключение Platform Fly"""
        if not self.game or not self.root_part:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            self.platform_var.set(False)
            return
        
        if self.platform_fly_enabled:
            self.platform_fly_enabled = False
            if self.platform_thread:
                self.running = False
                self.platform_thread = None
            # Удаляем платформу
            try:
                platform = self.game.Workspace.FindFirstChild("CheatPlatform")
                if platform:
                    platform.Parent = None
            except:
                pass
        else:
            self.platform_fly_enabled = True
            self.running = True
            self.platform_thread = threading.Thread(target=self.platform_fly_loop, daemon=True)
            self.platform_thread.start()

    def platform_fly_loop(self):
        """Цикл Platform Fly - создание платформы под игроком"""
        if not self.game or not self.root_part:
            return
        
        platform = None
        
        while self.running and self.platform_fly_enabled:
            try:
                if not self.root_part:
                    time.sleep(0.1)
                    continue
                
                player_pos = self.root_part.Position
                
                # Создаём или обновляем платформу
                if platform is None:
                    # Попытка создать платформу через память
                    # В реальной реализации нужно создавать Part через инъекцию
                    pass
                
                # Перемещаем платформу под игрока
                if platform:
                    platform.Position = Vector3(player_pos.X, player_pos.Y - 5, player_pos.Z)
                
                time.sleep(0.1)
            except:
                break

    def apply_hitbox(self):
        """Применение настроек хитбокса"""
        if not self.game:
            messagebox.showwarning("Внимание", "Сначала подключитесь к игре!")
            return
        
        try:
            target_type = self.hitbox_type.get()
            body_part = self.body_part_var.get()
            size = float(self.hitbox_size_var.get())
            
            if target_type == "Player":
                self.set_player_hitbox(body_part, size)
            else:
                self.set_npc_hitbox(body_part, size)
            
            messagebox.showinfo("Успех", f"Хитбокс применён:\nЧасть: {body_part}\nРазмер: {size}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось применить хитбокс:\n{str(e)}")

    def set_player_hitbox(self, part_name: str, size: float):
        """Установка хитбокса игрока"""
        if not self.character:
            return
        
        try:
            part = self.character.FindFirstChild(part_name)
            if part:
                # Изменяем размер части
                current_size = part.Size
                new_size = Vector3(size, size, size)
                part.Size = new_size
        except:
            pass

    def set_npc_hitbox(self, part_name: str, size: float):
        """Установка хитбокса NPC"""
        if not self.game:
            return
        
        try:
            # Получаем всех NPC в workspace
            npcs = []
            players = self.game.Players.GetPlayers()
            player_names = [p.Name for p in players]
            
            children = self.game.Workspace.GetChildren()
            for child in children:
                if child.ClassName == "Model" and child.Name not in player_names:
                    humanoid = child.FindFirstChild("Humanoid")
                    if humanoid:
                        npcs.append(child)
            
            # Применяем хитбокс ко всем NPC
            for npc in npcs:
                part = npc.FindFirstChild(part_name)
                if part:
                    part.Size = Vector3(size, size, size)
        except:
            pass

    def on_closing(self):
        """Обработчик закрытия окна"""
        self.running = False
        
        # Останавливаем все потоки
        if self.client:
            self.client.close()
        
        self.root.destroy()


def main():
    root = tk.Tk()
    app = RobloxCheatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
