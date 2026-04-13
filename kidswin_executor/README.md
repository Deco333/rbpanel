# KidsWin External Executor

A highly stable and undetected external Roblox executor targeting 89% UNC score compatibility.

## Architecture

```
┌─────────────┐     P/Invoke      ┌──────────────────┐    External Memory    ┌──────────────┐
│  KidsWinUI    │ ◄──────────────► │  KidsWinAPI.dll   │ ◄──────────────────► │   Roblox     │
│  (C# WPF)   │  RblxCore.cs     │  (exports.cpp)   │  Read/WriteMemory    │  Process     │
│              │                  │                  │                      │              │
│  Attach btn  │─► Connect(pid)──►│  1. OpenProcess   │                      │              │
│  Execute btn │─► ExecuteScript()│  2. Find DataModel│                      │              │
│              │                  │  3. SpoofWith     │──► Hijack Module ──► │ Init Script  │
│              │                  │  4. HTTP Server   │◄── /poll ──────────► │ Lua Worker   │
└─────────────┘                  └──────────────────┘                      └──────────────┘
```

## Key Features

- **External Execution**: No DLL injection into Roblox. The C++ DLL is loaded by the UI process only.
- **SpoofWith Technique**: Hijacks unloaded ModuleScripts with test/jest/spec/story names
- **HTTP Polling**: Lua worker polls local HTTP server (127.0.0.1:9753) for scripts
- **UNC Sandbox**: Full UNC API implementation (loadstring, request, getgenv, etc.)
- **Syscall Support**: Optional direct syscalls via Nt* functions for stealth
- **Memory Restoration**: Automatically restores all modified memory on disconnect

## Building the C++ DLL

### Prerequisites

- Windows 10/11
- Visual Studio 2019+ with C++ desktop development
- CMake 3.15+
- cpp-httplib (download to `src/third_party/`)

### Build Steps

```bash
cd kidswin_executor
mkdir build && cd build
cmake .. -G "Visual Studio 16 2019" -A x64
cmake --build . --config Release
# Output: bin/KidsWinAPI.dll
```

## Building the UI

### Prerequisites

- **.NET 6.0 SDK** or later: https://dotnet.microsoft.com/download

### Build Steps

```bash
cd kidswin_executor/ui
dotnet build --configuration Release
```

Or use the included batch file on Windows:

```bat
build.bat
```

### Setup

1. Build `KidsWinAPI.dll` from the C++ project first
2. Copy `KidsWinAPI.dll` to `ui/bin/Release/net6.0-windows/`
3. Run `KidsWinUI.exe`

## Usage

1. **Start Roblox** and join any game
2. **Run KidsWinUI.exe** (as Administrator)
3. Click **📎 Attach** to connect to Roblox
4. Write or load your Lua script in the editor
5. Click **▶ Execute** to run the script

## File Structure

```
kidswin_executor/
├── CMakeLists.txt          # Build configuration
├── README.md               # This file
├── include/
│   ├── offsets.h           # Roblox memory offsets
│   ├── unc_payload.h       # Embedded Lua UNC sandbox
│   ├── http_server.h       # C++ HTTP server header
│   └── exports.h           # C API for P/Invoke
├── src/
│   ├── executor.h          # Core execution engine
│   ├── exports.cpp         # Native API implementation
│   ├── memory/
│   │   └── instance_walker.h  # Roblox instance navigation
│   ├── process/
│   │   └── scanner.h       # Process enumeration
│   ├── syscalls/
│   │   ├── syscall_resolver.h  # Nt* syscall resolver
│   │   └── winhttp_client.h    # HTTP client for proxy
│   └── third_party/        # External dependencies
├── ui/                     # C# WPF UI (KidsWinUI)
│   ├── KidsWinUI.csproj    # .NET 6 project file
│   ├── MainWindow.xaml     # Main window UI definition
│   ├── MainWindow.xaml.cs  # Main window logic
│   ├── RblxCore.cs         # P/Invoke bridge
│   ├── App.xaml            # Application resources
│   ├── app.manifest        # Admin privileges manifest
│   └── build.bat           # Windows build script
└── bin/                    # Compiled DLL output
```

## UNC API Support

| Function | Description |
|----------|-------------|
| `loadstring(content)` | Compile and execute Lua code |
| `request(options)` | HTTP request with full options |
| `httpget(url)` | Simple HTTP GET wrapper |
| `getgenv()` | Get global environment |
| `getrenv()` | Get roblox environment |
| `gethui()` | Get hidden UI (PlayerGui-based) |
| `identifyexecutor()` | Returns "KidsWin" |
| `getidentity()` | Returns 8 (CoreScript) |

## Anti-Detection Features

1. **No Injection**: DLL runs externally, never injected into Roblox
2. **Test Modules Only**: Only hijacks modules with jest/test/spec/story names
3. **Immediate Restore**: SpoofTarget pointer restored within milliseconds
4. **Validation Checks**: Only restore if instance still valid (teleport-safe)
5. **Syscall Option**: Direct Nt* syscalls avoid hooked Win32 APIs
6. **RequestInternal**: Uses CoreScript-only HTTP API (no logging)

## Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| -1 | Not connected |
| -2 | DataModel destroyed (teleport) |
| -3 | Execution failed |

## Troubleshooting

### "Failed to initialize KidsWin API"
- Make sure `KidsWinAPI.dll` is in the same directory as `KidsWinUI.exe`
- Ensure the DLL was built for x64 architecture

### "No Roblox process found"
- Start Roblox and join a game first
- Make sure you're running the executor as Administrator

### "Failed to connect to Roblox"
- Check if your antivirus is blocking the DLL
- Try restarting Roblox and the executor

## License

Educational purposes only. Use at your own risk.
