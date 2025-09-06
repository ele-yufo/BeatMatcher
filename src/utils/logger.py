"""日志系统模块"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger


def setup_logger(level: str = "INFO", log_file: Optional[str] = None) -> object:
    """设置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        logger对象
    """
    # 移除默认handler
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )
    
    # 添加文件输出
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            encoding="utf-8",
        )
    
    # 设置第三方库的日志级别
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    logger.info("日志系统初始化完成")
    return logger


def get_logger(name: str) -> object:
    """获取指定名称的logger
    
    Args:
        name: logger名称
        
    Returns:
        logger对象
    """
    return logger.bind(name=name)