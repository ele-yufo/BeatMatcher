"""文件夹管理器"""

import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger

from ..difficulty.models import BeatmapAnalysis, DifficultyCategory
from ..difficulty.density_analyzer import DensityAnalyzer
from ..utils.config import Config
from ..utils.exceptions import FileOrganizationError


class FolderManager:
    """文件夹管理器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logger.bind(name=self.__class__.__name__)
        self.density_analyzer = DensityAnalyzer(config)
    
    def organize_by_difficulty(
        self, 
        beatmap_path: Path, 
        analysis: Optional[BeatmapAnalysis] = None
    ) -> Optional[Path]:
        """根据难度组织铺面文件
        
        Args:
            beatmap_path: 铺面文件路径
            analysis: 预先分析的结果，如果为None则重新分析
            
        Returns:
            Optional[Path]: 移动后的文件路径，失败返回None
        """
        if not self.config.files.organize_by_difficulty:
            self.logger.debug("难度分类功能已禁用")
            return beatmap_path
        
        try:
            # 如果没有提供分析结果，则进行分析
            if analysis is None:
                analysis = self.density_analyzer.analyze_beatmap(beatmap_path)
                if not analysis:
                    self.logger.warning(f"无法分析铺面难度，跳过分类: {beatmap_path}")
                    return beatmap_path
            
            # 确定目标目录
            category = analysis.primary_difficulty_category
            target_dir = self._get_category_directory(beatmap_path.parent, category)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成目标文件路径
            target_path = target_dir / beatmap_path.name
            
            # 如果目标文件已存在，处理重名
            if target_path.exists() and target_path != beatmap_path:
                target_path = self._handle_duplicate_filename(target_path)
            
            # 移动文件 - 使用Path对象确保跨平台兼容
            if target_path != beatmap_path:
                self.logger.info(f"移动铺面到难度文件夹: {beatmap_path.name} -> {category.value}")
                shutil.move(beatmap_path, target_path)
                return target_path
            else:
                self.logger.debug(f"铺面已在正确位置: {beatmap_path}")
                return beatmap_path
                
        except Exception as e:
            self.logger.error(f"组织文件失败: {beatmap_path} - {e}")
            raise FileOrganizationError(str(beatmap_path), "", str(e))
    
    def organize_batch(
        self, 
        beatmap_paths: List[Path], 
        analyses: Optional[Dict[str, BeatmapAnalysis]] = None
    ) -> Dict[str, Optional[Path]]:
        """批量组织铺面文件
        
        Args:
            beatmap_paths: 铺面文件路径列表
            analyses: 预先分析的结果字典
            
        Returns:
            Dict[str, Optional[Path]]: 组织结果字典
        """
        results = {}
        analyses = analyses or {}
        
        self.logger.info(f"开始批量组织 {len(beatmap_paths)} 个铺面文件")
        
        for i, path in enumerate(beatmap_paths, 1):
            self.logger.info(f"组织进度: {i}/{len(beatmap_paths)} - {path.name}")
            
            try:
                # 获取对应的分析结果
                analysis = analyses.get(str(path))
                
                # 组织文件
                new_path = self.organize_by_difficulty(path, analysis)
                results[str(path)] = new_path
                
            except Exception as e:
                self.logger.error(f"批量组织失败: {path} - {e}")
                results[str(path)] = None
        
        success_count = sum(1 for result in results.values() if result is not None)
        self.logger.info(f"批量组织完成: {success_count}/{len(beatmap_paths)} 成功")
        
        return results
    
    def create_difficulty_structure(self, base_dir: Path) -> Dict[DifficultyCategory, Path]:
        """创建难度目录结构
        
        Args:
            base_dir: 基础目录
            
        Returns:
            Dict[DifficultyCategory, Path]: 难度类别到目录路径的映射
        """
        structure = {}
        
        for category in DifficultyCategory:
            category_dir = self._get_category_directory(base_dir, category)
            category_dir.mkdir(parents=True, exist_ok=True)
            structure[category] = category_dir
            self.logger.debug(f"创建难度目录: {category_dir}")
        
        return structure
    
    def get_category_statistics(self, base_dir: Path) -> Dict[str, Any]:
        """获取各难度分类的统计信息
        
        Args:
            base_dir: 基础目录
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            "categories": {},
            "total_files": 0,
            "unorganized_files": 0
        }
        
        # 统计各难度目录的文件数
        for category in DifficultyCategory:
            category_dir = self._get_category_directory(base_dir, category)
            if category_dir.exists():
                file_count = len(list(category_dir.glob("*.zip")))
                stats["categories"][category.value] = {
                    "count": file_count,
                    "directory": str(category_dir)
                }
                stats["total_files"] += file_count
            else:
                stats["categories"][category.value] = {
                    "count": 0,
                    "directory": str(category_dir)
                }
        
        # 统计根目录的未分类文件
        unorganized_files = list(base_dir.glob("*.zip"))
        stats["unorganized_files"] = len(unorganized_files)
        stats["total_files"] += stats["unorganized_files"]
        
        return stats
    
    def cleanup_empty_directories(self, base_dir: Path) -> int:
        """清理空的难度目录
        
        Args:
            base_dir: 基础目录
            
        Returns:
            int: 删除的空目录数量
        """
        removed_count = 0
        
        for category in DifficultyCategory:
            category_dir = self._get_category_directory(base_dir, category)
            
            if category_dir.exists() and category_dir.is_dir():
                # 检查目录是否为空
                if not any(category_dir.iterdir()):
                    try:
                        category_dir.rmdir()
                        self.logger.info(f"删除空目录: {category_dir}")
                        removed_count += 1
                    except OSError as e:
                        self.logger.warning(f"删除目录失败: {category_dir} - {e}")
        
        return removed_count
    
    def move_to_category(
        self, 
        file_path: Path, 
        target_category: DifficultyCategory,
        base_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """手动将文件移动到指定难度分类
        
        Args:
            file_path: 源文件路径
            target_category: 目标难度分类
            base_dir: 基础目录，默认使用文件所在目录
            
        Returns:
            Optional[Path]: 移动后的文件路径，失败返回None
        """
        if base_dir is None:
            base_dir = file_path.parent
        
        try:
            # 确定目标目录
            target_dir = self._get_category_directory(base_dir, target_category)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成目标文件路径
            target_path = target_dir / file_path.name
            
            # 处理重名文件
            if target_path.exists() and target_path != file_path:
                target_path = self._handle_duplicate_filename(target_path)
            
            # 移动文件 - 使用Path对象确保跨平台兼容
            if target_path != file_path:
                self.logger.info(f"手动移动文件: {file_path.name} -> {target_category.value}")
                shutil.move(file_path, target_path)
                return target_path
            else:
                return file_path
                
        except Exception as e:
            self.logger.error(f"手动移动文件失败: {file_path} - {e}")
            return None
    
    def _get_category_directory(self, base_dir: Path, category: DifficultyCategory) -> Path:
        """获取难度分类目录路径
        
        Args:
            base_dir: 基础目录
            category: 难度分类
            
        Returns:
            Path: 分类目录路径
        """
        folder_name = self.density_analyzer.get_category_folder_name(category)
        return base_dir / folder_name
    
    def _handle_duplicate_filename(self, target_path: Path) -> Path:
        """处理重复文件名
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            Path: 处理后的文件路径
        """
        if not target_path.exists():
            return target_path
        
        # 生成新文件名
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                self.logger.debug(f"重命名重复文件: {target_path.name} -> {new_name}")
                return new_path
            counter += 1
            
            # 防止无限循环
            if counter > 1000:
                raise FileOrganizationError(
                    str(target_path), 
                    "", 
                    "无法生成唯一文件名"
                )
    
    def restore_original_structure(self, base_dir: Path) -> int:
        """恢复原始文件结构（将分类文件移回根目录）
        
        Args:
            base_dir: 基础目录
            
        Returns:
            int: 移动的文件数量
        """
        moved_count = 0
        
        self.logger.info(f"开始恢复原始文件结构: {base_dir}")
        
        # 遍历所有难度目录
        for category in DifficultyCategory:
            category_dir = self._get_category_directory(base_dir, category)
            
            if not category_dir.exists():
                continue
            
            # 移动目录中的所有文件
            for file_path in category_dir.glob("*"):
                if file_path.is_file():
                    try:
                        target_path = base_dir / file_path.name
                        
                        # 处理重名文件
                        if target_path.exists():
                            target_path = self._handle_duplicate_filename(target_path)
                        
                        shutil.move(file_path, target_path)
                        moved_count += 1
                        self.logger.debug(f"移动文件: {file_path.name} -> 根目录")
                        
                    except Exception as e:
                        self.logger.error(f"移动文件失败: {file_path} - {e}")
        
        # 清理空目录
        empty_dirs_removed = self.cleanup_empty_directories(base_dir)
        
        self.logger.info(f"恢复完成: 移动 {moved_count} 个文件，删除 {empty_dirs_removed} 个空目录")
        return moved_count