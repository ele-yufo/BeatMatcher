"""BeatSaver谱面下载器"""

import asyncio
import zipfile
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
from aiofiles import open as aopen
from loguru import logger

# Platform-specific file locking imports
try:
    if sys.platform != 'win32':
        import fcntl
    else:
        import msvcrt
except ImportError:
    # Fallback for systems without file locking support
    fcntl = None
    msvcrt = None

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
        
        # 全面检查是否已经下载（包括根目录和各难度文件夹）
        extracted_dir = output_dir / safe_name
        existing_path = self._find_existing_beatmap(output_dir, safe_name, beatmap.id)
        
        if zip_path.exists():
            self.logger.info(f"谱面ZIP已存在，跳过下载: {zip_path}")
            return zip_path
        elif extracted_dir.exists():
            self.logger.info(f"谱面文件夹已存在，跳过下载: {extracted_dir}")
            return extracted_dir
        elif existing_path:
            self.logger.info(f"谱面已存在于难度文件夹中，跳过下载: {existing_path}")
            return existing_path
        
        # 下载前最后一次检查（双重检查模式，减少并发竞态）
        final_check = self._find_existing_beatmap(output_dir, safe_name, beatmap.id)
        if final_check:
            self.logger.info(f"下载前最终检查发现已存在谱面: {final_check}")
            return final_check
        
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
                
                # 安全解压 - 防止目录遍历攻击
                self._safe_extract_all(zip_file, extract_dir)
            
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
    
    def _find_existing_beatmap(self, output_dir: Path, safe_name: str, beatmap_id: str) -> Optional[Path]:
        """查找已存在的谱面文件夹（优化版本）
        
        Args:
            output_dir: 输出根目录
            safe_name: 安全文件名
            beatmap_id: 谱面ID
            
        Returns:
            Optional[Path]: 找到的谱面路径，未找到返回None
        """
        # 只搜索一级子目录，避免深度遍历性能问题
        try:
            for item in output_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # 检查是否是难度文件夹（可配置的关键词）
                item_name_lower = item.name.lower()
                difficulty_keywords = getattr(self.config, 'difficulty_keywords', 
                    ['easy', 'medium', 'hard', 'blocks', 'nps', '难度'])
                is_difficulty_folder = any(keyword in item_name_lower for keyword in difficulty_keywords)
                
                if is_difficulty_folder:
                    # 在难度文件夹中搜索匹配的谱面
                    # 1. 精确匹配文件夹名
                    exact_match = item / safe_name
                    if exact_match.exists():
                        return exact_match
                    
                    # 2. 快速ID匹配（限制搜索范围）
                    try:
                        for beatmap_folder in item.iterdir():
                            if (beatmap_folder.is_dir() and 
                                beatmap_folder.name.startswith(beatmap_id + '_')):
                                self.logger.debug(f"通过ID找到重复谱面: {beatmap_folder}")
                                return beatmap_folder
                    except (OSError, PermissionError):
                        # 跳过无法访问的文件夹
                        continue
        
        except (OSError, PermissionError):
            self.logger.warning(f"无法访问输出目录: {output_dir}")
        
        return None
    
    def _safe_extract_all(self, zip_file: zipfile.ZipFile, extract_dir: Path) -> None:
        """安全解压ZIP文件，防止目录遍历攻击
        
        Args:
            zip_file: ZIP文件对象
            extract_dir: 目标解压目录
        """
        import os
        
        extract_dir_resolved = extract_dir.resolve()
        
        for member in zip_file.infolist():
            # 检查文件名是否安全
            if self._is_safe_zip_member(member, extract_dir_resolved):
                try:
                    zip_file.extract(member, extract_dir)
                except Exception as e:
                    self.logger.warning(f"跳过问题文件 {member.filename}: {e}")
                    continue
            else:
                self.logger.warning(f"跳过不安全的文件路径: {member.filename}")
    
    def _is_safe_zip_member(self, member: zipfile.ZipInfo, extract_dir: Path) -> bool:
        """检查ZIP成员是否安全
        
        Args:
            member: ZIP文件成员
            extract_dir: 解压目录
            
        Returns:
            bool: 是否安全
        """
        import os
        
        # 获取目标文件路径
        target_path = extract_dir / member.filename
        
        try:
            # 检查是否为符号链接（防止符号链接攻击）
            if target_path.exists() and target_path.is_symlink():
                self.logger.warning(f"跳过符号链接文件: {member.filename}")
                return False
            
            # 解析路径，防止符号链接攻击 - 使用strict=True增强安全性
            try:
                target_resolved = target_path.resolve(strict=True)
            except (OSError, RuntimeError):
                # strict=True在路径不存在时会抛出异常，这是正常的
                target_resolved = target_path.resolve()
            
            # 检查目标路径是否在预期目录内
            if not str(target_resolved).startswith(str(extract_dir.resolve())):
                return False
            
            # 检查文件名是否包含危险字符
            filename = member.filename
            
            # Unix路径检查 - 防止目录遍历
            if '..' in filename or filename.startswith('/'):
                return False
                
            # 检查文件大小限制（防止ZIP炸弹）
            if member.file_size > 100 * 1024 * 1024:  # 100MB限制
                self.logger.warning(f"文件过大，跳过: {filename} ({member.file_size / 1024 / 1024:.1f}MB)")
                return False
            
            return True
            
        except (OSError, ValueError) as e:
            self.logger.warning(f"路径解析失败: {member.filename} - {e}")
            return False
    
    async def close(self):
        """关闭下载器"""
        await self.api_client.close()