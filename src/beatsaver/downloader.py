"""BeatSaver谱面下载器"""

import asyncio
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any
from aiofiles import open as aopen
from loguru import logger

from .api_client import BeatSaverAPIClient
from .models import BeatSaverMap
from ..utils.config import Config
from ..utils.exceptions import DownloadError, BeatSaverAPIError


class BeatmapDownloader:
    """谱面下载器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        self.api_client = BeatSaverAPIClient(config)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.api_client.close()
    
    async def download(self, beatmap: BeatSaverMap, output_dir: Path) -> Optional[Path]:
        """下载谱面
        
        Args:
            beatmap: BeatSaver谱面信息
            output_dir: 输出目录
            
        Returns:
            Optional[Path]: 下载的文件路径，失败返回None
        """
        if not beatmap.download_url:
            self.logger.error(f"谱面没有下载链接: {beatmap.id}")
            return None
        
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        safe_name = self._generate_safe_filename(beatmap)
        zip_path = output_dir / f"{safe_name}.zip"
        
        # 检查是否已经下载
        if zip_path.exists():
            self.logger.info(f"谱面已存在，跳过下载: {zip_path}")
            return zip_path
        
        self.logger.info(f"开始下载谱面: {beatmap.name} -> {zip_path}")
        
        try:
            # 下载文件
            zip_data = await self.api_client.download_map(beatmap.id)
            
            # 保存到文件
            async with aopen(zip_path, 'wb') as f:
                await f.write(zip_data)
            
            # 验证ZIP文件
            if not self._validate_zip_file(zip_path):
                zip_path.unlink(missing_ok=True)
                raise DownloadError(beatmap.download_url, "下载的ZIP文件损坏")
            
            self.logger.info(f"谱面下载完成: {zip_path} ({len(zip_data)} bytes)")
            return zip_path
            
        except BeatSaverAPIError as e:
            self.logger.error(f"下载谱面失败: {beatmap.id} - {e}")
            # 清理可能存在的部分下载文件
            zip_path.unlink(missing_ok=True)
            return None
            
        except Exception as e:
            self.logger.error(f"下载谱面时出现意外错误: {beatmap.id} - {e}")
            # 清理可能存在的部分下载文件
            zip_path.unlink(missing_ok=True)
            raise DownloadError(beatmap.download_url, str(e))
    
    async def download_batch(
        self, 
        beatmaps: list[BeatSaverMap], 
        output_dir: Path,
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Optional[Path]]:
        """批量下载谱面
        
        Args:
            beatmaps: 谱面列表
            output_dir: 输出目录
            max_concurrent: 最大并发数
            
        Returns:
            Dict[str, Optional[Path]]: 下载结果字典，键为谱面ID
        """
        if not beatmaps:
            return {}
        
        max_concurrent = max_concurrent or self.config.files.max_concurrent_downloads
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(beatmap: BeatSaverMap) -> tuple[str, Optional[Path]]:
            async with semaphore:
                result = await self.download(beatmap, output_dir)
                return beatmap.id, result
        
        self.logger.info(f"开始批量下载 {len(beatmaps)} 个谱面 (并发数: {max_concurrent})")
        
        # 创建下载任务
        tasks = [download_with_semaphore(beatmap) for beatmap in beatmaps]
        
        # 执行下载
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        download_results = {}
        success_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"批量下载任务异常: {result}")
                continue
            
            beatmap_id, path = result
            download_results[beatmap_id] = path
            if path is not None:
                success_count += 1
        
        self.logger.info(f"批量下载完成: {success_count}/{len(beatmaps)} 成功")
        return download_results
    
    def extract_beatmap(self, zip_path: Path, extract_dir: Optional[Path] = None) -> Optional[Path]:
        """解压谱面文件
        
        Args:
            zip_path: ZIP文件路径
            extract_dir: 解压目录，默认为ZIP文件同级目录
            
        Returns:
            Optional[Path]: 解压后的目录路径，失败返回None
        """
        if not zip_path.exists():
            self.logger.error(f"ZIP文件不存在: {zip_path}")
            return None
        
        if extract_dir is None:
            extract_dir = zip_path.parent / zip_path.stem
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.logger.debug(f"解压谱面: {zip_path} -> {extract_dir}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # 检查ZIP文件完整性
                zip_file.testzip()
                
                # 解压所有文件
                zip_file.extractall(extract_dir)
            
            # 验证关键文件是否存在
            if not self._validate_beatmap_files(extract_dir):
                self.logger.warning(f"谱面文件不完整: {extract_dir}")
            
            self.logger.info(f"谱面解压完成: {extract_dir}")
            return extract_dir
            
        except zipfile.BadZipFile:
            self.logger.error(f"ZIP文件损坏: {zip_path}")
            return None
        except Exception as e:
            self.logger.error(f"解压谱面失败: {zip_path} - {e}")
            return None
    
    def _generate_safe_filename(self, beatmap: BeatSaverMap) -> str:
        """生成安全的文件名
        
        Args:
            beatmap: 谱面信息
            
        Returns:
            str: 安全的文件名
        """
        # 使用谱面ID和标题生成文件名
        song_name = beatmap.metadata.song_name or "unknown"
        artist_name = beatmap.metadata.song_author_name or "unknown"
        
        # 清理文件名中的非法字符
        safe_song = self._clean_filename(song_name)
        safe_artist = self._clean_filename(artist_name)
        
        # 限制长度
        max_length = 100
        filename = f"{beatmap.id}_{safe_artist}_{safe_song}"
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        return filename
    
    def _clean_filename(self, filename: str) -> str:
        """清理文件名中的非法字符 - Windows和Linux兼容
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        import re
        import os
        
        # Windows和Linux通用的非法字符
        # Windows: < > : " / \ | ? *  以及控制字符
        # Linux: 主要是 / 和空字符，但为了兼容性我们统一处理
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # Windows特有的保留名称检查
        if os.name == 'nt':  # Windows系统
            reserved_names = {
                'CON', 'PRN', 'AUX', 'NUL',
                'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
            }
            name_upper = filename.upper().split('.')[0]  # 检查文件名部分，忽略扩展名
            if name_upper in reserved_names:
                filename = f"_{filename}"  # 前缀下划线避免冲突
        
        # 移除连续的下划线和空格
        filename = re.sub(r'[_\s]+', '_', filename)
        
        # Windows文件名不能以点或空格结尾
        if os.name == 'nt':
            filename = filename.rstrip('. ')
        
        # 移除开头和结尾的下划线
        filename = filename.strip('_')
        
        # 确保文件名不为空且不超过合理长度
        if not filename:
            filename = "unnamed"
        
        # Windows路径长度限制 (通常是260字符，但文件名部分建议不超过255)
        max_filename_length = 200  # 保守一点，给路径留空间
        if len(filename) > max_filename_length:
            filename = filename[:max_filename_length]
        
        return filename
    
    def _validate_zip_file(self, zip_path: Path) -> bool:
        """验证ZIP文件是否有效
        
        Args:
            zip_path: ZIP文件路径
            
        Returns:
            bool: 是否有效
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # 测试ZIP文件完整性
                result = zip_file.testzip()
                return result is None
        except (zipfile.BadZipFile, FileNotFoundError):
            return False
    
    def _validate_beatmap_files(self, beatmap_dir: Path) -> bool:
        """验证谱面文件是否完整
        
        Args:
            beatmap_dir: 谱面目录
            
        Returns:
            bool: 文件是否完整
        """
        # 检查关键文件
        info_file = beatmap_dir / "Info.dat"
        if not info_file.exists():
            # 尝试小写文件名
            info_file = beatmap_dir / "info.dat"
            if not info_file.exists():
                return False
        
        # 检查是否有难度文件
        difficulty_files = list(beatmap_dir.glob("*.dat"))
        if len(difficulty_files) < 2:  # Info.dat + 至少一个难度文件
            return False
        
        return True
    
    async def close(self):
        """关闭下载器"""
        await self.api_client.close()