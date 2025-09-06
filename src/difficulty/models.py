"""难度分析相关数据模型"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class DifficultyCategory(Enum):
    """难度分类"""
    EASY = "easy"
    MEDIUM = "medium" 
    HARD = "hard"


@dataclass
class BeatmapNote:
    """铺面方块信息"""
    time: float  # 时间戳（拍）
    line_index: int  # 横向位置 (0-3)
    line_layer: int  # 纵向位置 (0-2)
    type: int  # 方块类型 (0=红, 1=蓝)
    cut_direction: int  # 切割方向


@dataclass
class BeatmapObstacle:
    """障碍物信息"""
    time: float  # 时间戳（拍）
    line_index: int  # 起始横向位置
    type: int  # 障碍物类型
    duration: float  # 持续时间（拍）
    width: int  # 宽度


@dataclass
class BeatmapEvent:
    """事件信息（灯光等）"""
    time: float  # 时间戳（拍）
    type: int  # 事件类型
    value: int  # 事件值


@dataclass
class DifficultyStats:
    """难度统计信息"""
    notes_count: int
    obstacles_count: int
    events_count: int
    duration: float  # 歌曲长度（秒）
    bpm: float  # BPM
    nps: float  # Notes Per Second
    peak_nps: float  # 峰值NPS
    density_variations: List[float]  # 密度变化数组
    difficulty_name: str
    characteristic: str
    
    @property
    def difficulty_category(self) -> DifficultyCategory:
        """根据NPS判断难度分类"""
        if self.nps < 4.0:
            return DifficultyCategory.EASY
        elif self.nps < 7.0:
            return DifficultyCategory.MEDIUM
        else:
            return DifficultyCategory.HARD
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "notes_count": self.notes_count,
            "obstacles_count": self.obstacles_count,
            "events_count": self.events_count,
            "duration": self.duration,
            "bpm": self.bpm,
            "nps": self.nps,
            "peak_nps": self.peak_nps,
            "difficulty_name": self.difficulty_name,
            "characteristic": self.characteristic,
            "difficulty_category": self.difficulty_category.value,
            "density_variations_count": len(self.density_variations),
        }


@dataclass
class BeatmapAnalysis:
    """铺面分析结果"""
    beatmap_id: str
    song_name: str
    difficulties: List[DifficultyStats]
    
    @property
    def max_nps(self) -> float:
        """获取最大NPS"""
        if not self.difficulties:
            return 0.0
        return max(diff.nps for diff in self.difficulties)
    
    @property
    def primary_difficulty_category(self) -> DifficultyCategory:
        """获取主要难度分类（最高难度）"""
        if not self.difficulties:
            return DifficultyCategory.EASY
        
        max_nps = self.max_nps
        if max_nps < 4.0:
            return DifficultyCategory.EASY
        elif max_nps < 7.0:
            return DifficultyCategory.MEDIUM
        else:
            return DifficultyCategory.HARD
    
    def get_difficulty_by_name(self, name: str) -> Optional[DifficultyStats]:
        """根据名称获取难度统计"""
        for diff in self.difficulties:
            if diff.difficulty_name.lower() == name.lower():
                return diff
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "beatmap_id": self.beatmap_id,
            "song_name": self.song_name,
            "max_nps": self.max_nps,
            "primary_difficulty_category": self.primary_difficulty_category.value,
            "difficulties": [diff.to_dict() for diff in self.difficulties],
            "difficulty_count": len(self.difficulties),
        }