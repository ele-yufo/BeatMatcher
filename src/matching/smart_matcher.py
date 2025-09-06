"""智能匹配引擎"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from loguru import logger

from .string_matcher import StringMatcher
from ..audio.models import AudioFile
from ..beatsaver.models import BeatSaverMap
from ..utils.config import Config
from ..utils.exceptions import MatchingError


@dataclass
class MatchResult:
    """匹配结果"""
    beatmap: BeatSaverMap
    score: float
    artist_similarity: float
    title_similarity: float
    confidence: str  # "high", "medium", "low"
    reasons: List[str]  # 匹配原因列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "beatmap_id": self.beatmap.id,
            "beatmap_name": self.beatmap.name,
            "song_name": self.beatmap.metadata.song_name,
            "song_author": self.beatmap.metadata.song_author_name,
            "level_author": self.beatmap.metadata.level_author_name,
            "score": self.score,
            "artist_similarity": self.artist_similarity,
            "title_similarity": self.title_similarity,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "downloads": self.beatmap.stats.downloads,
            "rating": self.beatmap.stats.rating,
        }


class SmartMatcher:
    """智能匹配引擎"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        self.string_matcher = StringMatcher(
            normalize_case=config.matching.normalize_case,
            remove_special_chars=config.matching.remove_special_chars
        )
    
    def find_best_match(
        self,
        audio_file: AudioFile,
        search_results: List[BeatSaverMap]
    ) -> Optional[MatchResult]:
        """找到最佳匹配的铺面
        
        Args:
            audio_file: 本地音频文件
            search_results: 搜索结果列表
            
        Returns:
            Optional[MatchResult]: 最佳匹配结果，无匹配返回None
        """
        if not search_results:
            self.logger.warning(f"搜索结果为空: {audio_file}")
            return None
        
        self.logger.info(f"开始匹配: {audio_file.artist} - {audio_file.title}")
        self.logger.debug(f"候选铺面数量: {len(search_results)}")
        
        # 计算所有候选项的匹配分数
        match_results = []
        for beatmap in search_results:
            try:
                result = self._calculate_match_score(audio_file, beatmap)
                if result and result.score >= self.config.matching.minimum_similarity:
                    match_results.append(result)
            except Exception as e:
                self.logger.warning(f"计算匹配分数失败: {beatmap.id} - {e}")
                continue
        
        if not match_results:
            self.logger.warning(f"未找到满足最低相似度要求的匹配: {audio_file}")
            return None
        
        # 按分数排序
        match_results.sort(key=lambda x: x.score, reverse=True)
        best_match = match_results[0]
        
        self.logger.info(f"找到最佳匹配: {best_match.beatmap.name} (分数: {best_match.score:.3f})")
        self.logger.debug(f"匹配详情: {best_match.reasons}")
        
        return best_match
    
    def find_all_matches(
        self,
        audio_file: AudioFile,
        search_results: List[BeatSaverMap],
        max_results: int = 5
    ) -> List[MatchResult]:
        """找到所有符合条件的匹配
        
        Args:
            audio_file: 本地音频文件
            search_results: 搜索结果列表
            max_results: 最大返回结果数
            
        Returns:
            List[MatchResult]: 匹配结果列表，按分数降序排列
        """
        if not search_results:
            return []
        
        match_results = []
        for beatmap in search_results:
            try:
                result = self._calculate_match_score(audio_file, beatmap)
                if result and result.score >= self.config.matching.minimum_similarity:
                    match_results.append(result)
            except Exception as e:
                self.logger.warning(f"计算匹配分数失败: {beatmap.id} - {e}")
                continue
        
        # 按分数排序并限制数量
        match_results.sort(key=lambda x: x.score, reverse=True)
        return match_results[:max_results]
    
    def _calculate_match_score(
        self,
        audio_file: AudioFile,
        beatmap: BeatSaverMap
    ) -> Optional[MatchResult]:
        """计算匹配分数
        
        Args:
            audio_file: 本地音频文件
            beatmap: BeatSaver铺面
            
        Returns:
            Optional[MatchResult]: 匹配结果，失败返回None
        """
        try:
            # 标准化字符串
            local_artist = self.string_matcher.normalize_artist_name(audio_file.artist)
            local_title = self.string_matcher.normalize_title(audio_file.title)
            
            beatmap_artist = self.string_matcher.normalize_artist_name(beatmap.metadata.song_author_name)
            beatmap_title = self.string_matcher.normalize_title(beatmap.metadata.song_name)
            
            # 计算相似度
            artist_similarity = self.string_matcher.similarity(local_artist, beatmap_artist)
            title_similarity = self.string_matcher.similarity(local_title, beatmap_title)
            
            # 计算综合分数
            score = (artist_similarity * self.config.matching.artist_weight +
                    title_similarity * self.config.matching.title_weight)
            
            # 判断置信度
            confidence = self._determine_confidence(artist_similarity, title_similarity, score)
            
            # 生成匹配原因
            reasons = self._generate_match_reasons(
                local_artist, local_title,
                beatmap_artist, beatmap_title,
                artist_similarity, title_similarity
            )
            
            return MatchResult(
                beatmap=beatmap,
                score=score,
                artist_similarity=artist_similarity,
                title_similarity=title_similarity,
                confidence=confidence,
                reasons=reasons
            )
            
        except Exception as e:
            self.logger.error(f"计算匹配分数时出错: {e}")
            return None
    
    def _determine_confidence(
        self,
        artist_similarity: float,
        title_similarity: float,
        overall_score: float
    ) -> str:
        """判断匹配置信度
        
        Args:
            artist_similarity: 艺术家相似度
            title_similarity: 标题相似度
            overall_score: 综合分数
            
        Returns:
            str: 置信度等级
        """
        # 高置信度：两个维度都很高
        if artist_similarity >= 0.9 and title_similarity >= 0.9:
            return "high"
        
        # 高置信度：综合分数很高且没有太大偏差
        if overall_score >= 0.9 and min(artist_similarity, title_similarity) >= 0.8:
            return "high"
        
        # 中置信度：综合分数良好
        if overall_score >= 0.7 and min(artist_similarity, title_similarity) >= 0.6:
            return "medium"
        
        # 低置信度：其他情况
        return "low"
    
    def _generate_match_reasons(
        self,
        local_artist: str,
        local_title: str,
        beatmap_artist: str,
        beatmap_title: str,
        artist_similarity: float,
        title_similarity: float
    ) -> List[str]:
        """生成匹配原因说明
        
        Args:
            local_artist: 本地艺术家
            local_title: 本地标题
            beatmap_artist: 铺面艺术家
            beatmap_title: 铺面标题
            artist_similarity: 艺术家相似度
            title_similarity: 标题相似度
            
        Returns:
            List[str]: 匹配原因列表
        """
        reasons = []
        
        # 艺术家匹配
        if artist_similarity >= 0.95:
            reasons.append(f"艺术家完全匹配: '{local_artist}' ≈ '{beatmap_artist}'")
        elif artist_similarity >= 0.8:
            reasons.append(f"艺术家高度匹配: '{local_artist}' ≈ '{beatmap_artist}' ({artist_similarity:.2f})")
        elif artist_similarity >= 0.6:
            reasons.append(f"艺术家部分匹配: '{local_artist}' ≈ '{beatmap_artist}' ({artist_similarity:.2f})")
        else:
            reasons.append(f"艺术家匹配度较低: '{local_artist}' ≈ '{beatmap_artist}' ({artist_similarity:.2f})")
        
        # 标题匹配
        if title_similarity >= 0.95:
            reasons.append(f"标题完全匹配: '{local_title}' ≈ '{beatmap_title}'")
        elif title_similarity >= 0.8:
            reasons.append(f"标题高度匹配: '{local_title}' ≈ '{beatmap_title}' ({title_similarity:.2f})")
        elif title_similarity >= 0.6:
            reasons.append(f"标题部分匹配: '{local_title}' ≈ '{beatmap_title}' ({title_similarity:.2f})")
        else:
            reasons.append(f"标题匹配度较低: '{local_title}' ≈ '{beatmap_title}' ({title_similarity:.2f})")
        
        return reasons
    
    def batch_match(
        self,
        audio_files: List[AudioFile],
        all_search_results: Dict[str, List[BeatSaverMap]]
    ) -> Dict[str, Optional[MatchResult]]:
        """批量匹配
        
        Args:
            audio_files: 音频文件列表
            all_search_results: 所有搜索结果，键为音频文件的标识
            
        Returns:
            Dict[str, Optional[MatchResult]]: 匹配结果字典
        """
        results = {}
        
        for audio_file in audio_files:
            file_key = f"{audio_file.artist} - {audio_file.title}"
            search_results = all_search_results.get(file_key, [])
            
            try:
                best_match = self.find_best_match(audio_file, search_results)
                results[file_key] = best_match
                
                if best_match:
                    self.logger.info(f"匹配成功: {file_key} -> {best_match.beatmap.name}")
                else:
                    self.logger.warning(f"未找到匹配: {file_key}")
                    
            except Exception as e:
                self.logger.error(f"批量匹配失败: {file_key} - {e}")
                results[file_key] = None
        
        success_count = sum(1 for result in results.values() if result is not None)
        self.logger.info(f"批量匹配完成: {success_count}/{len(audio_files)} 成功")
        
        return results