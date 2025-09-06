@echo off
REM BeatMatcher Windows Dependencies Installation Script
REM This script handles encoding issues on Windows

echo ===============================================
echo    BeatMatcher - Windows Dependencies Setup
echo ===============================================
echo.

REM Set UTF-8 encoding
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

echo Installing Python dependencies for BeatMatcher...
echo.

REM Upgrade pip first
echo [1/2] Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo Warning: pip upgrade failed, continuing with current version
)

REM Install dependencies individually to avoid encoding issues
echo [2/2] Installing dependencies...
echo.

REM Core dependencies
echo Installing core dependencies...
pip install mutagen>=1.47.0
pip install httpx>=0.25.0
pip install aiohttp>=3.9.0
pip install fuzzywuzzy>=0.18.0
pip install python-Levenshtein>=0.25.0
pip install pydantic>=2.5.0
pip install loguru>=0.7.0
pip install PyYAML>=6.0
pip install aiofiles>=23.0.0
pip install orjson>=3.9.0
pip install tqdm>=4.66.0

REM Optional dependencies for audio processing
echo Installing audio processing dependencies...
pip install librosa>=0.10.0

REM Development dependencies (optional)
echo Installing development dependencies...
pip install pytest>=7.4.0
pip install pytest-asyncio>=0.23.0
pip install pytest-cov>=4.1.0
pip install mypy>=1.7.0
pip install black>=23.0.0
pip install isort>=5.13.0
pip install bandit>=1.7.0

echo.
echo ===============================================
echo         Installation completed!
echo ===============================================
echo.
echo You can now run BeatMatcher:
echo   python main.py --help
echo.
pause