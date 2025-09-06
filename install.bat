@echo off
REM BeatSaber Downloader 安装脚本 (Windows)

setlocal EnableDelayedExpansion

echo ===============================================
echo        BeatSaber Downloader 安装程序
echo ===============================================
echo.

REM 检查Python
echo 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python。请先安装Python 3.9或更高版本。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python版本: %PYTHON_VERSION%

REM 检查pip
echo 检查pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: pip不可用。请重新安装Python并确保包含pip。
    pause
    exit /b 1
)
echo ✓ pip可用

REM 询问是否创建虚拟环境
echo.
set /p "CREATE_VENV=是否创建Python虚拟环境？(推荐) [Y/n]: "
if /i "%CREATE_VENV%" neq "n" (
    echo 创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo 错误: 虚拟环境创建失败
        pause
        exit /b 1
    )
    
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
    
    REM 更新pip
    python -m pip install --upgrade pip
    
    echo ✓ 虚拟环境创建完成
    echo   激活命令: venv\Scripts\activate.bat
    echo   停用命令: deactivate
    echo.
)

REM 安装依赖
echo 安装Python依赖包...
if not exist "requirements.txt" (
    echo 错误: requirements.txt文件不存在
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 错误: 依赖包安装失败
    pause
    exit /b 1
)
echo ✓ 依赖包安装完成

REM 创建配置文件
echo.
echo 设置配置文件...
if not exist "config\my_settings.yaml" (
    if exist "config\settings.yaml" (
        copy "config\settings.yaml" "config\my_settings.yaml" >nul
        echo ✓ 创建用户配置文件: config\my_settings.yaml
    ) else (
        echo 警告: 默认配置文件不存在，跳过配置文件创建
    )
) else (
    echo ✓ 用户配置文件已存在: config\my_settings.yaml
)

REM 创建桌面快捷方式
echo.
set /p "CREATE_SHORTCUT=是否创建桌面快捷方式？[Y/n]: "
if /i "%CREATE_SHORTCUT%" neq "n" (
    set "CURRENT_DIR=%CD%"
    set "DESKTOP=%USERPROFILE%\Desktop"
    set "SHORTCUT_PATH=%DESKTOP%\BeatSaber Downloader.bat"
    
    echo @echo off > "%SHORTCUT_PATH%"
    echo cd /d "%CURRENT_DIR%" >> "%SHORTCUT_PATH%"
    echo python main.py --help >> "%SHORTCUT_PATH%"
    echo echo. >> "%SHORTCUT_PATH%"
    echo pause >> "%SHORTCUT_PATH%"
    
    echo ✓ 桌面快捷方式创建完成
)

REM 运行测试
echo.
set /p "RUN_TESTS=是否运行测试以验证安装？[Y/n]: "
if /i "%RUN_TESTS%" neq "n" (
    echo 运行测试...
    python -m pytest tests\ -v
    if %errorlevel% equ 0 (
        echo ✓ 测试完成
    ) else (
        echo 警告: 部分测试失败，但安装可能仍然成功
    )
)

REM 显示使用说明
echo.
echo ===============================================
echo              安装完成！
echo ===============================================
echo.
echo 使用方法:
echo   python main.py --music-dir C:\path\to\music --output-dir C:\path\to\beatmaps
echo.
echo 示例:
echo   python main.py --music-dir C:\Users\%USERNAME%\Music --output-dir C:\BeatSaber\Beatmaps
echo.
echo 更多选项:
echo   python main.py --help
echo.
echo 配置文件: config\my_settings.yaml
echo 日志文件: logs\beatsaber_downloader.log
echo.

if exist "venv" (
    echo 注意: 如果使用了虚拟环境，请先激活：
    echo   venv\Scripts\activate.bat
    echo.
)

echo 项目文档: README.md
echo.
echo 安装完成！🎉
pause