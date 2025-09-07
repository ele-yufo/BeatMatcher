"""
异步集成测试
Test async patterns and integration workflows
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import main
from src.utils.config import Config


class TestAsyncPatterns:
    """测试异步模式和集成工作流"""
    
    @pytest.fixture
    def temp_dirs(self):
        """临时目录fixtures"""
        music_dir = tempfile.mkdtemp()
        output_dir = tempfile.mkdtemp()
        
        # 创建一些测试音乐文件
        music_path = Path(music_dir)
        (music_path / "test1.mp3").touch()
        (music_path / "test2.mp3").touch()
        (music_path / "test3.flac").touch()
        
        yield Path(music_dir), Path(output_dir)
        
        # 清理
        import shutil
        shutil.rmtree(music_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_async_await_patterns(self):
        """测试async/await模式的正确性"""
        
        # 模拟异步函数调用链
        call_order = []
        
        async def mock_searcher_search(*args, **kwargs):
            call_order.append("searcher")
            await asyncio.sleep(0.01)
            return [Mock()]
        
        async def mock_downloader_download(*args, **kwargs):
            call_order.append("downloader")
            await asyncio.sleep(0.01)
            return Path("/tmp/test.zip")
        
        async def mock_organizer_organize(*args, **kwargs):
            call_order.append("organizer")
            await asyncio.sleep(0.01)
            return Path("/tmp/organized")
        
        # 测试异步调用顺序
        searcher = AsyncMock()
        searcher.search.side_effect = mock_searcher_search
        
        downloader = AsyncMock()
        downloader.download.side_effect = mock_downloader_download
        
        organizer = AsyncMock()
        organizer.organize_by_difficulty.side_effect = mock_organizer_organize
        
        # 模拟完整的异步工作流
        search_results = await searcher.search("test", "artist")
        download_result = await downloader.download(Mock(), Path("/tmp"))
        organize_result = await organizer.organize_by_difficulty(Path("/tmp"), Mock())
        
        # 验证调用顺序
        assert call_order == ["searcher", "downloader", "organizer"]
        assert search_results is not None
        assert download_result is not None
        assert organize_result is not None
    
    @pytest.mark.asyncio 
    async def test_concurrent_semaphore_behavior(self):
        """测试并发信号量行为"""
        max_concurrent = 2
        active_tasks = []
        max_active = 0
        
        async def tracked_task(task_id):
            """带跟踪的任务"""
            nonlocal max_active
            active_tasks.append(task_id)
            max_active = max(max_active, len(active_tasks))
            
            await asyncio.sleep(0.1)  # 模拟工作
            
            active_tasks.remove(task_id)
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def semaphore_controlled_task(task_id):
            async with semaphore:
                return await tracked_task(task_id)
        
        # 创建多个任务
        tasks = [semaphore_controlled_task(i) for i in range(5)]
        
        # 并发执行
        await asyncio.gather(*tasks)
        
        # 验证最大并发数不超过限制
        assert max_active <= max_concurrent
        assert max_active > 0  # 确保有任务执行
        assert len(active_tasks) == 0  # 所有任务都应该完成
    
    @pytest.mark.asyncio
    async def test_error_handling_in_async_context(self):
        """测试异步上下文中的错误处理"""
        
        successful_tasks = []
        failed_tasks = []
        
        async def failing_task(task_id, should_fail=False):
            """可能失败的任务"""
            if should_fail:
                raise Exception(f"Task {task_id} failed")
            
            await asyncio.sleep(0.01)
            successful_tasks.append(task_id)
            return f"success_{task_id}"
        
        # 创建混合任务（一些会失败）
        tasks = [
            failing_task(1, False),  # 成功
            failing_task(2, True),   # 失败  
            failing_task(3, False),  # 成功
            failing_task(4, True),   # 失败
            failing_task(5, False),  # 成功
        ]
        
        # 使用return_exceptions=True收集所有结果
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                failed_tasks.append(i)
        
        # 验证错误处理
        assert len(successful_tasks) == 3
        assert len(failed_tasks) == 2
        assert 2 in failed_tasks
        assert 4 in failed_tasks
        assert all(isinstance(r, (str, Exception)) for r in results)
    
    @pytest.mark.asyncio
    async def test_async_context_managers(self):
        """测试异步上下文管理器"""
        
        class MockAsyncResource:
            def __init__(self):
                self.is_open = False
                self.operations = []
            
            async def __aenter__(self):
                self.is_open = True
                self.operations.append("opened")
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.is_open = False
                self.operations.append("closed")
            
            async def do_work(self):
                if not self.is_open:
                    raise RuntimeError("Resource not open")
                self.operations.append("work_done")
                return "result"
        
        resource = MockAsyncResource()
        
        # 测试正常使用
        async with resource as r:
            result = await r.do_work()
            assert result == "result"
            assert r.is_open
        
        # 验证资源已正确关闭
        assert not resource.is_open
        assert resource.operations == ["opened", "work_done", "closed"]
        
        # 测试异常情况
        resource2 = MockAsyncResource()
        
        try:
            async with resource2 as r:
                await r.do_work()
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # 验证即使有异常，资源也被正确关闭
        assert not resource2.is_open
        assert "closed" in resource2.operations
    
    def test_main_simple_similarity_edge_cases(self):
        """测试main.py中simple_similarity函数的边界情况"""
        
        # 测试None和空字符串
        assert main.simple_similarity(None, "test") == 0.0
        assert main.simple_similarity("test", None) == 0.0
        assert main.simple_similarity(None, None) == 0.0
        
        # 测试空字符串
        assert main.simple_similarity("", "test") == 0.0
        assert main.simple_similarity("test", "") == 0.0
        assert main.simple_similarity("", "") == 0.0
        
        # 测试大小写
        assert main.simple_similarity("Test", "test") == 1.0
        assert main.simple_similarity("HELLO WORLD", "hello world") == 1.0
        
        # 测试包含匹配
        assert main.simple_similarity("hello world music", "hello") == 0.8
        assert main.simple_similarity("test", "this is a test song") == 0.8
        
        # 测试词汇匹配
        similarity = main.simple_similarity("hello world", "world music")
        assert 0.0 < similarity < 1.0
        
        # 测试无匹配
        assert main.simple_similarity("abc", "xyz") == 0.0
        assert main.simple_similarity("completely different", "nothing matches") == 0.0
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_with_real_semaphore(self):
        """使用真实的main.py函数测试并发处理"""
        
        # 创建模拟的音频文件
        mock_audio_files = []
        for i in range(5):
            audio_file = Mock()
            audio_file.title = f"Song {i}"
            audio_file.artist = f"Artist {i}"
            mock_audio_files.append(audio_file)
        
        # 模拟组件
        searcher = AsyncMock()
        matcher = Mock()
        scorer = Mock()
        downloader = AsyncMock()
        analyzer = Mock()
        organizer = AsyncMock()
        output_dir = Path("/tmp/test_output")
        logger = Mock()
        
        # 跟踪并发执行
        processing_times = []
        
        async def mock_process_single_audio_file(*args, **kwargs):
            """模拟单个文件处理"""
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)  # 模拟处理时间
            end_time = asyncio.get_event_loop().time()
            processing_times.append(end_time - start_time)
            return {"success": True, "processing_time": end_time - start_time}
        
        # 使用patch模拟process_single_audio_file函数
        with patch('main.process_single_audio_file', side_effect=mock_process_single_audio_file):
            start_time = asyncio.get_event_loop().time()
            
            # 调用真实的并发处理函数
            results = await main.process_audio_files_concurrently(
                mock_audio_files, searcher, matcher, scorer, downloader,
                analyzer, organizer, output_dir, logger, max_concurrent=2
            )
            
            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time
        
        # 验证结果
        assert len(results) == 5
        assert all(r is not None for r in results)
        
        # 验证并发性能：总时间应该少于串行执行时间
        # 串行时间约为 5 * 0.1 = 0.5秒
        # 并发时间（最大并发2）应该约为 3 * 0.1 = 0.3秒
        assert total_time < 0.45  # 允许一些误差
        
        # 验证所有任务都被处理
        assert len(processing_times) == 5
    
    @pytest.mark.asyncio
    async def test_asyncio_task_cancellation(self):
        """测试异步任务取消"""
        
        cancelled_tasks = []
        completed_tasks = []
        
        async def cancellable_task(task_id):
            """可取消的任务"""
            try:
                await asyncio.sleep(0.5)
                completed_tasks.append(task_id)
                return f"completed_{task_id}"
            except asyncio.CancelledError:
                cancelled_tasks.append(task_id)
                raise
        
        # 创建任务
        tasks = [asyncio.create_task(cancellable_task(i)) for i in range(3)]
        
        # 等待一小段时间后取消部分任务
        await asyncio.sleep(0.1)
        tasks[1].cancel()  # 取消第二个任务
        
        # 等待所有任务完成或被取消
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证取消行为
        assert len(cancelled_tasks) == 1
        assert 1 in cancelled_tasks
        
        # 验证结果类型
        assert len(results) == 3
        assert isinstance(results[1], asyncio.CancelledError)
    
    def test_async_generator_patterns(self):
        """测试异步生成器模式（如果项目中使用）"""
        
        async def async_file_generator(count):
            """异步文件生成器示例"""
            for i in range(count):
                await asyncio.sleep(0.01)  # 模拟异步操作
                yield f"file_{i}.mp3"
        
        async def consume_async_generator():
            files = []
            async for file in async_file_generator(5):
                files.append(file)
            return files
        
        # 运行测试
        files = asyncio.run(consume_async_generator())
        
        # 验证结果
        assert len(files) == 5
        assert all(f.startswith("file_") and f.endswith(".mp3") for f in files)
        assert files == ["file_0.mp3", "file_1.mp3", "file_2.mp3", "file_3.mp3", "file_4.mp3"]


class TestAsyncErrorRecovery:
    """测试异步错误恢复机制"""
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self):
        """测试部分失败的处理"""
        
        results = {"success": [], "failed": []}
        
        async def process_item(item_id, should_fail=False):
            """处理单个项目"""
            try:
                if should_fail:
                    raise Exception(f"Processing failed for {item_id}")
                
                await asyncio.sleep(0.01)
                results["success"].append(item_id)
                return {"id": item_id, "status": "success"}
                
            except Exception as e:
                results["failed"].append(item_id)
                return {"id": item_id, "status": "failed", "error": str(e)}
        
        # 创建混合任务（部分失败）
        tasks = []
        for i in range(5):
            should_fail = i % 2 == 1  # 奇数ID失败
            tasks.append(process_item(i, should_fail))
        
        # 执行所有任务
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        assert len(results["success"]) == 3  # 0, 2, 4成功
        assert len(results["failed"]) == 2   # 1, 3失败
        
        # 验证没有异常被抛出到外层
        assert not any(isinstance(r, Exception) for r in task_results)
        
        # 验证所有任务都返回了结果
        assert len(task_results) == 5
        success_count = sum(1 for r in task_results if r.get("status") == "success")
        failed_count = sum(1 for r in task_results if r.get("status") == "failed")
        
        assert success_count == 3
        assert failed_count == 2
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """测试超时处理"""
        
        async def slow_task(duration):
            """慢任务"""
            await asyncio.sleep(duration)
            return f"completed after {duration}s"
        
        # 测试正常完成
        try:
            result = await asyncio.wait_for(slow_task(0.1), timeout=0.2)
            assert result == "completed after 0.1s"
        except asyncio.TimeoutError:
            pytest.fail("Task should not have timed out")
        
        # 测试超时
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_task(0.3), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_cancellation(self):
        """测试取消时的资源清理"""
        
        class ResourceTracker:
            def __init__(self):
                self.opened_resources = set()
                self.closed_resources = set()
            
            def open_resource(self, resource_id):
                self.opened_resources.add(resource_id)
            
            def close_resource(self, resource_id):
                self.closed_resources.add(resource_id)
                self.opened_resources.discard(resource_id)
        
        tracker = ResourceTracker()
        
        async def resource_using_task(task_id):
            """使用资源的任务"""
            resource_id = f"resource_{task_id}"
            try:
                tracker.open_resource(resource_id)
                await asyncio.sleep(1.0)  # 长时间操作
                return f"completed_{task_id}"
            except asyncio.CancelledError:
                # 清理资源
                tracker.close_resource(resource_id)
                raise
            finally:
                # 确保资源被清理
                tracker.close_resource(resource_id)
        
        # 启动任务
        task = asyncio.create_task(resource_using_task(1))
        
        # 等待一小段时间后取消
        await asyncio.sleep(0.1)
        task.cancel()
        
        # 等待取消完成
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # 验证资源被正确清理
        assert len(tracker.opened_resources) == 0
        assert "resource_1" in tracker.closed_resources