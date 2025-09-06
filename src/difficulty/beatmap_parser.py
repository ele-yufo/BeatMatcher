"""Beat Saber铺面文件解析器"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .models import (
    BeatmapNote, BeatmapObstacle, BeatmapEvent, 
    DifficultyStats, BeatmapAnalysis
)
from ..utils.exceptions import BeatmapParsingError


class BeatmapParser:
    """Beat Saber铺面解析器"""
    
    def __init__(self):
        self.logger = logger.bind(name=self.__class__.__name__)
    
    def parse_beatmap_directory(self, beatmap_dir: Path) -> Optional[BeatmapAnalysis]:
        """解析铺面目录
        
        Args:
            beatmap_dir: 铺面目录路径
            
        Returns:
            Optional[BeatmapAnalysis]: 解析结果，失败返回None
        """
        try:
            # 找到Info.dat文件
            info_file = self._find_info_file(beatmap_dir)
            if not info_file:
                raise BeatmapParsingError(str(beatmap_dir), "找不到Info.dat文件")
            
            # 解析Info.dat
            info_data = self._parse_json_file(info_file)
            if not info_data:
                raise BeatmapParsingError(str(info_file), "Info.dat解析失败")
            
            # 提取基本信息
            song_name = info_data.get("_songName", "Unknown")
            bpm = float(info_data.get("_beatsPerMinute", 120))
            
            # 解析所有难度
            difficulties = []
            difficulty_sets = info_data.get("_difficultyBeatmapSets", [])
            
            for diff_set in difficulty_sets:
                characteristic = diff_set.get("_beatmapCharacteristicName", "Standard")
                beatmaps = diff_set.get("_difficultyBeatmaps", [])
                
                for beatmap_info in beatmaps:
                    try:
                        diff_stats = self._parse_difficulty(
                            beatmap_dir, beatmap_info, bpm, characteristic
                        )
                        if diff_stats:
                            difficulties.append(diff_stats)
                    except Exception as e:
                        self.logger.warning(f"解析难度失败: {e}")
                        continue
            
            if not difficulties:
                self.logger.warning(f"未找到有效难度: {beatmap_dir}")
                return None
            
            return BeatmapAnalysis(
                beatmap_id=beatmap_dir.name,
                song_name=song_name,
                difficulties=difficulties
            )
            
        except Exception as e:
            self.logger.error(f"解析铺面目录失败: {beatmap_dir} - {e}")
            return None
    
    def parse_difficulty_file(
        self, 
        difficulty_file: Path, 
        bpm: float = 120.0,
        difficulty_name: str = "Unknown",
        characteristic: str = "Standard"
    ) -> Optional[DifficultyStats]:
        """解析单个难度文件
        
        Args:
            difficulty_file: 难度文件路径
            bpm: BPM值
            difficulty_name: 难度名称
            characteristic: 特性名称
            
        Returns:
            Optional[DifficultyStats]: 难度统计，失败返回None
        """
        try:
            # 解析难度文件
            diff_data = self._parse_json_file(difficulty_file)
            if not diff_data:
                return None
            
            return self._analyze_difficulty_data(
                diff_data, bpm, difficulty_name, characteristic
            )
            
        except Exception as e:
            self.logger.error(f"解析难度文件失败: {difficulty_file} - {e}")
            return None
    
    def _find_info_file(self, beatmap_dir: Path) -> Optional[Path]:
        """查找Info.dat文件"""
        # 常见的Info文件名
        possible_names = ["Info.dat", "info.dat", "INFO.DAT"]
        
        for name in possible_names:
            info_file = beatmap_dir / name
            if info_file.exists():
                return info_file
        
        return None
    
    def _parse_json_file(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """解析JSON文件"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError) as e:
            self.logger.error(f"JSON文件解析失败: {json_file} - {e}")
            return None
    
    def _parse_difficulty(
        self, 
        beatmap_dir: Path, 
        beatmap_info: Dict[str, Any], 
        bpm: float,
        characteristic: str
    ) -> Optional[DifficultyStats]:
        """解析单个难度"""
        # 获取难度文件名和信息
        difficulty_name = beatmap_info.get("_difficulty", "Unknown")
        beatmap_filename = beatmap_info.get("_beatmapFilename", "")
        
        if not beatmap_filename:
            self.logger.warning(f"难度文件名为空: {difficulty_name}")
            return None
        
        # 查找难度文件
        difficulty_file = beatmap_dir / beatmap_filename
        if not difficulty_file.exists():
            self.logger.warning(f"难度文件不存在: {difficulty_file}")
            return None
        
        # 解析难度数据
        diff_data = self._parse_json_file(difficulty_file)
        if not diff_data:
            return None
        
        return self._analyze_difficulty_data(diff_data, bpm, difficulty_name, characteristic)
    
    def _analyze_difficulty_data(
        self, 
        diff_data: Dict[str, Any], 
        bpm: float,
        difficulty_name: str,
        characteristic: str
    ) -> Optional[DifficultyStats]:
        """分析难度数据"""
        try:
            # 解析方块数据
            notes_data = diff_data.get("_notes", [])
            obstacles_data = diff_data.get("_obstacles", [])
            events_data = diff_data.get("_events", [])
            
            # 转换为对象
            notes = [self._parse_note(note) for note in notes_data if note]
            obstacles = [self._parse_obstacle(obs) for obs in obstacles_data if obs]
            events = [self._parse_event(event) for event in events_data if event]
            
            # 过滤无效数据
            notes = [n for n in notes if n is not None]
            obstacles = [o for o in obstacles if o is not None]
            events = [e for e in events if e is not None]
            
            if not notes:
                self.logger.warning(f"难度没有方块数据: {difficulty_name}")
                return None
            
            # 计算统计信息
            duration = self._calculate_duration(notes, bpm)
            nps = len(notes) / duration if duration > 0 else 0
            peak_nps = self._calculate_peak_nps(notes, bpm)
            density_variations = self._calculate_density_variations(notes, bpm)
            
            return DifficultyStats(
                notes_count=len(notes),
                obstacles_count=len(obstacles),
                events_count=len(events),
                duration=duration,
                bpm=bpm,
                nps=nps,
                peak_nps=peak_nps,
                density_variations=density_variations,
                difficulty_name=difficulty_name,
                characteristic=characteristic
            )
            
        except Exception as e:
            self.logger.error(f"分析难度数据失败: {e}")
            return None
    
    def _parse_note(self, note_data: Dict[str, Any]) -> Optional[BeatmapNote]:
        """解析方块数据"""
        try:
            return BeatmapNote(
                time=float(note_data.get("_time", 0)),
                line_index=int(note_data.get("_lineIndex", 0)),
                line_layer=int(note_data.get("_lineLayer", 0)),
                type=int(note_data.get("_type", 0)),
                cut_direction=int(note_data.get("_cutDirection", 0))
            )
        except (ValueError, KeyError) as e:
            self.logger.debug(f"解析方块数据失败: {e}")
            return None
    
    def _parse_obstacle(self, obstacle_data: Dict[str, Any]) -> Optional[BeatmapObstacle]:
        """解析障碍物数据"""
        try:
            return BeatmapObstacle(
                time=float(obstacle_data.get("_time", 0)),
                line_index=int(obstacle_data.get("_lineIndex", 0)),
                type=int(obstacle_data.get("_type", 0)),
                duration=float(obstacle_data.get("_duration", 0)),
                width=int(obstacle_data.get("_width", 1))
            )
        except (ValueError, KeyError) as e:
            self.logger.debug(f"解析障碍物数据失败: {e}")
            return None
    
    def _parse_event(self, event_data: Dict[str, Any]) -> Optional[BeatmapEvent]:
        """解析事件数据"""
        try:
            return BeatmapEvent(
                time=float(event_data.get("_time", 0)),
                type=int(event_data.get("_type", 0)),
                value=int(event_data.get("_value", 0))
            )
        except (ValueError, KeyError) as e:
            self.logger.debug(f"解析事件数据失败: {e}")
            return None
    
    def _calculate_duration(self, notes: List[BeatmapNote], bpm: float) -> float:
        """计算歌曲持续时间（秒）"""
        if not notes:
            return 0.0
        
        # 找到最后一个方块的时间
        last_note_time = max(note.time for note in notes)
        
        # 转换拍数到秒数
        # 拍数 * 60 / BPM = 秒数
        duration = (last_note_time * 60.0) / bpm
        return max(duration, 1.0)  # 至少1秒
    
    def _calculate_peak_nps(self, notes: List[BeatmapNote], bpm: float, window_size: float = 1.0) -> float:
        """计算峰值NPS（在指定窗口大小内）
        
        Args:
            notes: 方块列表
            bpm: BPM值
            window_size: 窗口大小（秒）
            
        Returns:
            float: 峰值NPS
        """
        if not notes:
            return 0.0
        
        # 将拍数时间转换为秒
        note_times = [(note.time * 60.0) / bpm for note in notes]
        note_times.sort()
        
        if len(note_times) < 2:
            return len(note_times)
        
        max_nps = 0.0
        window_beats = (window_size * bpm) / 60.0  # 转换窗口大小为拍数
        
        for i, start_time in enumerate(note_times):
            end_time = start_time + window_size
            
            # 统计窗口内的方块数量
            count = 0
            for j in range(i, len(note_times)):
                if note_times[j] <= end_time:
                    count += 1
                else:
                    break
            
            nps = count / window_size
            max_nps = max(max_nps, nps)
        
        return max_nps
    
    def _calculate_density_variations(self, notes: List[BeatmapNote], bpm: float, segment_duration: float = 2.0) -> List[float]:
        """计算密度变化（将歌曲分段统计每段的NPS）
        
        Args:
            notes: 方块列表
            bpm: BPM值
            segment_duration: 段落时长（秒）
            
        Returns:
            List[float]: 每段的NPS值列表
        """
        if not notes:
            return []
        
        # 计算总时长
        total_duration = self._calculate_duration(notes, bpm)
        if total_duration <= 0:
            return []
        
        # 计算段落数量
        num_segments = max(1, int(total_duration / segment_duration))
        segments = [0] * num_segments
        
        # 统计每段的方块数量
        for note in notes:
            note_time_seconds = (note.time * 60.0) / bpm
            segment_index = min(int(note_time_seconds / segment_duration), num_segments - 1)
            segments[segment_index] += 1
        
        # 转换为NPS
        return [count / segment_duration for count in segments]