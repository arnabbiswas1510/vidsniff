@echo off
echo [vidsniff setup]

echo.
echo [1/3] Installing Python dependencies + vidsniff command...
pip install -e .
if %errorlevel% neq 0 (
    echo [!] pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

:: Add Python user Scripts dir to PATH permanently if vidsniff isn't found yet
where vidsniff >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [*] Adding Python Scripts directory to PATH...
    for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"') do set "PY_SCRIPTS=%%i"
    if defined PY_SCRIPTS (
        setx PATH "%PY_SCRIPTS%;%PATH%" >nul
        echo [OK] Added: %PY_SCRIPTS%
        echo [!] Please RESTART your terminal for 'vidsniff' to be available on PATH.
    )
) else (
    echo [OK] vidsniff command is already on PATH.
)

echo.
echo [2/3] Installing aria2c (fast multi-connection downloader)...
where aria2c >nul 2>&1
if %errorlevel% equ 0 (
    echo aria2c already installed.
) else (
    echo Trying winget...
    winget install aria2.aria2 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo winget failed. Install aria2c manually:
        echo   https://github.com/aria2/aria2/releases/latest
        echo   Download aria2c.exe and place it on your PATH.
        echo   vidsniff still works without aria2c, just slower.
    ) else (
        echo aria2c installed successfully.
    )
)

echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo  After restarting your terminal, use:
echo    vidsniff "https://youtube.com/watch?v=..."
echo    vidsniff "https://youtu.be/..." -x --audio-format ogg
echo    vidsniff "https://bestjavporn.com/video/some-slug/"
echo.
echo  Or run directly now (without restarting):
echo    python vidsniff.py "URL"
echo.
pause
