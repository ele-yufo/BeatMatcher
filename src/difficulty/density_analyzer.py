"""难度密度分析器"""

from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

from .beatmap_parser import BeatmapParser
from .models import BeatmapAnalysis, DifficultyCategory, DifficultyStats
from ..utils.config import Config
from ..utils.exceptions import BeatmapParsingError


class DensityAnalyzer:
    """难度密度分析器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        self.parser = BeatmapParser()
    
    def analyze_beatmap(self, beatmap_path: Path) -> Optional[BeatmapAnalysis]:
        """分析谱面难度
        
        Args:
            beatmap_path: 谱面文件路径（ZIP文件或解压后的目录）
            
        Returns:
            Optional[BeatmapAnalysis]: 分析结果，失败返回None
        """
        try:
            # 检查文件大小，跳过超大谱面避免卡死
            if beatmap_path.is_file():
                file_size = beatmap_path.stat().st_size
                max_size = 50 * 1024 * 1024  # 50MB限制
                if file_size > max_size:
                    self.logger.warning(f"谱面文件过大 ({file_size/1024/1024:.1f}MB)，跳过分析: {beatmap_path.name}")
                    return None
            
            # 确定处理路径
            if beatmap_path.is_file() and beatmap_path.suffix.lower() == '.zip':
                # 如果是ZIP文件，需要先解压
                from ..beatsaver.downloader import BeatmapDownloader
                downloader = BeatmapDownloader(self.config)
                extracted_dir = downloader.extract_beatmap(beatmap_path)
                if not extracted_dir:
                    raise BeatmapParsingError(str(beatmap_path), "ZIP文件解压失败")
                
                # 验证解压路径的安全性，防止目录遍历攻击
                if not str(extracted_dir.resolve()).startswith(str(beatmap_path.parent.resolve())):
                    raise BeatmapParsingError(str(beatmap_path), "ZIP文件包含不安全的路径，可能存在目录遍历攻击")
                
                analysis_path = extracted_dir
            elif beatmap_path.is_dir():
                # 如果是目录，直接分析
                analysis_path = beatmap_path
            else:
                raise BeatmapParsingError(str(beatmap_path), "无效的谱面路径")
            
            self.logger.info(f"开始分析谱面难度: {analysis_path}")
            
            # 解析谱面 - 添加超时保护
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("谱面分析超时")
            
            # 设置30秒超时
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            try:
                analysis = self.parser.parse_beatmap_directory(analysis_path)
                signal.alarm(0)  # 取消超时
                
                if not analysis:
                    return None
            except TimeoutError:
                signal.alarm(0)  # 取消超时
                self.logger.warning(f"谱面分析超时，跳过: {beatmap_path.name}")
                return None
            
            # 记录分析结果
            self.logger.info(f"谱面分析完成: {analysis.song_name}")
            self.logger.info(f"  难度数量: {len(analysis.difficulties)}")
            self.logger.info(f"  最大NPS: {analysis.max_nps:.2f}")
            self.logger.info(f"  主要难度分类: {analysis.primary_difficulty_category.value}")
            
            for diff in analysis.difficulties:
                self.logger.debug(f"  {diff.difficulty_name} ({diff.characteristic}): "
                               f"NPS={diff.nps:.2f}, 方块数={diff.notes_count}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"分析铺面失败: {beatmap_path} - {e}")
            return None
    
    def get_difficulty_category(self, analysis: BeatmapAnalysis) -> DifficultyCategory:
        """获取铺面的难度分类
        
        Args:
            analysis: 铺面分析结果
            
        Returns:
            DifficultyCategory: 难度分类
        """
        return analysis.primary_difficulty_category
    
    def get_category_folder_name(self, category: DifficultyCategory) -> str:
        """获取难度分类对应的文件夹名称
        
        Args:
            category: 难度分类
            
        Returns:
            str: 文件夹名称
        """
        category_config = self.config.difficulty.categories.get(category.value)
        if category_config:
            return category_config.folder
        
        # 默认文件夹名称
        folder_names = {
            DifficultyCategory.EASY: "Easy (0-4 blocks/s)",
            DifficultyCategory.MEDIUM: "Medium (4-7 blocks/s)",
            DifficultyCategory.HARD: "Hard (7+ blocks/s)"
        }
        return folder_names.get(category, "Unknown")
    
    def analyze_batch(self, beatmap_paths: List[Path]) -> Dict[str, Optional[BeatmapAnalysis]]:
        """批量分析铺面难度
        
        Args:
            beatmap_paths: 铺面路径列表
            
        Returns:
            Dict[str, Optional[BeatmapAnalysis]]: 分析结果字典
        """
        results = {}
        
        self.logger.info(f"开始批量分析 {len(beatmap_paths)} 个铺面")
        
        for i, path in enumerate(beatmap_paths, 1):
            self.logger.info(f"分析进度: {i}/{len(beatmap_paths)} - {path.name}")
            
            try:
                analysis = self.analyze_beatmap(path)
                results[str(path)] = analysis
            except Exception as e:
                self.logger.error(f"批量分析失败: {path} - {e}")
                results[str(path)] = None
        
        success_count = sum(1 for result in results.values() if result is not None)
        self.logger.info(f"批量分析完成: {success_count}/{len(beatmap_paths)} 成功")
        
        return results
    
    def get_statistics(self, analyses: List[BeatmapAnalysis]) -> Dict[str, any]:
        """获取分析统计信息
        
        Args:
            analyses: 分析结果列表
            
        Returns:
            Dict: 统计信息
        """
        if not analyses:
            return {
                "total_count": 0,
                "category_distribution": {},
                "average_nps": 0.0,
                "nps_range": {"min": 0.0, "max": 0.0}
            }
        
        # 统计难度分类分布
        category_count = {
            DifficultyCategory.EASY.value: 0,
            DifficultyCategory.MEDIUM.value: 0,
            DifficultyCategory.HARD.value: 0
        }
        
        nps_values = []
        
        for analysis in analyses:
            category = analysis.primary_difficulty_category
            category_count[category.value] += 1
            nps_values.append(analysis.max_nps)
        
        # 计算NPS统计
        avg_nps = sum(nps_values) / len(nps_values) if nps_values else 0.0
        min_nps = min(nps_values) if nps_values else 0.0
        max_nps = max(nps_values) if nps_values else 0.0
        
        return {
            "total_count": len(analyses),
            "category_distribution": category_count,
            "average_nps": avg_nps,
            "nps_range": {"min": min_nps, "max": max_nps},
            "nps_values": nps_values
        }
    
    def find_similar_difficulties(
        self, 
        target_analysis: BeatmapAnalysis, 
        other_analyses: List[BeatmapAnalysis],
        nps_threshold: float = 1.0
    ) -> List[BeatmapAnalysis]:
        """查找相似难度的铺面
        
        Args:
            target_analysis: 目标铺面分析
            other_analyses: 其他铺面分析列表
            nps_threshold: NPS相似度阈值
            
        Returns:
            List[BeatmapAnalysis]: 相似难度的铺面列表
        """
        target_nps = target_analysis.max_nps
        similar_beatmaps = []
        
        for analysis in other_analyses:
            if analysis.beatmap_id == target_analysis.beatmap_id:
                continue  # 跳过自己
            
            nps_diff = abs(analysis.max_nps - target_nps)
            if nps_diff <= nps_threshold:
                similar_beatmaps.append(analysis)
        
        # 按NPS相似度排序
        similar_beatmaps.sort(key=lambda x: abs(x.max_nps - target_nps))
        
        return similar_beatmaps
    
    def recommend_difficulty_progression(self, analyses: List[BeatmapAnalysis]) -> List[BeatmapAnalysis]:
        """推荐难度递进顺序
        
        Args:
            analyses: 铺面分析列表
            
        Returns:
            List[BeatmapAnalysis]: 按难度递进排序的铺面列表
        """
        # 按最大NPS排序
        sorted_analyses = sorted(analyses, key=lambda x: x.max_nps)
        
        self.logger.info(f"难度递进推荐顺序 ({len(sorted_analyses)} 个铺面):")
        for i, analysis in enumerate(sorted_analyses, 1):
            category = analysis.primary_difficulty_category.value
            self.logger.info(f"  {i}. {analysis.song_name} - NPS: {analysis.max_nps:.2f} ({category})")
        
        return sorted_analyses