"""音频文件扫描器"""

import asyncio
from pathlib import Path
from typing import List, AsyncGenerator, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from tqdm import tqdm

from .models import AudioFile
from .metadata_extractor import MetadataExtractor
from ..utils.config import Config
from ..utils.exceptions import AudioProcessingError


class AudioScanner:
    """音频文件扫描器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.extractor = MetadataExtractor()
        self.logger = logger.bind(name=self.__class__.__name__)
        self.supported_formats = set(config.files.supported_audio_formats)
    
    async def scan_directory(self, directory: Path, recursive: bool = True) -> List[AudioFile]:
        """扫描目录中的音频文件
        
        Args:
            directory: 要扫描的目录路径
            recursive: 是否递归扫描子目录
            
        Returns:
            List[AudioFile]: 音频文件列表
        """
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"路径不是目录: {directory}")
        
        self.logger.info(f"开始扫描目录: {directory}")
        
        # 查找音频文件
        audio_files_paths = self._find_audio_files(directory, recursive)
        total_files = len(audio_files_paths)
        
        if total_files == 0:
            self.logger.warning("未找到支持的音频文件")
            return []
        
        self.logger.info(f"发现 {total_files} 个音频文件")
        
        # 并行提取元数据
        audio_files = await self._extract_metadata_parallel(audio_files_paths)
        
        self.logger.info(f"成功处理 {len(audio_files)}/{total_files} 个音频文件")
        return audio_files
    
    def _find_audio_files(self, directory: Path, recursive: bool = True) -> List[Path]:
        """查找音频文件"""
        audio_files = []
        
        if recursive:
            # 递归搜索
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                    audio_files.append(file_path)
        else:
            # 只搜索当前目录
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                    audio_files.append(file_path)
        
        return sorted(audio_files)
    
    async def _extract_metadata_parallel(self, file_paths: List[Path]) -> List[AudioFile]:
        """并行提取元数据"""
        max_workers = min(self.config.performance.max_concurrent_tasks, len(file_paths))
        audio_files = []
        failed_files = []
        
        # 创建进度条
        if self.config.performance.show_progress:
            pbar = tqdm(total=len(file_paths), desc="提取元数据")
        else:
            pbar = None
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_path = {
                executor.submit(self._extract_single_metadata, path): path
                for path in file_paths
            }
            
            # 收集结果
            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                try:
                    audio_file = future.result()
                    if audio_file:
                        audio_files.append(audio_file)
                except Exception as e:
                    failed_files.append((file_path, str(e)))
                    self.logger.warning(f"处理失败: {file_path} - {e}")
                finally:
                    if pbar:
                        pbar.update(1)
        
        if pbar:
            pbar.close()
        
        # 记录失败的文件
        if failed_files:
            self.logger.warning(f"失败处理 {len(failed_files)} 个文件:")
            for file_path, error in failed_files:
                self.logger.warning(f"  - {file_path}: {error}")
        
        return audio_files
    
    def _extract_single_metadata(self, file_path: Path) -> Optional[AudioFile]:
        """提取单个文件的元数据（在线程中运行）"""
        try:
            metadata = self.extractor.extract(file_path)
            return AudioFile(file_path=file_path, metadata=metadata)
        except AudioProcessingError as e:
            self.logger.debug(f"跳过文件: {e}")
            return None
        except Exception as e:
            self.logger.error(f"意外错误: {file_path} - {e}")
            return None
    
    async def scan_file(self, file_path: Path) -> Optional[AudioFile]:
        """扫描单个音频文件
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            Optional[AudioFile]: 音频文件对象，失败返回None
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"不支持的音频格式: {file_path.suffix}")
        
        try:
            # 在线程池中运行
            loop = asyncio.get_event_loop()
            audio_file = await loop.run_in_executor(
                None, self._extract_single_metadata, file_path
            )
            return audio_file
        except Exception as e:
            self.logger.error(f"扫描文件失败: {file_path} - {e}")
            return None
    
    async def scan_files(self, file_paths: List[Path]) -> List[AudioFile]:
        """扫描多个音频文件
        
        Args:
            file_paths: 音频文件路径列表
            
        Returns:
            List[AudioFile]: 音频文件列表
        """
        if not file_paths:
            return []
        
        # 过滤支持的格式
        valid_paths = [
            path for path in file_paths
            if path.exists() and path.suffix.lower() in self.supported_formats
        ]
        
        if not valid_paths:
            self.logger.warning("没有找到有效的音频文件")
            return []
        
        self.logger.info(f"处理 {len(valid_paths)} 个音频文件")
        return await self._extract_metadata_parallel(valid_paths)
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式列表"""
        return list(self.supported_formats)