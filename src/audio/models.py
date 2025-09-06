"""音频相关数据模型"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class AudioMetadata:
    """音频文件元数据"""
    title: str
    artist: str
    album: Optional[str] = None
    duration: Optional[float] = None  # 秒
    bitrate: Optional[int] = None
    file_format: Optional[str] = None
    file_size: Optional[int] = None  # 字节
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    
    def __post_init__(self):
        """数据清理和标准化"""
        # 清理空字符串
        if self.title == "":
            self.title = "Unknown Title"
        if self.artist == "":
            self.artist = "Unknown Artist"
        
        # 标准化字符串
        self.title = self.title.strip()
        self.artist = self.artist.strip()
        
        if self.album:
            self.album = self.album.strip()
        if self.genre:
            self.genre = self.genre.strip()


@dataclass
class AudioFile:
    """音频文件信息"""
    file_path: Path
    metadata: AudioMetadata
    
    @property
    def title(self) -> str:
        return self.metadata.title
    
    @property
    def artist(self) -> str:
        return self.metadata.artist
    
    @property
    def album(self) -> Optional[str]:
        return self.metadata.album
    
    @property
    def duration(self) -> Optional[float]:
        return self.metadata.duration
    
    @property
    def file_size_mb(self) -> Optional[float]:
        """文件大小（MB）"""
        if self.metadata.file_size:
            return self.metadata.file_size / (1024 * 1024)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "file_path": str(self.file_path),
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "bitrate": self.metadata.bitrate,
            "file_format": self.metadata.file_format,
            "file_size_mb": self.file_size_mb,
            "year": self.metadata.year,
            "genre": self.metadata.genre,
            "track_number": self.metadata.track_number,
        }
    
    def __str__(self) -> str:
        return f"{self.artist} - {self.title}"