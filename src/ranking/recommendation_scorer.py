"""推荐度评分系统"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from ..beatsaver.models import BeatSaverMap
from ..matching.smart_matcher import MatchResult
from ..utils.config import Config


@dataclass
class ScoredBeatmap:
    """评分后的铺面"""
    beatmap: BeatSaverMap
    recommendation_score: float
    match_score: float
    download_score: float
    rating_score: float
    upvote_score: float
    recency_score: float
    quality_indicators: List[str]
    warnings: List[str]
    
    @property
    def total_score(self) -> float:
        """总分（匹配分数 + 推荐分数）"""
        return self.match_score + self.recommendation_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "beatmap_id": self.beatmap.id,
            "beatmap_name": self.beatmap.name,
            "song_name": self.beatmap.metadata.song_name,
            "song_author": self.beatmap.metadata.song_author_name,
            "level_author": self.beatmap.metadata.level_author_name,
            "total_score": self.total_score,
            "recommendation_score": self.recommendation_score,
            "match_score": self.match_score,
            "download_score": self.download_score,
            "rating_score": self.rating_score,
            "upvote_score": self.upvote_score,
            "recency_score": self.recency_score,
            "quality_indicators": self.quality_indicators,
            "warnings": self.warnings,
            "downloads": self.beatmap.stats.downloads,
            "rating": self.beatmap.stats.rating,
            "upvote_ratio": self.beatmap.stats.upvote_ratio,
            "ranked": self.beatmap.ranked,
            "max_nps": self.beatmap.max_nps,
        }


class RecommendationScorer:
    """推荐度评分器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        
        # 缓存统计数据，用于归一化
        self._stats_cache = {
            "max_downloads": 0,
            "avg_downloads": 0,
            "max_rating": 1.0,
            "cache_time": None,
            "cache_duration": timedelta(hours=1)  # 缓存1小时
        }
    
    def score_beatmaps(self, match_results: List[MatchResult]) -> List[ScoredBeatmap]:
        """对匹配结果进行评分
        
        Args:
            match_results: 匹配结果列表
            
        Returns:
            List[ScoredBeatmap]: 评分后的铺面列表，按总分降序排列
        """
        if not match_results:
            return []
        
        self.logger.info(f"开始对 {len(match_results)} 个匹配结果进行评分")
        
        # 更新统计数据缓存
        self._update_stats_cache([result.beatmap for result in match_results])
        
        scored_beatmaps = []
        for result in match_results:
            try:
                scored = self._score_single_beatmap(result)
                if scored:
                    scored_beatmaps.append(scored)
            except Exception as e:
                self.logger.warning(f"评分失败: {result.beatmap.id} - {e}")
                continue
        
        # 按总分排序
        scored_beatmaps.sort(key=lambda x: x.total_score, reverse=True)
        
        self.logger.info(f"评分完成，共 {len(scored_beatmaps)} 个有效结果")
        return scored_beatmaps
    
    def score_single_match(self, match_result: MatchResult) -> Optional[ScoredBeatmap]:
        """对单个匹配结果进行评分
        
        Args:
            match_result: 匹配结果
            
        Returns:
            Optional[ScoredBeatmap]: 评分结果，失败返回None
        """
        # 更新统计缓存（单个铺面）
        self._update_stats_cache([match_result.beatmap])
        
        return self._score_single_beatmap(match_result)
    
    def _score_single_beatmap(self, match_result: MatchResult) -> Optional[ScoredBeatmap]:
        """对单个铺面进行评分计算
        
        Args:
            match_result: 匹配结果
            
        Returns:
            Optional[ScoredBeatmap]: 评分结果
        """
        beatmap = match_result.beatmap
        
        try:
            # 检查最低要求
            if not self._meets_minimum_requirements(beatmap):
                self.logger.debug(f"铺面不满足最低要求: {beatmap.id}")
                return None
            
            # 计算各项评分
            download_score = self._calculate_download_score(beatmap)
            rating_score = self._calculate_rating_score(beatmap)
            upvote_score = self._calculate_upvote_score(beatmap)
            recency_score = self._calculate_recency_score(beatmap)
            
            # 计算综合推荐分数
            recommendation_score = (
                download_score * self.config.scoring.download_count_weight +
                rating_score * self.config.scoring.rating_weight +
                upvote_score * self.config.scoring.upvote_ratio_weight +
                recency_score * self.config.scoring.recency_weight
            )
            
            # 生成质量指标和警告
            quality_indicators = self._generate_quality_indicators(beatmap)
            warnings = self._generate_warnings(beatmap)
            
            return ScoredBeatmap(
                beatmap=beatmap,
                recommendation_score=recommendation_score,
                match_score=match_result.score,
                download_score=download_score,
                rating_score=rating_score,
                upvote_score=upvote_score,
                recency_score=recency_score,
                quality_indicators=quality_indicators,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"评分计算失败: {beatmap.id} - {e}")
            return None
    
    def _meets_minimum_requirements(self, beatmap: BeatSaverMap) -> bool:
        """检查铺面是否满足最低要求
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            bool: 是否满足要求
        """
        # 检查最低评分
        if beatmap.stats.rating < self.config.scoring.minimum_rating:
            return False
        
        # 检查最低下载量
        if beatmap.stats.downloads < self.config.scoring.minimum_downloads:
            return False
        
        # 检查是否有有效版本
        if not beatmap.versions:
            return False
        
        return True
    
    def _calculate_download_score(self, beatmap: BeatSaverMap) -> float:
        """计算下载量分数
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            float: 下载量分数 (0.0-1.0)
        """
        downloads = beatmap.stats.downloads
        max_downloads = self._stats_cache["max_downloads"]
        
        if max_downloads <= 0:
            return 0.5  # 默认中等分数
        
        # 使用对数标准化，避免热门铺面占绝对优势
        if downloads <= 0:
            return 0.0
        
        # 对数标准化
        log_downloads = math.log(downloads + 1)
        log_max = math.log(max_downloads + 1)
        
        score = log_downloads / log_max
        return min(score, 1.0)
    
    def _calculate_rating_score(self, beatmap: BeatSaverMap) -> float:
        """计算评分分数
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            float: 评分分数 (0.0-1.0)
        """
        rating = beatmap.stats.rating
        
        # BeatSaver的评分通常是0-1范围
        score = rating
        return min(max(score, 0.0), 1.0)
    
    def _calculate_upvote_score(self, beatmap: BeatSaverMap) -> float:
        """计算点赞率分数
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            float: 点赞率分数 (0.0-1.0)
        """
        upvote_ratio = beatmap.stats.upvote_ratio
        
        # 考虑投票总数，投票数太少的铺面降低权重
        total_votes = beatmap.stats.upvotes + beatmap.stats.downvotes
        if total_votes < 10:
            # 投票数不足，降低可信度
            confidence = total_votes / 10.0
            return upvote_ratio * confidence + 0.5 * (1 - confidence)
        
        return upvote_ratio
    
    def _calculate_recency_score(self, beatmap: BeatSaverMap) -> float:
        """计算时间新旧分数
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            float: 时间分数 (0.0-1.0)
        """
        now = datetime.now(beatmap.uploaded.tzinfo)
        age_days = (now - beatmap.uploaded).days
        
        # 时间衰减函数：6个月内为1.0，之后逐渐衰减
        if age_days <= 0:
            return 1.0
        elif age_days <= 180:  # 6个月内
            return 1.0
        elif age_days <= 365:  # 1年内
            return 0.8
        elif age_days <= 730:  # 2年内
            return 0.6
        elif age_days <= 1095:  # 3年内
            return 0.4
        else:  # 3年以上
            return 0.2
    
    def _generate_quality_indicators(self, beatmap: BeatSaverMap) -> List[str]:
        """生成质量指标
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            List[str]: 质量指标列表
        """
        indicators = []
        
        # 排位状态
        if beatmap.ranked:
            indicators.append("🏆 排位铺面")
        elif beatmap.qualified:
            indicators.append("⭐ 审核通过")
        
        # 下载量指标
        downloads = beatmap.stats.downloads
        if downloads >= 10000:
            indicators.append("🔥 热门铺面 (10k+ 下载)")
        elif downloads >= 5000:
            indicators.append("📈 受欢迎 (5k+ 下载)")
        elif downloads >= 1000:
            indicators.append("👍 较受欢迎 (1k+ 下载)")
        
        # 评分指标
        rating = beatmap.stats.rating
        if rating >= 0.9:
            indicators.append("⭐ 高评分 (90%+)")
        elif rating >= 0.8:
            indicators.append("✨ 好评 (80%+)")
        
        # 点赞率
        upvote_ratio = beatmap.stats.upvote_ratio
        total_votes = beatmap.stats.upvotes + beatmap.stats.downvotes
        if total_votes >= 50 and upvote_ratio >= 0.9:
            indicators.append("👏 极受好评 (90%+ 点赞)")
        elif total_votes >= 20 and upvote_ratio >= 0.8:
            indicators.append("👍 受好评 (80%+ 点赞)")
        
        # 难度多样性
        if beatmap.difficulty_count >= 5:
            indicators.append("🎯 多难度选择")
        
        # 创作者信誉
        if beatmap.uploader.unique_set:
            indicators.append("🎨 知名创作者")
        
        return indicators
    
    def _generate_warnings(self, beatmap: BeatSaverMap) -> List[str]:
        """生成警告信息
        
        Args:
            beatmap: 铺面信息
            
        Returns:
            List[str]: 警告列表
        """
        warnings = []
        
        # 自动生成警告
        if beatmap.automapper:
            warnings.append("⚠️ 自动生成铺面")
        
        # 评分过低
        if beatmap.stats.rating < 0.6:
            warnings.append(f"⚠️ 评分较低 ({beatmap.stats.rating:.1%})")
        
        # 下载量过少
        if beatmap.stats.downloads < 100:
            warnings.append("⚠️ 下载量较少，可能为新作品")
        
        # 负评过多
        upvote_ratio = beatmap.stats.upvote_ratio
        if upvote_ratio < 0.6:
            warnings.append(f"⚠️ 负评较多 ({upvote_ratio:.1%} 点赞率)")
        
        # 过于古老
        age_days = (datetime.now(beatmap.uploaded.tzinfo) - beatmap.uploaded).days
        if age_days > 1095:  # 3年以上
            warnings.append(f"⚠️ 较旧的铺面 ({age_days // 365} 年前)")
        
        return warnings
    
    def _update_stats_cache(self, beatmaps: List[BeatSaverMap]) -> None:
        """更新统计数据缓存
        
        Args:
            beatmaps: 铺面列表
        """
        now = datetime.now()
        
        # 检查缓存是否过期
        if (self._stats_cache["cache_time"] is None or 
            now - self._stats_cache["cache_time"] > self._stats_cache["cache_duration"]):
            
            # 重新计算统计数据
            if beatmaps:
                downloads = [bm.stats.downloads for bm in beatmaps]
                ratings = [bm.stats.rating for bm in beatmaps if bm.stats.rating > 0]
                
                self._stats_cache["max_downloads"] = max(downloads) if downloads else 0
                self._stats_cache["avg_downloads"] = sum(downloads) / len(downloads) if downloads else 0
                self._stats_cache["max_rating"] = max(ratings) if ratings else 1.0
                self._stats_cache["cache_time"] = now
                
                self.logger.debug(f"统计缓存更新: max_downloads={self._stats_cache['max_downloads']}, "
                                f"avg_downloads={self._stats_cache['avg_downloads']:.1f}, "
                                f"max_rating={self._stats_cache['max_rating']}")
    
    def get_top_recommendations(
        self,
        scored_beatmaps: List[ScoredBeatmap],
        count: int = 1
    ) -> List[ScoredBeatmap]:
        """获取顶级推荐
        
        Args:
            scored_beatmaps: 已评分的铺面列表
            count: 返回数量
            
        Returns:
            List[ScoredBeatmap]: 顶级推荐列表
        """
        if not scored_beatmaps:
            return []
        
        # 已按分数排序，直接返回前N个
        return scored_beatmaps[:count]