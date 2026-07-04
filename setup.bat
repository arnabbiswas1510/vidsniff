@echo off
echo [vidsniff setup]

echo.
echo [1/2] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing aria2c (fast multi-connection downloader)...
where aria2c >nul 2>&1
if %errorlevel% equ 0 (
    echo aria2c already installed.
) else (
    echo Trying winget...
    winget install aria2.aria2 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo winget failed. Please install aria2c manually:
        echo   https://github.com/aria2/aria2/releases/latest
        echo   Download aria2c.exe, place it somewhere on your PATH.
        echo.
        echo vidsniff will still work without aria2c, just slower.
    ) else (
        echo aria2c installed successfully.
    )
)

echo.
echo [OK] Setup complete!
echo.
echo Usage:
echo   python vidsniff.py "https://youtube.com/watch?v=..."
echo   python vidsniff.py "https://youtu.be/..." -x --audio-format ogg
echo   python vidsniff.py "https://bestjavporn.com/video/some-slug/"
echo.
pause
