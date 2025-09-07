#!/usr/bin/env python3
"""
BeatMatcher - 自动下载本地音乐对应的 Beat Saber 谱面
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
    start_time = asyncio.get_event_loop().time()
    try:
        logger.info(f"处理文件: {audio_file.title} - {audio_file.artist}")
        
        # 1. 搜索谱面 - 使用多层搜索策略
        search_results = await searcher.search(audio_file.title, audio_file.artist)
        
        # 如果组合搜索失败，尝试只用标题搜索
        if not search_results:
            logger.info(f"组合搜索失败，尝试仅标题搜索: {audio_file.title}")
            search_results = await searcher.search_by_title_only(audio_file.title)
        
        # 如果标题搜索也失败，尝试只用艺术家搜索
        if not search_results and audio_file.artist.lower() != "unknown artist":
            logger.info(f"标题搜索失败，尝试仅艺术家搜索: {audio_file.artist}")
            search_results = await searcher.search_by_artist_only(audio_file.artist)
        
        if not search_results:
            logger.warning(f"所有搜索策略均失败: {audio_file.artist} - {audio_file.title}")
            return None
        
        logger.info(f"找到 {len(search_results)} 个候选谱面")
        
        # 2. 简单匹配 - 找到第一个合理的匹配即可
        best_match = None
        for beatmap in search_results:
            # 简单的相似度检查：歌名或作者有一个匹配就算成功
            title_match = simple_similarity(audio_file.title, beatmap.metadata.song_name) > 0.3
            artist_match = simple_similarity(audio_file.artist, beatmap.metadata.song_author_name) > 0.3
            
            if title_match or artist_match:
                best_match = beatmap
                logger.info(f"找到匹配: {beatmap.metadata.song_name} by {beatmap.metadata.song_author_name}")
                break
        
        if not best_match:
            logger.warning(f"无合适匹配: {audio_file.title} - {audio_file.artist}")
            return None
        
        # 3. 下载谱面文件（可能返回ZIP文件或已存在的文件夹）
        download_result = await downloader.download(best_match, output_dir)
        if not download_result:
            logger.error(f"下载失败: {best_match.name}")
            return None
        
        # 4. 处理下载结果（ZIP文件需要解压，文件夹直接使用）
        if download_result.suffix == '.zip':
            # 是ZIP文件，需要解压
            downloaded_zip_path = download_result
            extracted_dir = downloader.extract_beatmap(downloaded_zip_path)
            if not extracted_dir:
                logger.error(f"解压失败: {downloaded_zip_path}")
                # 清理失败的ZIP文件
                downloaded_zip_path.unlink(missing_ok=True)
                return None
            
            # 解压成功后删除ZIP文件
            should_cleanup_zip = True
        else:
            # 是已存在的文件夹，直接使用
            extracted_dir = download_result
            downloaded_zip_path = None
            should_cleanup_zip = False
        
        # 5. 分析难度
        analysis = analyzer.analyze_beatmap(extracted_dir)
        if not analysis:
            logger.warning(f"难度分析失败，将使用默认中等难度分类: {extracted_dir}")
            # 创建一个默认的分析结果用于中等难度分类
            from src.difficulty.models import DifficultyStats, BeatmapAnalysis, DifficultyCategory
            default_stats = DifficultyStats(
                notes_count=100, 
                obstacles_count=0, 
                events_count=0,
                duration=180.0, 
                bpm=120.0, 
                nps=4.5,  # 中等难度的NPS值
                peak_nps=4.5, 
                density_variations=[4.5],
                difficulty_name="Unknown", 
                characteristic="Standard"
            )
            analysis = BeatmapAnalysis(
                beatmap_id=extracted_dir.name,
                song_name=audio_file.title or "Unknown",
                difficulties=[default_stats]
            )
        
        # 6. 组织到难度文件夹
        final_path = await organizer.organize_by_difficulty(extracted_dir, analysis)
        
        # 7. 清理原始ZIP文件（只在新下载时删除）
        if should_cleanup_zip and downloaded_zip_path:
            try:
                downloaded_zip_path.unlink()
                logger.debug(f"已删除ZIP文件: {downloaded_zip_path}")
            except Exception as e:
                logger.warning(f"删除ZIP文件失败: {downloaded_zip_path} - {e}")
                # 不影响主流程，继续处理
        
        processing_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"完成处理: {audio_file.title} -> {analysis.primary_difficulty_category.value} (耗时: {processing_time:.1f}秒)")
        
        return {
            'audio_file': audio_file,
            'beatmap': best_match,
            'downloaded_zip_path': downloaded_zip_path,
            'extracted_dir': extracted_dir,
            'final_path': final_path,
            'analysis': analysis,
            'processing_time': processing_time
        }
        
    except Exception as e:
        logger.error(f"处理音频文件失败: {audio_file.title} - {e}")
        
        # 错误恢复：清理可能产生的临时文件
        try:
            # 如果有已下载的ZIP文件且需要清理，清理它
            if ('should_cleanup_zip' in locals() and should_cleanup_zip and 
                'downloaded_zip_path' in locals() and downloaded_zip_path and downloaded_zip_path.exists()):
                downloaded_zip_path.unlink()
                logger.debug(f"清理失败任务的ZIP文件: {downloaded_zip_path}")
            
            # 如果有已解压的目录但处理失败，保留它（用户可能需要手动处理）
            if 'extracted_dir' in locals() and extracted_dir and extracted_dir.exists():
                logger.info(f"保留部分处理的文件夹以供手动检查: {extracted_dir}")
                
        except Exception as cleanup_error:
            logger.warning(f"清理失败任务时出错: {cleanup_error}")
        
        return None


async def process_audio_files_concurrently(
    audio_files,
    searcher,
    matcher,
    scorer,
    downloader,
    analyzer,
    organizer,
    output_dir,
    logger,
    max_concurrent=3
):
    """并发处理音频文件列表"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(audio_file):
        """使用信号量控制并发的处理函数"""
        async with semaphore:
            return await process_single_audio_file(
                audio_file, searcher, matcher, scorer, downloader,
                analyzer, organizer, output_dir, logger
            )
    
    # 创建所有任务
    tasks = [process_with_semaphore(audio_file) for audio_file in audio_files]
    
    # 使用进度条监控并发执行
    results = []
    completed = 0
    
    with tqdm(total=len(audio_files), desc="并发处理进度") as pbar:
        # 使用 asyncio.as_completed 来获取完成的任务
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                results.append(result)
                completed += 1
                pbar.update(1)
                
                # 记录进度
                if completed % 10 == 0 or completed == len(audio_files):
                    success_count = sum(1 for r in results if r is not None)
                    logger.info(f"并发进度: {completed}/{len(audio_files)}, 成功: {success_count}")
                    
            except Exception as e:
                logger.error(f"并发处理任务失败: {e}")
                results.append(None)
                completed += 1
                pbar.update(1)
    
    return results


