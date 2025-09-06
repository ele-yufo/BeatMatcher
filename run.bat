@echo off
REM BeatSaber Downloader 运行脚本 (Windows)
setlocal EnableDelayedExpansion

REM 初始化变量
set "MUSIC_DIR="
set "OUTPUT_DIR="
set "CONFIG_FILE="
set "MAX_FILES="
set "DRY_RUN="
set "PYTHON_CMD=python"

REM 显示帮助信息
:show_help
echo BeatSaber Downloader 运行脚本
echo.
echo 用法: %~nx0 [选项] ^<音乐目录^> ^<输出目录^>
echo.
echo 参数:
echo   音乐目录    本地音乐文件所在目录
echo   输出目录    下载的铺面保存目录
echo.
echo 选项:
echo   /h, /help        显示此帮助信息
echo   /c, /config      指定配置文件路径 (默认: config\settings.yaml)
echo   /m, /max-files   最大处理文件数 (用于测试)
echo   /d, /dry-run     只搜索和匹配，不下载文件
echo   /t, /test        运行测试模式 (处理前5个文件)
echo.
echo 示例:
echo   %~nx0 C:\Music C:\BeatSaber\Beatmaps
echo   %~nx0 /c config\my_settings.yaml C:\Music C:\BeatSaber\Beatmaps
echo   %~nx0 /t C:\Music C:\BeatSaber\Beatmaps
echo   %~nx0 /dry-run C:\Music C:\BeatSaber\Beatmaps
echo.
goto :eof

REM 检查依赖
:check_dependencies
echo 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python
    exit /b 1
)

if not exist "main.py" (
    echo 错误: main.py不存在，请确保在项目根目录中运行
    exit /b 1
)

REM 检查虚拟环境
if exist "venv" (
    if not defined VIRTUAL_ENV (
        echo 检测到虚拟环境但未激活，正在激活...
        call venv\Scripts\activate.bat
        echo ✓ 虚拟环境已激活
    )
)
goto :eof

REM 验证目录
:validate_directories
if "%MUSIC_DIR%"=="" (
    echo 错误: 请指定音乐目录
    call :show_help
    exit /b 1
)

if "%OUTPUT_DIR%"=="" (
    echo 错误: 请指定输出目录
    call :show_help
    exit /b 1
)

if not exist "%MUSIC_DIR%" (
    echo 错误: 音乐目录不存在: %MUSIC_DIR%
    exit /b 1
)

REM 创建输出目录（如果不存在）
if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
)
echo ✓ 目录验证通过
goto :eof

REM 显示运行信息
:show_run_info
echo ===============================================
echo        BeatSaber Downloader 开始运行
echo ===============================================
echo.
echo 音乐目录: %MUSIC_DIR%
echo 输出目录: %OUTPUT_DIR%

if defined CONFIG_FILE (
    echo 配置文件: %CONFIG_FILE%
)

if defined MAX_FILES (
    echo 最大文件数: %MAX_FILES%
)

if defined DRY_RUN (
    echo 模拟运行模式: 只搜索和匹配，不下载文件
)
echo.
goto :eof

REM 构建Python命令
:build_command
set "CMD=%PYTHON_CMD% main.py --music-dir "%MUSIC_DIR%" --output-dir "%OUTPUT_DIR%""

if defined CONFIG_FILE (
    set "CMD=!CMD! --config "%CONFIG_FILE%""
)

if defined MAX_FILES (
    set "CMD=!CMD! --max-files %MAX_FILES%"
)

if defined DRY_RUN (
    set "CMD=!CMD! --dry-run"
)
goto :eof

REM 主函数
:main
REM 解析参数
:parse_args
if "%1"=="" goto :done_parsing

if /i "%1"=="/h" goto :help_exit
if /i "%1"=="/help" goto :help_exit

if /i "%1"=="/c" (
    set "CONFIG_FILE=%2"
    shift
    shift
    goto :parse_args
)
if /i "%1"=="/config" (
    set "CONFIG_FILE=%2"
    shift
    shift
    goto :parse_args
)

if /i "%1"=="/m" (
    set "MAX_FILES=%2"
    shift
    shift
    goto :parse_args
)
if /i "%1"=="/max-files" (
    set "MAX_FILES=%2"
    shift
    shift
    goto :parse_args
)

if /i "%1"=="/d" (
    set "DRY_RUN=true"
    shift
    goto :parse_args
)
if /i "%1"=="/dry-run" (
    set "DRY_RUN=true"
    shift
    goto :parse_args
)

if /i "%1"=="/t" (
    set "MAX_FILES=5"
    echo 测试模式: 只处理前5个文件
    shift
    goto :parse_args
)
if /i "%1"=="/test" (
    set "MAX_FILES=5"
    echo 测试模式: 只处理前5个文件
    shift
    goto :parse_args
)

REM 位置参数
if "%MUSIC_DIR%"=="" (
    set "MUSIC_DIR=%1"
    shift
    goto :parse_args
)

if "%OUTPUT_DIR%"=="" (
    set "OUTPUT_DIR=%1"
    shift
    goto :parse_args
)

echo 错误: 参数过多
call :show_help
exit /b 1

:help_exit
call :show_help
exit /b 0

:done_parsing

REM 检查依赖和环境
call :check_dependencies
if %errorlevel% neq 0 exit /b %errorlevel%

REM 验证目录
call :validate_directories
if %errorlevel% neq 0 exit /b %errorlevel%

REM 显示运行信息
call :show_run_info

REM 构建并执行Python命令
call :build_command
echo 执行命令: !CMD!
echo.

REM 执行程序
!CMD!

echo.
echo 程序执行完成！
goto :eof

REM 程序入口
call :main %*