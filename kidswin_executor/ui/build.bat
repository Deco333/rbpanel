@echo off
echo Building KidsWinUI...
dotnet build --configuration Release
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful!
    echo Output: bin\Release\net6.0-windows\
) else (
    echo.
    echo Build failed!
)
pause
