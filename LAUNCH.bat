@echo off
echo Starting Roblox Panel v4.0...
echo.

echo [1/2] Starting WebSocket server...
start "Roblox Panel Server" cmd /k "pip install websockets robloxmemoryapi >nul 2>&1 & python server.py"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Next.js frontend...
start "Roblox Panel Frontend" cmd /k "npm install >nul 2>&1 & npm run dev"

echo.
echo Panel starting! Open http://localhost:3000 in your browser.
echo Press any key to exit this launcher.
pause >nul
