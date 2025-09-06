"""音频元数据提取器"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError
from loguru import logger

from .models import AudioMetadata
from ..utils.exceptions import AudioProcessingError


class MetadataExtractor:
    """音频元数据提取器"""
    
    def __init__(self):
        self.logger = logger.bind(name=self.__class__.__name__)
    
    def extract(self, file_path: Path) -> AudioMetadata:
        """提取音频文件元数据
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            AudioMetadata: 提取的元数据
            
        Raises:
            AudioProcessingError: 处理失败时抛出
        """
        try:
            # 检查文件是否存在
            if not file_path.exists():
                raise AudioProcessingError(str(file_path), "文件不存在")
            
            # 获取文件大小
            file_size = file_path.stat().st_size
            
            # 使用mutagen提取元数据
            audio_file = MutagenFile(file_path)
            
            if audio_file is None:
                raise AudioProcessingError(str(file_path), "不支持的音频格式")
            
            # 提取基本信息
            metadata = self._extract_metadata(audio_file)
            metadata["file_size"] = file_size
            metadata["file_format"] = file_path.suffix.lower()
            
            # 创建AudioMetadata对象
            audio_metadata = AudioMetadata(**metadata)
            
            self.logger.debug(f"提取元数据成功: {file_path.name} - {audio_metadata.artist} - {audio_metadata.title}")
            return audio_metadata
            
        except ID3NoHeaderError:
            # 对于没有ID3标签的文件，使用文件名作为标题
            self.logger.warning(f"文件缺少元数据标签: {file_path.name}")
            return self._extract_from_filename(file_path)
            
        except Exception as e:
            self.logger.error(f"提取元数据失败: {file_path} - {e}")
            # 如果提取失败，尝试从文件名提取信息
            return self._extract_from_filename(file_path)
    
    def _extract_metadata(self, audio_file) -> Dict[str, Any]:
        """从mutagen文件对象中提取元数据"""
        metadata = {
            "title": "Unknown Title",
            "artist": "Unknown Artist",
            "album": None,
            "duration": None,
            "bitrate": None,
            "year": None,
            "genre": None,
            "track_number": None,
        }
        
        # 获取时长
        if audio_file.info and hasattr(audio_file.info, 'length'):
            metadata["duration"] = audio_file.info.length
        
        # 获取码率
        if audio_file.info and hasattr(audio_file.info, 'bitrate'):
            metadata["bitrate"] = audio_file.info.bitrate
        
        # 提取标签信息
        if audio_file.tags:
            # 标题 (支持ID3, FLAC, MP4等格式)
            title = self._get_tag_value(audio_file.tags, ['TIT2', 'TITLE', 'title', '\xa9nam'])
            if title:
                metadata["title"] = title
            
            # 艺术家
            artist = self._get_tag_value(audio_file.tags, ['TPE1', 'ARTIST', 'artist', '\xa9ART'])
            if artist:
                metadata["artist"] = artist
            
            # 专辑
            album = self._get_tag_value(audio_file.tags, ['TALB', 'ALBUM', 'album', '\xa9alb'])
            if album:
                metadata["album"] = album
            
            # 年份
            year = self._get_tag_value(audio_file.tags, ['TDRC', 'DATE', 'date', '\xa9day'])
            if year:
                try:
                    metadata["year"] = int(str(year)[:4])  # 只取年份部分
                except (ValueError, TypeError):
                    pass
            
            # 流派
            genre = self._get_tag_value(audio_file.tags, ['TCON', 'GENRE', 'genre', '\xa9gen'])
            if genre:
                metadata["genre"] = genre
            
            # 曲目编号
            track = self._get_tag_value(audio_file.tags, ['TRCK', 'TRACKNUMBER', 'tracknumber', 'trkn'])
            if track:
                try:
                    # 处理 "1/10" 这种格式
                    track_str = str(track).split('/')[0]
                    metadata["track_number"] = int(track_str)
                except (ValueError, TypeError):
                    pass
        
        return metadata
    
    def _get_tag_value(self, tags, tag_keys: list) -> Optional[str]:
        """从标签中获取值（支持多种标签格式）"""
        for key in tag_keys:
            try:
                if key in tags:
                    value = tags[key]
                    if isinstance(value, list) and value:
                        return str(value[0])
                    elif value:
                        return str(value)
            except ValueError:
                # 某些格式的标签对象在检查不兼容的键时会抛出ValueError
                # 例如FLAC文件检查MP4格式的标签键
                continue
        return None
    
    def _extract_from_filename(self, file_path: Path) -> AudioMetadata:
        """从文件名中提取信息（作为备选方案）"""
        filename = file_path.stem
        
        # 尝试解析 "Artist - Title" 格式
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            # 只有标题
            artist = "Unknown Artist"
            title = filename
        
        file_size = file_path.stat().st_size if file_path.exists() else None
        
        return AudioMetadata(
            title=title,
            artist=artist,
            file_size=file_size,
            file_format=file_path.suffix.lower()
        )