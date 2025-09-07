#!/usr/bin/env python3
"""
重复谱面清理工具
用于清理已下载的重复谱面文件夹
"""

import sys
from pathlib import Path
from collections import defaultdict
import argparse
from loguru import logger


def find_duplicate_beatmaps(directory: Path) -> dict:
    """查找重复的谱面文件夹
    
    Args:
        directory: 要搜索的目录
        
    Returns:
        dict: 重复谱面的分组，键为谱面ID，值为路径列表
    """
    beatmap_groups = defaultdict(list)
    
    # 递归搜索所有文件夹
    for item in directory.rglob("*"):
        if not item.is_dir():
            continue
            
        # 提取谱面ID（文件夹名开头的数字+字母组合）
        name = item.name
        # 匹配类似 "15169_", "7345_" 的模式
        if "_" in name:
            potential_id = name.split("_")[0]
            # 检查是否是谱面ID格式（数字+字母）
            if potential_id and (potential_id.isdigit() or any(c.isalpha() for c in potential_id[-3:])):
                beatmap_groups[potential_id].append(item)
    
    # 只返回有重复的
    duplicates = {bid: paths for bid, paths in beatmap_groups.items() if len(paths) > 1}
    return duplicates


def cleanup_duplicates(duplicates: dict, dry_run: bool = True) -> None:
    """清理重复文件
    
    Args:
        duplicates: 重复文件分组
        dry_run: 是否只是预览，不实际删除
    """
    total_duplicates = 0
    total_size_saved = 0
    
    logger.info(f"发现 {len(duplicates)} 个谱面存在重复")
    
    for beatmap_id, paths in duplicates.items():
        logger.info(f"\n谱面 {beatmap_id} 有 {len(paths)} 个重复:")
        
        # 按修改时间排序，保留最新的
        paths_with_time = [(p, p.stat().st_mtime) for p in paths]
        paths_with_time.sort(key=lambda x: x[1], reverse=True)
        
        # 保留第一个（最新的），删除其余的
        keep_path = paths_with_time[0][0]
        remove_paths = [p[0] for p in paths_with_time[1:]]
        
        logger.info(f"  保留: {keep_path}")
        
        for remove_path in remove_paths:
            # 计算文件夹大小
            folder_size = sum(f.stat().st_size for f in remove_path.rglob('*') if f.is_file())
            total_size_saved += folder_size
            total_duplicates += 1
            
            if dry_run:
                logger.info(f"  [预览] 将删除: {remove_path} ({folder_size / 1024 / 1024:.1f} MB)")
            else:
                logger.info(f"  删除: {remove_path} ({folder_size / 1024 / 1024:.1f} MB)")
                try:
                    import shutil
                    shutil.rmtree(remove_path)
                    logger.success(f"    ✓ 已删除")
                except Exception as e:
                    logger.error(f"    ✗ 删除失败: {e}")
    
    logger.info(f"\n总计:")
    logger.info(f"  重复文件夹数: {total_duplicates}")
    logger.info(f"  节省空间: {total_size_saved / 1024 / 1024:.1f} MB")
    
    if dry_run:
        logger.info(f"\n这只是预览！使用 --confirm 参数实际执行删除操作")


def main():
    parser = argparse.ArgumentParser(description='清理重复的Beat Saber谱面文件夹')
    parser.add_argument('directory', type=str, help='要清理的目录路径')
    parser.add_argument('--confirm', action='store_true', help='确认执行删除操作（默认只预览）')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    directory = Path(args.directory)
    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return 1
    
    logger.info(f"扫描目录: {directory}")
    duplicates = find_duplicate_beatmaps(directory)
    
    if not duplicates:
        logger.success("未发现重复文件！")
        return 0
    
    cleanup_duplicates(duplicates, dry_run=not args.confirm)
    return 0


if __name__ == "__main__":
    sys.exit(main())