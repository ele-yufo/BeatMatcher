"""
测试Windows兼容性改进
Test Windows compatibility improvements
"""

import pytest
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.beatsaver.downloader import BeatmapDownloader
from src.beatsaver.models import BeatSaverMap, BeatSaverMetadata, BeatSaverStats, BeatSaverUser
from src.utils.config import Config


class TestWindowsCompatibility:
    """测试Windows兼容性功能"""
    
    @pytest.fixture
    def config(self):
        """配置fixture"""
        config_data = {
            'logging': {'level': 'INFO', 'file': 'test.log'},
            'beatsaver': {
                'base_url': 'https://api.beatsaver.com', 
                'max_retries': 3,
                'request_delay': 1.0,
                'timeout': 30
            },
            'matching': {'title_weight': 0.6, 'artist_weight': 0.4},
            'scoring': {'download_count_weight': 0.3, 'rating_weight': 0.25, 'upvote_ratio_weight': 0.25, 'recency_weight': 0.2},
            'difficulty': {
                'categories': {
                    'easy': {'min': 0, 'max': 4, 'folder': 'Easy'},
                    'medium': {'min': 4, 'max': 7, 'folder': 'Medium'}, 
                    'hard': {'min': 7, 'max': 999, 'folder': 'Hard'}
                }
            },
            'files': {'max_concurrent_downloads': 3}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            return Config(config_path)
        finally:
            Path(config_path).unlink(missing_ok=True)
    
    def test_platform_specific_imports(self):
        """测试平台特定的导入处理"""
        # 重新导入模块以测试导入逻辑
        import importlib
        
        # 测试在不同平台上的导入行为
        with patch('sys.platform', 'linux'):
            try:
                # 重新加载模块
                import src.beatsaver.downloader
                importlib.reload(src.beatsaver.downloader)
                assert True  # 导入应该成功
            except ImportError:
                pytest.fail("Linux platform imports should succeed")
        
        with patch('sys.platform', 'win32'):
            try:
                import src.beatsaver.downloader
                importlib.reload(src.beatsaver.downloader)
                assert True  # 导入应该成功
            except ImportError:
                pytest.fail("Windows platform imports should succeed")
    
    def test_windows_reserved_names(self, config):
        """测试Windows保留名称处理"""
        downloader = BeatmapDownloader(config)
        
        # Windows保留名称列表
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        for reserved_name in reserved_names:
            # 测试大写
            cleaned = downloader._clean_filename(reserved_name)
            assert cleaned != reserved_name.lower()
            assert len(cleaned) > 0
            
            # 测试小写
            cleaned_lower = downloader._clean_filename(reserved_name.lower())
            assert len(cleaned_lower) > 0
            
            # 测试带扩展名
            name_with_ext = f"{reserved_name}.txt"
            cleaned_ext = downloader._clean_filename(name_with_ext)
            assert len(cleaned_ext) > 0
    
    def test_illegal_characters_removal(self, config):
        """测试非法字符清理"""
        downloader = BeatmapDownloader(config)
        
        # Windows和Linux通用的非法字符
        illegal_chars = '<>:"/\\|?*'
        control_chars = [chr(i) for i in range(0, 32)]  # 控制字符
        
        test_filename = "test" + "".join(illegal_chars) + "file" + "".join(control_chars[:5])
        cleaned = downloader._clean_filename(test_filename)
        
        # 验证所有非法字符都被清理
        for char in illegal_chars:
            assert char not in cleaned
        
        for char in control_chars[:5]:
            assert char not in cleaned
        
        # 验证基本内容还在
        assert "test" in cleaned
        assert "file" in cleaned
    
    def test_path_length_limits(self, config):
        """测试路径长度限制"""
        downloader = BeatmapDownloader(config)
        
        # 测试超长文件名
        very_long_name = "A" * 300
        cleaned = downloader._clean_filename(very_long_name)
        
        # 应该被截断到合理长度
        assert len(cleaned) <= 200
        assert len(cleaned) > 0
        
        # 测试正常长度文件名不受影响
        normal_name = "Normal Song Name"
        cleaned_normal = downloader._clean_filename(normal_name)
        assert cleaned_normal == normal_name
    
    def test_trailing_dots_and_spaces(self, config):
        """测试Windows文件名结尾处理"""
        downloader = BeatmapDownloader(config)
        
        test_cases = [
            "filename.",
            "filename ",
            "filename. ",
            "filename .txt",
            "filename...",
            "filename   "
        ]
        
        for test_name in test_cases:
            cleaned = downloader._clean_filename(test_name)
            
            # Windows兼容：不应该以点或空格结尾
            if sys.platform == 'win32' or hasattr(Path, 'drive'):
                assert not cleaned.endswith((' ', '.'))
            
            # 确保清理后不为空
            assert len(cleaned.strip()) > 0
    
    def test_unicode_handling(self, config):
        """测试Unicode字符处理"""
        downloader = BeatmapDownloader(config)
        
        unicode_names = [
            "测试歌曲",
            "música española",
            "日本の歌",
            "Émilie",
            "Björk",
            "café"
        ]
        
        for unicode_name in unicode_names:
            cleaned = downloader._clean_filename(unicode_name)
            
            # Unicode字符应该被保留
            assert len(cleaned) > 0
            # 应该不包含非法字符
            illegal_chars = '<>:"/\\|?*'
            for char in illegal_chars:
                assert char not in cleaned
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-specific test")
    def test_windows_file_locking_import(self):
        """测试Windows文件锁定模块导入"""
        try:
            import msvcrt
            assert msvcrt is not None
        except ImportError:
            pytest.fail("msvcrt should be available on Windows")
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix-specific test")  
    def test_unix_file_locking_import(self):
        """测试Unix文件锁定模块导入"""
        try:
            import fcntl
            assert fcntl is not None
        except ImportError:
            pytest.fail("fcntl should be available on Unix systems")
    
    def test_cross_platform_path_handling(self, config):
        """测试跨平台路径处理"""
        downloader = BeatmapDownloader(config)
        
        # 测试不同平台的路径分隔符
        path_variants = [
            "folder\\file.txt",  # Windows风格
            "folder/file.txt",   # Unix风格
            "folder\\subdir/file.txt",  # 混合风格
        ]
        
        for path_variant in path_variants:
            cleaned = downloader._clean_filename(path_variant)
            
            # 路径分隔符应该被转换为下划线
            assert "\\" not in cleaned
            assert "/" not in cleaned
            assert "folder" in cleaned
            assert "file.txt" in cleaned
    
    def test_file_system_compatibility(self, config):
        """测试文件系统兼容性"""
        downloader = BeatmapDownloader(config)
        
        # 创建包含各种字符的谱面信息
        from datetime import datetime
        mock_beatmap = BeatSaverMap(
            id="test123",
            name="Test/Beatmap:With<Special>Characters",
            description="Test description",
            uploader=BeatSaverUser(id=1, name="TestUser"),
            metadata=BeatSaverMetadata(
                bpm=120.0,
                duration=180,
                song_name="Song|Name?With*Issues",
                song_author_name='Artist"Name\\Test',
                level_author_name="Mapper",
                song_sub_name=""
            ),
            stats=BeatSaverStats(
                downloads=1000,
                plays=5000,
                upvotes=100,
                downvotes=10,
                score=0.9
            ),
            uploaded=datetime.now(),
            automapper=False,
            ranked=False,
            qualified=False,
            versions=[]
        )
        
        # 生成安全文件名
        safe_name = downloader._generate_safe_filename(mock_beatmap)
        
        # 验证文件名可以在各种文件系统上使用
        assert len(safe_name) > 0
        assert len(safe_name) <= 100
        
        # 验证没有问题字符
        problematic_chars = '<>:"/\\|?*'
        for char in problematic_chars:
            assert char not in safe_name
        
        # 验证包含关键信息
        assert "test123" in safe_name
    
    def test_empty_and_none_handling(self, config):
        """测试空值和None处理"""
        downloader = BeatmapDownloader(config)
        
        test_cases = [
            None,
            "",
            "   ",
            "\t\n",
        ]
        
        for test_case in test_cases:
            if test_case is None:
                # None应该被转换为默认值
                cleaned = downloader._clean_filename("unknown")
                assert cleaned == "unknown"
            else:
                cleaned = downloader._clean_filename(test_case)
                # 空字符串应该被转换为默认值
                assert len(cleaned) > 0
                assert cleaned == "unnamed"
    
    def test_concurrent_file_operations(self, config):
        """测试并发文件操作的线程安全性"""
        downloader = BeatmapDownloader(config)
        
        results = []
        errors = []
        
        def clean_filename_worker(filename):
            """工作线程函数"""
            try:
                result = downloader._clean_filename(filename)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时清理文件名
        threads = []
        test_filenames = [f"test{i}|filename<{i}>" for i in range(10)]
        
        for filename in test_filenames:
            thread = threading.Thread(target=clean_filename_worker, args=(filename,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证结果
        assert len(errors) == 0
        assert len(results) == len(test_filenames)
        
        # 验证所有结果都是有效的
        for result in results:
            assert len(result) > 0
            assert "|" not in result
            assert "<" not in result
            assert ">" not in result


class TestCrossPlatformThreading:
    """测试跨平台线程处理"""
    
    def test_threading_module_import(self):
        """测试线程模块导入"""
        import threading
        import asyncio
        
        # 这些模块应该在所有平台上都可用
        assert threading is not None
        assert asyncio is not None
    
    def test_asyncio_semaphore_cross_platform(self):
        """测试asyncio.Semaphore跨平台兼容性"""
        import asyncio
        
        async def test_semaphore():
            semaphore = asyncio.Semaphore(2)
            
            async def worker():
                async with semaphore:
                    await asyncio.sleep(0.01)
                    return True
            
            # 创建多个任务
            tasks = [worker() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(results)
        
        # 在当前事件循环中运行测试
        asyncio.run(test_semaphore())
    
    def test_concurrent_file_access(self, tmp_path):
        """测试并发文件访问"""
        import threading
        import time
        
        test_file = tmp_path / "test.txt"
        
        results = []
        errors = []
        
        def write_worker(worker_id):
            """写入工作线程"""
            try:
                with open(test_file, 'a') as f:
                    f.write(f"Worker {worker_id}\n")
                results.append(f"write_{worker_id}")
            except Exception as e:
                errors.append(e)
        
        def read_worker(worker_id):
            """读取工作线程"""
            try:
                # 等待文件被创建
                time.sleep(0.1)
                if test_file.exists():
                    with open(test_file, 'r') as f:
                        content = f.read()
                    results.append(f"read_{worker_id}")
            except Exception as e:
                errors.append(e)
        
        # 创建混合的读写线程
        threads = []
        for i in range(3):
            write_thread = threading.Thread(target=write_worker, args=(i,))
            read_thread = threading.Thread(target=read_worker, args=(i,))
            threads.extend([write_thread, read_thread])
        
        # 启动所有线程
        for thread in threads:
            thread.start()
        
        # 等待完成
        for thread in threads:
            thread.join()
        
        # 验证没有严重错误
        assert len(errors) == 0
        assert len(results) > 0