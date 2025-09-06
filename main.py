#!/usr/bin/env python3
"""
BeatSaber Downloader - 自动下载本地音乐对应的Beat Saber铺面
主入口文件
"""

import asyncio
import argparse
from pathlib import Path
from tqdm import tqdm
from src.utils.logger import setup_logger
from src.utils.config import Config
from src.audio.audio_scanner import AudioScanner
from src.beatsaver.searcher import BeatSaverSearcher
from src.matching.smart_matcher import SmartMatcher
from src.ranking.recommendation_scorer import RecommendationScorer
from src.beatsaver.downloader import BeatmapDownloader
from src.difficulty.density_analyzer import DensityAnalyzer
from src.organizer.folder_manager import FolderManager


async def process_single_audio_file(
    audio_file,
    searcher,
    matcher,
    scorer,
    downloader,
    analyzer,
    organizer,
    output_dir,
    logger
):
    """处理单个音频文件的完整流程"""
    try:
        logger.info(f"处理文件: {audio_file.title} - {audio_file.artist}")
        
        # 1. 搜索铺面
        search_results = await searcher.search(audio_file.title, audio_file.artist)
        if not search_results:
            logger.warning(f"未找到匹配的铺面: {audio_file.title}")
            return None
        
        # 2. 智能匹配
        best_matches = matcher.find_all_matches(audio_file, search_results, max_results=3)
        if not best_matches:
            logger.warning(f"匹配度过低: {audio_file.title}")
            return None
        
        # 3. 评分排序
        scored_maps = scorer.score_beatmaps(best_matches)
        if not scored_maps:
            logger.warning(f"评分失败: {audio_file.title}")
            return None
        
        # 4. 选择最佳铺面
        best_scored = scored_maps[0]
        logger.info(f"选择铺面: {best_scored.beatmap.name} (匹配分数: {best_scored.match_score:.3f}, 推荐分数: {best_scored.recommendation_score:.3f})")
        
        # 5. 下载铺面
        downloaded_path = await downloader.download(best_scored.beatmap, output_dir)
        if not downloaded_path:
            logger.error(f"下载失败: {best_scored.beatmap.name}")
            return None
        
        # 6. 分析难度
        analysis = analyzer.analyze_beatmap(downloaded_path)
        if not analysis:
            logger.warning(f"难度分析失败，使用默认分类: {downloaded_path}")
            # 仍然移动到输出目录，但不进行难度分类
            return {
                'audio_file': audio_file,
                'beatmap': best_scored.beatmap,
                'downloaded_path': downloaded_path,
                'analysis': None
            }
        
        # 7. 组织文件夹
        final_path = organizer.organize_by_difficulty(downloaded_path, analysis)
        
        logger.info(f"完成处理: {audio_file.title} -> {analysis.primary_difficulty_category.value}")
        
        return {
            'audio_file': audio_file,
            'beatmap': best_scored.beatmap,
            'downloaded_path': downloaded_path,
            'final_path': final_path,
            'analysis': analysis
        }
        
    except Exception as e:
        logger.error(f"处理音频文件失败: {audio_file.title} - {e}")
        return None


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="BeatSaber Downloader - 自动下载本地音乐对应的Beat Saber铺面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps --config my_config.yaml
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps --max-files 10
        """
    )
    parser.add_argument("--music-dir", type=str, required=True, help="本地音乐目录路径")
    parser.add_argument("--output-dir", type=str, required=True, help="输出铺面目录路径")
    parser.add_argument("--config", type=str, default="config/settings.yaml", help="配置文件路径")
    parser.add_argument("--max-files", type=int, help="最大处理文件数（用于测试）")
    parser.add_argument("--dry-run", action="store_true", help="只搜索和匹配，不下载文件")
    
    args = parser.parse_args()
    
    try:
        # 初始化配置和日志
        config = Config(args.config)
        config.validate()  # 验证配置
        logger = setup_logger(config.log_level, config.log_file)
        
        logger.info("=" * 60)
        logger.info("开始BeatSaber铺面下载任务")
        logger.info(f"音乐目录: {args.music_dir}")
        logger.info(f"输出目录: {args.output_dir}")
        logger.info(f"配置文件: {args.config}")
        if args.max_files:
            logger.info(f"最大文件数: {args.max_files}")
        if args.dry_run:
            logger.info("模拟运行模式（不下载文件）")
        logger.info("=" * 60)
        
        # 检查目录
        music_dir = Path(args.music_dir)
        output_dir = Path(args.output_dir)
        
        if not music_dir.exists():
            logger.error(f"音乐目录不存在: {music_dir}")
            return
        
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 扫描本地音乐
        logger.info("步骤 1/7: 扫描本地音乐文件...")
        scanner = AudioScanner(config)
        audio_files = await scanner.scan_directory(music_dir)
        
        if not audio_files:
            logger.warning("未找到任何音频文件")
            return
        
        # 限制处理数量（用于测试）
        if args.max_files:
            audio_files = audio_files[:args.max_files]
        
        logger.info(f"发现 {len(audio_files)} 个音频文件")
        
        # 2. 初始化组件
        logger.info("步骤 2/7: 初始化组件...")
        async with BeatSaverSearcher(config) as searcher:
            matcher = SmartMatcher(config)
            scorer = RecommendationScorer(config)
            
            if not args.dry_run:
                async with BeatmapDownloader(config) as downloader:
                    analyzer = DensityAnalyzer(config)
                    organizer = FolderManager(config)
                    
                    # 创建难度目录结构
                    organizer.create_difficulty_structure(output_dir)
                    
                    # 3-7. 处理音频文件
                    logger.info(f"步骤 3-7: 处理 {len(audio_files)} 个音频文件...")
                    
                    results = []
                    with tqdm(total=len(audio_files), desc="处理进度") as pbar:
                        for audio_file in audio_files:
                            result = await process_single_audio_file(
                                audio_file, searcher, matcher, scorer, downloader,
                                analyzer, organizer, output_dir, logger
                            )
                            results.append(result)
                            pbar.update(1)
                    
                    # 统计结果
                    successful_results = [r for r in results if r is not None]
                    success_count = len(successful_results)
                    
                    logger.info("=" * 60)
                    logger.info(f"任务完成！处理结果: {success_count}/{len(audio_files)} 成功")
                    
                    if successful_results:
                        # 统计难度分布
                        category_stats = {}
                        for result in successful_results:
                            if result.get('analysis'):
                                category = result['analysis'].primary_difficulty_category.value
                                category_stats[category] = category_stats.get(category, 0) + 1
                        
                        logger.info("难度分布:")
                        for category, count in category_stats.items():
                            logger.info(f"  {category}: {count} 个铺面")
                        
                        # 显示组织统计
                        org_stats = organizer.get_category_statistics(output_dir)
                        logger.info(f"文件组织统计: 总共 {org_stats['total_files']} 个文件")
                        for category, info in org_stats['categories'].items():
                            if info['count'] > 0:
                                logger.info(f"  {category}: {info['count']} 个文件")
            else:
                # 模拟运行模式
                logger.info(f"步骤 3-4: 模拟搜索和匹配 {len(audio_files)} 个音频文件...")
                
                match_results = []
                with tqdm(total=len(audio_files), desc="模拟进度") as pbar:
                    for audio_file in audio_files:
                        # 搜索和匹配
                        search_results = await searcher.search(audio_file.title, audio_file.artist)
                        if search_results:
                            best_matches = matcher.find_all_matches(audio_file, search_results, max_results=1)
                            if best_matches:
                                scored_maps = scorer.score_beatmaps(best_matches)
                                if scored_maps:
                                    match_results.append({
                                        'audio_file': audio_file,
                                        'best_match': scored_maps[0]
                                    })
                        pbar.update(1)
                
                logger.info("=" * 60)
                logger.info(f"模拟运行完成！匹配结果: {len(match_results)}/{len(audio_files)} 成功")
                
                if match_results:
                    logger.info("匹配的铺面:")
                    for result in match_results[:10]:  # 只显示前10个
                        audio = result['audio_file']
                        match = result['best_match']
                        logger.info(f"  {audio.artist} - {audio.title} -> {match.beatmap.name} (分数: {match.total_score:.3f})")
                    
                    if len(match_results) > 10:
                        logger.info(f"  ... 还有 {len(match_results) - 10} 个匹配结果")
        
        logger.info("=" * 60)
        logger.info("程序执行完成")
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())