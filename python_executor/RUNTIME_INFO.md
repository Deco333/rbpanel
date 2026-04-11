# 🐍 Python External Executor для Roblox

## ⚠️ Важная информация о работе

### Почему скрипт `print("hello")` не работает?

Вы видите **0 клиентов** в статусе Bridge, потому что:

1. **Python Executor** - это только **внешняя часть** (External)
2. Для работы требуется **DLL инжектор**, который внедряет Lua-скрипт внутрь процесса Roblox
3. Этот Lua-скрипт (Bridge Client) подключается к вашему Python HTTP серверу на порту 6767

```
┌─────────────────┐         HTTP          ┌─────────────────┐
│  Python Executor│ ←────── Port 6767 ──→ │   Bridge DLL    │
│  (Web UI + API) │                       │  (Внутри игры)  │
└─────────────────┘                       └─────────────────┘
        │                                         │
        │                                         ▼
        │                                 ┌─────────────────┐
        └───────────────────────────────→ │   Roblox Game   │
                                          │  (Lua Context)  │
                                          └─────────────────┘
```

### Текущее состояние:
- ✅ Python сервер работает (порт 5000 - UI, порт 6767 - Bridge)
- ✅ Находит процесс Roblox
- ✅ Attach работает
- ❌ **Нет DLL для инъекции** → 0 клиентов → скрипты не выполняются

## 🔧 Что нужно для полной работы

### Вариант 1: Создание DLL инжектора (Windows)
```python
# Требуется создать DLL на C++/C# которая:
1. Внедряется в процесс Roblox через CreateRemoteThread
2. Загружает lua51.dll или использует существующий Lua контекст
3. Выполняет Lua скрипт который соединяется с http://localhost:6767
```

### Вариант 2: Использование готовых решений
- [pyploit](https://github.com/vynnhere/pyploit) - имеет базовый инжектор
- [Synapse X](https://synapse.to/) - коммерческий эксплойт
- [Script-Ware](https://scriptware.com/) - коммерческий эксплойт

### Вариант 3: Симуляция режима (для тестов)
Можно добавить режим симуляции в `injector.py`:
```python
def execute_script(self, source: str) -> bool:
    # В режиме симуляции просто выводим в консоль
    print(f"[SIMULATED] Executing: {source[:100]}...")
    return True
```

## 📁 Структура проекта

```
python_executor/
├── main.py                 # Точка входа
├── requirements.txt        # Зависимости
├── core/
│   ├── memory.py          # Работа с памятью (Windows API)
│   ├── bridge.py          # HTTP сервер (порт 6767)
│   ├── injector.py        # Логика инъекции
│   └── luau.py            # Компиляция Luau bytecode
├── ui/
│   └── app.py             # Flask REST API
├── offsets/
│   └── manager.py         # Оффсеты с imtheo.lol
├── templates/
│   └── index.html         # Web UI
└── static/
    ├── css/style.css      # Стили
    └── js/main.js         # Frontend логика
```

## 🚀 Запуск

```bash
cd python_executor
pip install -r requirements.txt
python main.py
```

Откройте http://localhost:5000

## 🎨 UI Функции

| Кнопка | Описание |
|--------|----------|
| **Attach** | Подключиться к процессу Roblox |
| **Execute** | Отправить скрипт на выполнение |
| **Clear** | Очистить редактор |

## 📊 Статусы Bridge

- **Online (N clients)** - N DLL клиентов подключено
- **Online (0 clients)** - Сервер работает, но DLL не внедрена
- **Offline** - Сервер не запущен

## 🔗 Полезные ссылки

- [Offsets API](https://imtheo.lol/Offsets) - Автоматические оффсеты
- [pyploit](https://github.com/vynnhere/pyploit) - Пример на Python
- [ExternalExecutor](https://github.com/black-loaf2026/ExternalExecutor) - C++ реализация

## ⚡ Требования

- Windows 10/11
- Python 3.8+
- Права администратора (для доступа к памяти)
- Roblox Player запущен

## 🛑 Ограничения текущей версии

1. **Требуется DLL** - без неё скрипты не выполняются
2. **Только Windows** - используется WinAPI для работы с памятью
3. **Anti-Cheat** - Byfron (Hyperion) может блокировать инъекцию

## 💡 Будущие улучшения

- [ ] Создать DLL инжектор на C++
- [ ] Добавить обход Byfron
- [ ] Режим симуляции для тестов
- [ ] Поддержка файловых скриптов
- [ ] Автовосстановление соединения

---

**Примечание**: Этот проект создан в образовательных целях. Используйте ответственно.