def simple_similarity(str1: str, str2: str) -> float:
    """简单的字符串相似度计算"""
    if not str1 or not str2:
        return 0.0
    
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    
    # 完全匹配
    if str1 == str2:
        return 1.0
    
    # 包含匹配
    if str1 in str2 or str2 in str1:
        return 0.8
    
    # 词汇匹配
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    if words1 & words2:  # 有交集
        return len(words1 & words2) / max(len(words1), len(words2))
    
    return 0.0


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="BeatMatcher - 自动下载本地音乐对应的 Beat Saber 谱面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps --config my_config.yaml
  python main.py --music-dir /path/to/music --output-dir /path/to/beatmaps --max-files 10
        """
    )
    parser.add_argument("--music-dir", type=str, required=True, help="本地音乐目录路径")
    parser.add_argument("--output-dir", type=str, required=True, help="输出谱面目录路径")
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
        logger.info("开始 BeatSaber 谱面下载任务")
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
                    
                    # 3-7. 并发处理音频文件
                    logger.info(f"步骤 3-7: 并发处理 {len(audio_files)} 个音频文件...")
                    
                    # 获取并发配置
                    max_concurrent = getattr(config.performance, 'max_concurrent_tasks', 3)
                    logger.info(f"使用并发数: {max_concurrent}")
                    
                    results = await process_audio_files_concurrently(
                        audio_files, searcher, matcher, scorer, downloader,
                        analyzer, organizer, output_dir, logger, max_concurrent
                    )
                    
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
                            logger.info(f"  {category}: {count} 个谱面")
                        
                        # 显示组织统计
                        org_stats = organizer.get_category_statistics(output_dir)
                        logger.info(f"文件组织统计: 总共 {org_stats['total_files']} 个谱面")
                        for category, info in org_stats['categories'].items():
                            if info['count'] > 0:
                                logger.info(f"  {category}: {info['count']} 个谱面（文件夹: {info['folders']}, ZIP: {info['zip_files']}）")
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
                    logger.info("匹配的谱面:")
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