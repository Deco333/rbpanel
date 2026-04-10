# Python External Executor for Roblox

A fully Python-based external Level 8 executor for Roblox with a modern web UI.

## Features

- **Pure Python Implementation**: Core functionality written entirely in Python
- **Modern Web UI**: Clean interface with Attach, Execute, and Clear buttons
- **Luau Bytecode Support**: Compile and execute Luau scripts
- **Memory Reading/Writing**: Direct process memory manipulation
- **HTTP Bridge**: Communication between executor and injected script
- **Dynamic Offsets**: Fetch latest offsets from imtheo.lol API

## Project Structure

```
python_executor/
├── core/
│   ├── __init__.py
│   ├── memory.py          # Memory reading/writing utilities
│   ├── luau.py            # Luau bytecode compilation
│   ├── bridge.py          # HTTP bridge server
│   └── injector.py        # Process attachment and injection
├── ui/
│   ├── __init__.py
│   └── app.py             # Flask/FastAPI web server
├── offsets/
│   ├── __init__.py
│   └── manager.py         # Offset management and updates
├── static/
│   ├── css/
│   │   └── style.css      # UI styling
│   └── js/
│       └── main.js        # Frontend logic
├── templates/
│   └── index.html         # Main UI template
├── requirements.txt       # Python dependencies
└── main.py                # Application entry point
```

## Requirements

- Windows OS (for process memory access)
- Python 3.8+
- Admin privileges (for process attachment)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the executor:
```bash
python main.py
```

3. Open browser to `http://localhost:5000`

## Usage

1. Click **Attach** to connect to Roblox process
2. Paste your Lua script in the editor
3. Click **Execute** to run the script
4. Click **Clear** to reset the editor

## Credits

Based on research from:
- External-Executor-Dependencies
- ExternalExecutor
- pyploit
- imtheo.lol Offsets

## License

MIT License
