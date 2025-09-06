#!/bin/bash

# BeatSaber Downloader 运行脚本
# 简化的运行接口

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo "BeatSaber Downloader 运行脚本"
    echo
    echo "用法: $0 [选项] <音乐目录> <输出目录>"
    echo
    echo "参数:"
    echo "  音乐目录    本地音乐文件所在目录"
    echo "  输出目录    下载的铺面保存目录"
    echo
    echo "选项:"
    echo "  -h, --help        显示此帮助信息"
    echo "  -c, --config      指定配置文件路径 (默认: config/settings.yaml)"
    echo "  -m, --max-files   最大处理文件数 (用于测试)"
    echo "  -d, --dry-run     只搜索和匹配，不下载文件"
    echo "  -t, --test        运行测试模式 (处理前5个文件)"
    echo
    echo "示例:"
    echo "  $0 ~/Music ~/BeatSaber/Beatmaps"
    echo "  $0 -c config/my_settings.yaml ~/Music ~/BeatSaber/Beatmaps"
    echo "  $0 -t ~/Music ~/BeatSaber/Beatmaps"
    echo "  $0 --dry-run ~/Music ~/BeatSaber/Beatmaps"
    echo
}

# 检查依赖
check_dependencies() {
    # 检查Python
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        echo -e "${RED}错误: 未找到Python${NC}"
        exit 1
    fi
    
    # 检查main.py
    if [ ! -f "main.py" ]; then
        echo -e "${RED}错误: main.py不存在，请确保在项目根目录中运行${NC}"
        exit 1
    fi
    
    # 检查虚拟环境
    if [ -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${YELLOW}检测到虚拟环境但未激活，正在激活...${NC}"
        source venv/bin/activate
        echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
    fi
}

# 验证目录
validate_directories() {
    local music_dir="$1"
    local output_dir="$2"
    
    if [ -z "$music_dir" ] || [ -z "$output_dir" ]; then
        echo -e "${RED}错误: 请指定音乐目录和输出目录${NC}"
        show_help
        exit 1
    fi
    
    if [ ! -d "$music_dir" ]; then
        echo -e "${RED}错误: 音乐目录不存在: $music_dir${NC}"
        exit 1
    fi
    
    # 创建输出目录（如果不存在）
    mkdir -p "$output_dir"
    echo -e "${GREEN}✓ 目录验证通过${NC}"
}

# 构建Python命令
build_python_command() {
    local music_dir="$1"
    local output_dir="$2"
    
    # 确定Python命令
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi
    
    # 构建基础命令
    CMD="$PYTHON_CMD main.py --music-dir \"$music_dir\" --output-dir \"$output_dir\""
    
    # 添加可选参数
    if [ -n "$CONFIG_FILE" ]; then
        CMD="$CMD --config \"$CONFIG_FILE\""
    fi
    
    if [ -n "$MAX_FILES" ]; then
        CMD="$CMD --max-files $MAX_FILES"
    fi
    
    if [ "$DRY_RUN" = "true" ]; then
        CMD="$CMD --dry-run"
    fi
    
    echo "$CMD"
}

# 显示运行信息
show_run_info() {
    echo -e "${BLUE}===============================================${NC}"
    echo -e "${BLUE}       BeatSaber Downloader 开始运行${NC}"
    echo -e "${BLUE}===============================================${NC}"
    echo
    echo -e "${GREEN}音乐目录:${NC} $1"
    echo -e "${GREEN}输出目录:${NC} $2"
    
    if [ -n "$CONFIG_FILE" ]; then
        echo -e "${GREEN}配置文件:${NC} $CONFIG_FILE"
    fi
    
    if [ -n "$MAX_FILES" ]; then
        echo -e "${GREEN}最大文件数:${NC} $MAX_FILES"
    fi
    
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}模拟运行模式:${NC} 只搜索和匹配，不下载文件"
    fi
    
    echo
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -m|--max-files)
                MAX_FILES="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            -t|--test)
                MAX_FILES="5"
                echo -e "${YELLOW}测试模式: 只处理前5个文件${NC}"
                shift
                ;;
            -*)
                echo -e "${RED}错误: 未知选项 $1${NC}"
                show_help
                exit 1
                ;;
            *)
                if [ -z "$MUSIC_DIR" ]; then
                    MUSIC_DIR="$1"
                elif [ -z "$OUTPUT_DIR" ]; then
                    OUTPUT_DIR="$1"
                else
                    echo -e "${RED}错误: 参数过多${NC}"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # 检查必需参数
    if [ -z "$MUSIC_DIR" ] || [ -z "$OUTPUT_DIR" ]; then
        echo -e "${RED}错误: 请指定音乐目录和输出目录${NC}"
        show_help
        exit 1
    fi
    
    # 检查依赖和环境
    check_dependencies
    
    # 验证目录
    validate_directories "$MUSIC_DIR" "$OUTPUT_DIR"
    
    # 显示运行信息
    show_run_info "$MUSIC_DIR" "$OUTPUT_DIR"
    
    # 构建并执行Python命令
    CMD=$(build_python_command "$MUSIC_DIR" "$OUTPUT_DIR")
    echo -e "${BLUE}执行命令:${NC} $CMD"
    echo
    
    # 执行程序
    eval $CMD
    
    echo
    echo -e "${GREEN}程序执行完成！${NC}"
}

# 捕获Ctrl+C
trap 'echo -e "\n${YELLOW}程序被用户中断${NC}"; exit 130' INT

# 运行主函数
main "$@"