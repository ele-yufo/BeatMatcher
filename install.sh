#!/bin/bash

# BeatSaber Downloader 安装脚本
# 适用于 Linux 和 macOS

set -e  # 遇到错误立即退出

echo "==============================================="
echo "       BeatSaber Downloader 安装程序"
echo "==============================================="
echo

# 检查Python版本
check_python() {
    echo "检查Python环境..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "错误: 未找到Python。请先安装Python 3.9或更高版本。"
        exit 1
    fi
    
    # 检查Python版本
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+')
    MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$MAJOR_VERSION" -lt 3 ] || [ "$MAJOR_VERSION" -eq 3 -a "$MINOR_VERSION" -lt 9 ]; then
        echo "错误: Python版本过低 ($PYTHON_VERSION)。需要Python 3.9或更高版本。"
        exit 1
    fi
    
    echo "✓ Python版本: $PYTHON_VERSION (符合要求)"
}

# 检查pip
check_pip() {
    echo "检查pip..."
    
    if command -v pip3 &> /dev/null; then
        PIP_CMD="pip3"
    elif command -v pip &> /dev/null; then
        PIP_CMD="pip"
    else
        echo "错误: 未找到pip。请先安装pip。"
        exit 1
    fi
    
    echo "✓ 找到pip: $PIP_CMD"
}

# 创建虚拟环境（可选）
create_venv() {
    echo
    read -p "是否创建Python虚拟环境？(推荐) [Y/n]: " -r
    echo
    
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "跳过虚拟环境创建"
        return
    fi
    
    VENV_DIR="venv"
    
    echo "创建虚拟环境..."
    $PYTHON_CMD -m venv $VENV_DIR
    
    echo "激活虚拟环境..."
    source $VENV_DIR/bin/activate
    
    # 更新虚拟环境中的pip
    python -m pip install --upgrade pip
    
    echo "✓ 虚拟环境创建完成"
    echo "  激活命令: source $VENV_DIR/bin/activate"
    echo "  停用命令: deactivate"
    echo
}

# 安装依赖
install_dependencies() {
    echo "安装Python依赖包..."
    
    # 检查requirements.txt是否存在
    if [ ! -f "requirements.txt" ]; then
        echo "错误: requirements.txt文件不存在"
        exit 1
    fi
    
    # 安装依赖
    $PIP_CMD install -r requirements.txt
    
    echo "✓ 依赖包安装完成"
}

# 创建配置文件
setup_config() {
    echo
    echo "设置配置文件..."
    
    CONFIG_DIR="config"
    USER_CONFIG="$CONFIG_DIR/my_settings.yaml"
    DEFAULT_CONFIG="$CONFIG_DIR/settings.yaml"
    
    if [ ! -f "$USER_CONFIG" ]; then
        if [ -f "$DEFAULT_CONFIG" ]; then
            cp "$DEFAULT_CONFIG" "$USER_CONFIG"
            echo "✓ 创建用户配置文件: $USER_CONFIG"
        else
            echo "警告: 默认配置文件不存在，跳过配置文件创建"
        fi
    else
        echo "✓ 用户配置文件已存在: $USER_CONFIG"
    fi
}

# 创建桌面快捷方式（Linux）
create_desktop_shortcut() {
    if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v desktop-file-install &> /dev/null; then
        echo
        read -p "是否创建桌面快捷方式？[Y/n]: " -r
        echo
        
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            CURRENT_DIR=$(pwd)
            DESKTOP_FILE="$HOME/.local/share/applications/beatsaber-downloader.desktop"
            
            cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=BeatSaber Downloader
Comment=自动下载本地音乐对应的Beat Saber铺面
Exec=gnome-terminal -- bash -c "cd '$CURRENT_DIR' && python main.py --help; read -p '按Enter键关闭窗口...'"
Icon=$CURRENT_DIR/icon.png
Terminal=false
Type=Application
Categories=AudioVideo;
EOF
            
            chmod +x "$DESKTOP_FILE"
            echo "✓ 桌面快捷方式创建完成"
        fi
    fi
}

# 运行测试
run_tests() {
    echo
    read -p "是否运行测试以验证安装？[Y/n]: " -r
    echo
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo "运行测试..."
        
        if command -v pytest &> /dev/null; then
            pytest tests/ -v
        else
            $PYTHON_CMD -m pytest tests/ -v
        fi
        
        echo "✓ 测试完成"
    fi
}

# 显示使用说明
show_usage() {
    echo
    echo "==============================================="
    echo "             安装完成！"
    echo "==============================================="
    echo
    echo "使用方法:"
    echo "  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps"
    echo
    echo "示例:"
    echo "  python main.py --music-dir ~/Music --output-dir ~/BeatSaber/Beatmaps"
    echo
    echo "更多选项:"
    echo "  python main.py --help"
    echo
    echo "配置文件: config/my_settings.yaml"
    echo "日志文件: logs/beatsaber_downloader.log"
    echo
    
    if [ -d "venv" ]; then
        echo "注意: 如果使用了虚拟环境，请先激活："
        echo "  source venv/bin/activate"
        echo
    fi
    
    echo "项目文档: README.md"
    echo "问题反馈: https://github.com/your-repo/issues"
    echo
}

# 主函数
main() {
    # 检查是否在项目目录中
    if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
        echo "错误: 请在BeatSaber Downloader项目根目录中运行此脚本"
        exit 1
    fi
    
    check_python
    check_pip
    create_venv
    install_dependencies
    setup_config
    create_desktop_shortcut
    run_tests
    show_usage
    
    echo "安装完成！🎉"
}

# 运行主函数
main "$@"