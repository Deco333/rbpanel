# 🎮 Roblox External Executor

A fully functional external executor for Roblox written in Python and C++.

## ⚠️ Disclaimer
This project is for educational purposes only. Use at your own risk. Violating Roblox Terms of Service may result in account termination.

## 📁 Project Structure

```
roblox_executor/
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── CMakeLists.txt          # C++ build configuration
├── README.md               # This file
│
├── core/
│   ├── memory.py           # Windows memory operations
│   ├── bridge.py           # Internal HTTP bridge server
│   ├── injector.py         # DLL injection logic
│   └── luau.py             # Luau bytecode compiler (TODO)
│
├── ui/
│   └── app.py              # Flask web UI server
│
├── offsets/
│   └── manager.py          # Offsets from imtheo.lol
│
├── dll_src/
│   └── bridge.cpp          # C++ bridge DLL source
│
├── bin/                    # Compiled binaries (DLL/PYD)
│
├── templates/
│   └── index.html          # Web UI HTML
│
└── static/
    ├── css/style.css       # Dark theme styles
    └── js/main.js          # Frontend JavaScript
```

## 🚀 Features

- **Web-based UI** - Modern dark theme interface
- **Process Detection** - Auto-find Roblox processes
- **Attach/Detach** - Connect to Roblox process
- **DLL Injection** - Inject bridge DLL for real execution
- **Script Editor** - Write and execute Lua scripts
- **Output Console** - View script output and logs
- **Simulation Mode** - Test scripts without injection
- **Auto Offsets** - Fetch latest offsets from imtheo.lol

## 📋 Requirements

### Python Dependencies
```bash
pip install flask requests psutil
# On Windows: pip install pywin32
```

### For DLL Compilation (Windows)
- Visual Studio 2019+ with C++ workload
- CMake 3.15+
- Windows SDK

## 🔧 Installation

### 1. Install Python Dependencies
```bash
cd roblox_executor
pip install -r requirements.txt
```

### 2. Compile Bridge DLL (Windows Only)

#### Option A: Using CMake
```bash
mkdir build && cd build
cmake .. -G "Visual Studio 16 2019" -A x64
cmake --build . --config Release
copy Release\bridge.dll ../bin/
```

#### Option B: Using Visual Studio
1. Open `dll_src/bridge.cpp` in Visual Studio
2. Create new DLL project
3. Add the code and compile as x64 Release
4. Copy resulting DLL to `bin/bridge.dll`

#### Option C: Pre-compiled DLL
Download pre-compiled `bridge.dll` from releases (if available).

## 🎯 Usage

### Start the Executor
```bash
python main.py
```

### Access the UI
Open http://localhost:5000 in your browser

### Steps:
1. Click **🔄 Refresh** to find Roblox processes
2. Select a process from dropdown
3. Click **📎 Attach** to connect
4. (Optional) Click **💉 Inject DLL** for real execution
5. Write Lua script in editor
6. Click **▶ Execute** or press `Ctrl+Enter`
7. View output in console

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/processes` | GET | List Roblox processes |
| `/api/attach` | POST | Attach to process |
| `/api/detach` | POST | Detach from process |
| `/api/inject` | POST | Inject bridge DLL |
| `/api/execute` | POST | Execute Lua script |
| `/api/clear` | POST | Clear output buffer |
| `/api/status` | GET | Get executor status |
| `/api/output` | GET | Get output buffer |

## 🏗️ Architecture

```
┌─────────────────┐     HTTP      ┌─────────────────┐
│   Web Browser   │ ◄──────────► │   Python UI     │
│  (localhost:5k) │               │  Server (Flask) │
└─────────────────┘               └────────┬────────┘
                                           │
                              ┌────────────┼────────────┐
                              │            │            │
                              ▼            ▼            ▼
                       ┌──────────┐ ┌──────────┐ ┌──────────┐
                       │ Injector │ │ Memory   │ │ Offsets  │
                       │ (WinAPI) │ │ Reader   │ │ Manager  │
                       └──────────┘ └──────────┘ └──────────┘
                                           │
                              (DLL Injection)
                                           │
                              ┌────────────▼────────────┐
                              │   Roblox Process        │
                              │  ┌─────────────────┐    │
                              │  │ Bridge DLL      │    │
                              │  │ (HTTP Server)   │    │
                              │  │ Port: 6768      │    │
                              │  └─────────────────┘    │
                              └─────────────────────────┘
```

## 🛠️ Building for Production

### Create PYD from DLL (Optional)
```bash
# Rename bridge.dll to bridge.pyd
# Place in core/ directory
# Import directly in Python
```

### Update Offsets
Offsets are automatically fetched from https://imtheo.lol/api/offsets
Manual update: Edit `offsets/manager.py` default values.

## ⚡ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Execute script |

## 📝 Example Scripts

### Hello World
```lua
print("Hello from Roblox!")
```

### Speed Hack
```lua
local player = game.Players.LocalPlayer
player.Character.Humanoid.WalkSpeed = 50
```

### Teleport
```lua
local player = game.Players.LocalPlayer
player.Character.HumanoidRootPart.CFrame = CFrame.new(0, 100, 0)
```

## 🐛 Troubleshooting

### "No Roblox processes found"
- Make sure Roblox is running
- Run executor as Administrator

### "Injection failed"
- Disable antivirus temporarily
- Run as Administrator
- Ensure DLL is in `bin/bridge.dll`

### "Bridge offline" after injection
- Wait 2-3 seconds after injection
- Check firewall settings
- Verify port 6768 is not blocked

## 📚 References

- [External Executor Dependencies](https://github.com/M0onzyz/External-Executor-Dependencies)
- [ExternalExecutor](https://github.com/black-loaf2026/ExternalExecutor)
- [pyploit](https://github.com/vynnhere/pyploit)
- [Offsets API](https://imtheo.lol/Offsets)

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please read contributing guidelines first.

---

**Made with ❤️ using Python & C++**
