@echo off
echo [vidsniff setup]
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)
echo.
echo [OK] Setup complete!
echo.
echo Usage:
echo   python vidsniff.py "https://youtube.com/watch?v=..."
echo   python vidsniff.py "https://site.com/video/slug/" --domain site.com
echo   python vidsniff.py "https://youtu.be/..." -x --audio-format ogg
echo.
pause
