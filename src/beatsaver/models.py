"""BeatSaver相关数据模型"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class MapStatus(Enum):
    """铺面状态"""
    PUBLISHED = "Published"
    FEEDBACK = "Feedback"
    ARCHIVED = "Archived"


@dataclass
class BeatSaverUser:
    """BeatSaver用户信息"""
    id: int
    name: str
    unique_set: bool = False
    hash: Optional[str] = None
    avatar: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverUser":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            unique_set=data.get("uniqueSet", False),
            hash=data.get("hash"),
            avatar=data.get("avatar")
        )


@dataclass
class BeatSaverStats:
    """铺面统计信息"""
    downloads: int
    plays: int
    downvotes: int
    upvotes: int
    score: float
    reviews: int = 0
    
    @property
    def rating(self) -> float:
        """评分 (0-1)"""
        return self.score
    
    @property
    def upvote_ratio(self) -> float:
        """点赞率 (0-1)"""
        total_votes = self.upvotes + self.downvotes
        if total_votes == 0:
            return 0.5  # 默认中性
        return self.upvotes / total_votes
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverStats":
        return cls(
            downloads=data.get("downloads", 0),
            plays=data.get("plays", 0),
            downvotes=data.get("downvotes", 0),
            upvotes=data.get("upvotes", 0),
            score=data.get("score", 0.0),
            reviews=data.get("reviews", 0)
        )


@dataclass
class BeatSaverMetadata:
    """铺面元数据"""
    bpm: float
    duration: int  # 秒
    song_name: str
    song_sub_name: str
    song_author_name: str
    level_author_name: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverMetadata":
        return cls(
            bpm=data.get("bpm", 0.0),
            duration=data.get("duration", 0),
            song_name=data.get("songName", ""),
            song_sub_name=data.get("songSubName", ""),
            song_author_name=data.get("songAuthorName", ""),
            level_author_name=data.get("levelAuthorName", "")
        )


@dataclass
class BeatSaverDifficulty:
    """难度信息"""
    njs: float  # Note Jump Speed
    offset: float
    notes: int
    bombs: int
    obstacles: int
    nps: float  # Notes Per Second
    length: float
    characteristic: str
    difficulty: str
    events: int
    chroma: bool = False
    me: bool = False
    ne: bool = False
    cinema: bool = False
    seconds: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverDifficulty":
        return cls(
            njs=data.get("njs", 0.0),
            offset=data.get("offset", 0.0),
            notes=data.get("notes", 0),
            bombs=data.get("bombs", 0),
            obstacles=data.get("obstacles", 0),
            nps=data.get("nps", 0.0),
            length=data.get("length", 0.0),
            characteristic=data.get("characteristic", ""),
            difficulty=data.get("difficulty", ""),
            events=data.get("events", 0),
            chroma=data.get("chroma", False),
            me=data.get("me", False),
            ne=data.get("ne", False),
            cinema=data.get("cinema", False),
            seconds=data.get("seconds", 0.0)
        )


@dataclass
class BeatSaverVersion:
    """铺面版本信息"""
    hash: str
    state: str
    created_at: datetime
    sage_score: int
    difficulties: List[BeatSaverDifficulty]
    download_url: str
    cover_url: str
    preview_url: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverVersion":
        # 解析难度列表
        difficulties = []
        for diff_data in data.get("diffs", []):
            difficulties.append(BeatSaverDifficulty.from_dict(diff_data))
        
        # 解析创建时间
        created_at_str = data.get("createdAt", "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            created_at = datetime.now()
        
        return cls(
            hash=data.get("hash", ""),
            state=data.get("state", ""),
            created_at=created_at,
            sage_score=data.get("sageScore", 0),
            difficulties=difficulties,
            download_url=data.get("downloadURL", ""),
            cover_url=data.get("coverURL", ""),
            preview_url=data.get("previewURL", "")
        )


@dataclass
class BeatSaverMap:
    """BeatSaver铺面信息"""
    id: str
    name: str
    description: str
    uploader: BeatSaverUser
    metadata: BeatSaverMetadata
    stats: BeatSaverStats
    uploaded: datetime
    automapper: bool
    ranked: bool
    qualified: bool
    versions: List[BeatSaverVersion]
    tags: Optional[List[str]] = None
    
    @property
    def latest_version(self) -> Optional[BeatSaverVersion]:
        """获取最新版本"""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.created_at)
    
    @property
    def download_url(self) -> Optional[str]:
        """获取下载链接"""
        latest = self.latest_version
        return latest.download_url if latest else None
    
    @property
    def max_nps(self) -> float:
        """获取最大每秒方块数"""
        max_nps = 0.0
        for version in self.versions:
            for difficulty in version.difficulties:
                max_nps = max(max_nps, difficulty.nps)
        return max_nps
    
    @property
    def difficulty_count(self) -> int:
        """获取难度数量"""
        total = 0
        for version in self.versions:
            total += len(version.difficulties)
        return total
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "song_name": self.metadata.song_name,
            "song_author": self.metadata.song_author_name,
            "level_author": self.metadata.level_author_name,
            "bpm": self.metadata.bpm,
            "duration": self.metadata.duration,
            "downloads": self.stats.downloads,
            "rating": self.stats.rating,
            "upvote_ratio": self.stats.upvote_ratio,
            "uploaded": self.uploaded.isoformat(),
            "max_nps": self.max_nps,
            "difficulty_count": self.difficulty_count,
            "download_url": self.download_url,
            "ranked": self.ranked,
            "automapper": self.automapper,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeatSaverMap":
        # 解析上传者
        uploader_data = data.get("uploader", {})
        uploader = BeatSaverUser.from_dict(uploader_data)
        
        # 解析元数据
        metadata_data = data.get("metadata", {})
        metadata = BeatSaverMetadata.from_dict(metadata_data)
        
        # 解析统计信息
        stats_data = data.get("stats", {})
        stats = BeatSaverStats.from_dict(stats_data)
        
        # 解析版本列表
        versions = []
        for version_data in data.get("versions", []):
            versions.append(BeatSaverVersion.from_dict(version_data))
        
        # 解析上传时间
        uploaded_str = data.get("uploaded", "")
        try:
            uploaded = datetime.fromisoformat(uploaded_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            uploaded = datetime.now()
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            uploader=uploader,
            metadata=metadata,
            stats=stats,
            uploaded=uploaded,
            automapper=data.get("automapper", False),
            ranked=data.get("ranked", False),
            qualified=data.get("qualified", False),
            versions=versions,
            tags=data.get("tags")
        )